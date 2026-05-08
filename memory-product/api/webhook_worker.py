"""
CP8 P5.4 — Webhook Delivery Worker

Processes pending webhook deliveries with retry logic, exponential backoff,
and auto-disable on excessive failures.

Can be run:
1. As a periodic cron job (every 30s via systemd timer)
2. As a standalone script (for manual processing)
3. As an RQ job (future enhancement)
"""

import sys
import os
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import psycopg2
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger("zerolatency.webhook_worker")

# Retry schedule: delays in seconds for each attempt
RETRY_DELAYS = [60, 300, 1500, 7200, 43200]  # 1m, 5m, 25m, 2h, 12h
MAX_ATTEMPTS = 5
AUTO_DISABLE_THRESHOLD = 40  # Consecutive failures before auto-disabling webhook
DELIVERY_TIMEOUT = 10  # seconds
BATCH_SIZE = 50


def sign_payload(secret_hex: str, raw_body: bytes) -> tuple[int, str]:
    """Generate HMAC signature for webhook payload."""
    import hmac
    import hashlib

    t = int(time.time())
    msg = f"{t}.".encode() + raw_body
    sig = hmac.new(bytes.fromhex(secret_hex), msg, hashlib.sha256).hexdigest()
    return t, sig


def process_webhook_queue(conn) -> dict:
    """
    Process pending webhook deliveries.

    Returns:
        Dict with statistics: {delivered, failed, dead_lettered}
    """
    stats = {
        "delivered": 0,
        "failed": 0,
        "dead_lettered": 0,
        "auto_disabled": 0
    }

    cur = conn.cursor()

    # Claim pending deliveries using FOR UPDATE SKIP LOCKED
    cur.execute(
        """
        SELECT wd.id, wd.webhook_id, wd.event_id, wd.event_type, wd.payload,
               wd.attempt_count, wd.tenant_id,
               tw.url, tw.secret, tw.consecutive_failures
        FROM memory_service.webhook_deliveries wd
        JOIN memory_service.tenant_webhooks tw ON wd.webhook_id = tw.id
        WHERE wd.status = 'pending'
          AND wd.next_attempt_at <= NOW()
          AND tw.enabled = true
          AND tw.deleted_at IS NULL
        ORDER BY wd.next_attempt_at ASC
        LIMIT %s
        FOR UPDATE OF wd SKIP LOCKED
        """,
        (BATCH_SIZE,)
    )

    deliveries = cur.fetchall()

    if not deliveries:
        logger.debug("No pending deliveries")
        return stats

    logger.info(f"Processing {len(deliveries)} pending deliveries")

    for delivery in deliveries:
        (delivery_id, webhook_id, event_id, event_type, payload,
         attempt_count, tenant_id, url, secret, consecutive_failures) = delivery

        try:
            # Serialize payload and sign
            if isinstance(payload, str):
                payload_json = payload
                payload_bytes = payload.encode('utf-8')
            else:
                payload_json = json.dumps(payload)
                payload_bytes = payload_json.encode('utf-8')

            timestamp, signature = sign_payload(secret, payload_bytes)

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-0Latency-Signature": f"t={timestamp},v1={signature}",
                "User-Agent": "0Latency-Webhooks/1.0"
            }

            # Attempt delivery
            logger.info(f"Delivering webhook {delivery_id} to {url} (attempt {attempt_count + 1}/{MAX_ATTEMPTS})")

            with httpx.Client(timeout=DELIVERY_TIMEOUT) as client:
                response = client.post(url, content=payload_bytes, headers=headers)

            status_code = response.status_code
            last_attempt_at = datetime.now(timezone.utc)

            # Check if delivery was successful (2xx status)
            if 200 <= status_code < 300:
                # Success! Mark as delivered
                cur.execute(
                    """
                    UPDATE memory_service.webhook_deliveries
                    SET status = 'delivered',
                        last_attempt_at = %s,
                        last_status_code = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (last_attempt_at, status_code, delivery_id)
                )

                # Reset webhook's consecutive_failures counter
                cur.execute(
                    """
                    UPDATE memory_service.tenant_webhooks
                    SET consecutive_failures = 0,
                        last_success_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (last_attempt_at, webhook_id)
                )

                conn.commit()
                stats["delivered"] += 1
                logger.info(f"Delivery {delivery_id} succeeded with status {status_code}")

            else:
                # Non-2xx response: schedule retry or dead-letter
                handle_delivery_failure(
                    conn, cur, delivery_id, webhook_id, tenant_id,
                    attempt_count, consecutive_failures,
                    status_code, f"HTTP {status_code}", stats
                )

        except httpx.TimeoutException as e:
            # Timeout: schedule retry or dead-letter
            handle_delivery_failure(
                conn, cur, delivery_id, webhook_id, tenant_id,
                attempt_count, consecutive_failures,
                None, f"Timeout: {str(e)}", stats
            )

        except Exception as e:
            # Other error: schedule retry or dead-letter
            error_msg = str(e)[:500]
            logger.error(f"Delivery {delivery_id} failed: {error_msg}")
            handle_delivery_failure(
                conn, cur, delivery_id, webhook_id, tenant_id,
                attempt_count, consecutive_failures,
                None, error_msg, stats
            )

    return stats


