"""
Webhook emission module for CP8 P5.4

Handles enqueuing webhook events when synthesis memories are replaced,
payload construction, and HMAC signing.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def sign_payload(secret_hex: str, raw_body: bytes) -> tuple[int, str]:
    """
    Generate HMAC signature for webhook payload using Stripe-style format.

    Args:
        secret_hex: 64-character hex string (32 bytes)
        raw_body: Raw JSON payload bytes

    Returns:
        (timestamp, signature_hex)
    """
    t = int(time.time())
    msg = f"{t}.".encode() + raw_body
    sig = hmac.new(bytes.fromhex(secret_hex), msg, hashlib.sha256).hexdigest()
    return t, sig


def generate_webhook_secret() -> str:
    """Generate a 32-byte secret for webhook HMAC signing."""
    return secrets.token_hex(32)  # 64 hex characters


def build_synthesis_replaced_payload(
    old_memory: dict,
    new_memory: dict,
    tenant_id: str,
    agent_id: str,
    change_reason: Optional[str] = None,
    audit_event_id: Optional[str] = None
) -> dict:
    """
    Build the payload for a synthesis.replaced webhook event.

    Args:
        old_memory: Dict with keys: id, headline, context, full_content, created_at
        new_memory: Dict with keys: id, headline, context, full_content, created_at
        tenant_id: Tenant UUID
        agent_id: Agent identifier
        change_reason: Optional explanation for the replacement
        audit_event_id: Optional UUID of the audit event

    Returns:
        Payload dict ready for JSON serialization
    """
    event_id = str(uuid4())
    occurred_at = datetime.now(timezone.utc).isoformat()

    return {
        "event_id": event_id,
        "event_type": "synthesis.replaced",
        "event_version": "1.0",
        "occurred_at": occurred_at,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "synthesis": {
            "memory_id": str(old_memory["id"]),
            "old_version": {
                "headline": old_memory.get("headline", ""),
                "context": old_memory.get("context", ""),
                "full_content": old_memory.get("full_content", ""),
                "created_at": old_memory.get("created_at", "").isoformat() if hasattr(old_memory.get("created_at", ""), "isoformat") else str(old_memory.get("created_at", ""))
            },
            "new_version": {
                "memory_id": str(new_memory["id"]),
                "headline": new_memory.get("headline", ""),
                "context": new_memory.get("context", ""),
                "full_content": new_memory.get("full_content", ""),
                "created_at": new_memory.get("created_at", "").isoformat() if hasattr(new_memory.get("created_at", ""), "isoformat") else str(new_memory.get("created_at", ""))
            },
            "change_reason": change_reason,
            "audit_event_id": audit_event_id
        }
    }


def enqueue_webhook_event(
    conn,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> int:
    """
    Enqueue webhook deliveries for all enabled webhooks matching the event type.

    This function MUST be called within an existing database transaction.
    It will query for matching webhooks and insert delivery records.
    If the transaction rolls back, no webhooks will be sent (outbox pattern).

    Args:
        conn: psycopg2 connection object (within transaction)
        tenant_id: Tenant UUID
        event_type: Event type (e.g., "synthesis.replaced")
        payload: Event payload dict

    Returns:
        Number of webhook deliveries enqueued
    """
    cur = conn.cursor()

    # Find all enabled webhooks for this tenant that match the event type
    cur.execute(
        """
        SELECT id, url, secret
        FROM memory_service.tenant_webhooks
        WHERE tenant_id = %s
          AND enabled = true
          AND deleted_at IS NULL
          AND %s = ANY(event_types)
        """,
        (tenant_id, event_type)
    )

    webhooks = cur.fetchall()

    if not webhooks:
        logger.debug(f"No enabled webhooks for tenant {tenant_id} event {event_type}")
        return 0

    # Serialize payload once
    payload_json = json.dumps(payload)
    event_id = payload.get("event_id", str(uuid4()))

    enqueued_count = 0
    for webhook_id, url, secret in webhooks:
        # Insert delivery record
        cur.execute(
            """
            INSERT INTO memory_service.webhook_deliveries
            (webhook_id, tenant_id, event_id, event_type, payload, status, attempt_count, next_attempt_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, 'pending', 0, NOW())
            """,
            (str(webhook_id), tenant_id, event_id, event_type, payload_json)
        )
        enqueued_count += 1

    logger.info(f"Enqueued {enqueued_count} webhook deliveries for tenant {tenant_id} event {event_type}")
    return enqueued_count