def handle_delivery_failure(
    conn, cur, delivery_id, webhook_id, tenant_id,
    attempt_count, consecutive_failures,
    status_code, error_msg, stats
):
    """Handle a failed delivery attempt with retry or dead-letter logic."""

    new_attempt_count = attempt_count + 1
    new_consecutive_failures = consecutive_failures + 1

    if new_attempt_count >= MAX_ATTEMPTS:
        # Exhausted retries: mark as dead
        cur.execute(
            """
            UPDATE memory_service.webhook_deliveries
            SET status = 'dead',
                attempt_count = %s,
                last_attempt_at = NOW(),
                last_status_code = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (new_attempt_count, status_code, error_msg, delivery_id)
        )

        # Log dead-letter audit event
        cur.execute(
            """
            INSERT INTO memory_service.synthesis_audit_events
            (tenant_id, target_memory_id, event_type, actor, event_payload)
            VALUES (%s, NULL, 'webhook_dead_lettered', 'system', %s::jsonb)
            """,
            (tenant_id, json.dumps({
                "delivery_id": str(delivery_id),
                "webhook_id": str(webhook_id),
                "attempts": new_attempt_count,
                "last_error": error_msg
            }))
        )

        conn.commit()
        stats["dead_lettered"] += 1
        logger.warning(f"Delivery {delivery_id} dead-lettered after {new_attempt_count} attempts")

    else:
        # Schedule retry with exponential backoff
        delay_seconds = RETRY_DELAYS[new_attempt_count - 1] if new_attempt_count <= len(RETRY_DELAYS) else RETRY_DELAYS[-1]
        next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

        cur.execute(
            """
            UPDATE memory_service.webhook_deliveries
            SET attempt_count = %s,
                next_attempt_at = %s,
                last_attempt_at = NOW(),
                last_status_code = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (new_attempt_count, next_attempt_at, status_code, error_msg, delivery_id)
        )

        conn.commit()
        stats["failed"] += 1
        logger.info(f"Delivery {delivery_id} failed (attempt {new_attempt_count}), retry in {delay_seconds}s")

    # Update webhook's consecutive failures
    cur.execute(
        """
        UPDATE memory_service.tenant_webhooks
        SET consecutive_failures = %s,
            last_failure_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (new_consecutive_failures, webhook_id)
    )

    # Check if we should auto-disable the webhook
    if new_consecutive_failures >= AUTO_DISABLE_THRESHOLD:
        cur.execute(
            """
            UPDATE memory_service.tenant_webhooks
            SET enabled = false,
                updated_at = NOW()
            WHERE id = %s
            """,
            (webhook_id,)
        )

        # Log auto-disable audit event
        cur.execute(
            """
            INSERT INTO memory_service.synthesis_audit_events
            (tenant_id, target_memory_id, event_type, actor, event_payload)
            VALUES (%s, NULL, 'webhook_auto_disabled', 'system', %s::jsonb)
            """,
            (tenant_id, json.dumps({
                "webhook_id": str(webhook_id),
                "consecutive_failures": new_consecutive_failures,
                "threshold": AUTO_DISABLE_THRESHOLD
            }))
        )

        conn.commit()
        stats["auto_disabled"] += 1
        logger.warning(f"Webhook {webhook_id} auto-disabled after {new_consecutive_failures} consecutive failures")
    else:
        conn.commit()


def main():
    """Main entry point for webhook worker."""
    logger.info("Starting webhook delivery worker")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("FATAL: DATABASE_URL not set")
        sys.exit(1)

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False

        stats = process_webhook_queue(conn)

        logger.info(f"Worker run complete: delivered={stats['delivered']} "
                   f"failed={stats['failed']} dead_lettered={stats['dead_lettered']} "
                   f"auto_disabled={stats['auto_disabled']}")

        conn.close()
        sys.exit(0)

    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
