"""
Webhooks — Event-driven notifications for memory state changes.
Feature gap #2 vs mem0: Real-time webhook delivery on memory events.
"""

import json
import hashlib
import hmac
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional
import requests

from storage_multitenant import _db_execute_rows

logger = logging.getLogger("zerolatency.webhooks")

# Background delivery queue
_delivery_queue: list[dict] = []
_delivery_lock = threading.Lock()
_delivery_thread: Optional[threading.Thread] = None

WEBHOOK_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
MAX_FAILURE_COUNT = 10  # disable webhook after this many consecutive failures


def register_webhook(tenant_id: str, url: str, events: list[str],
                     secret: str = None) -> dict:
    """Register a new webhook for a tenant."""
    valid_events = {
        "memory.created", "memory.updated", "memory.deleted",
        "memory.corrected", "memory.reinforced", "extraction.completed",
    }
    filtered_events = [e for e in events if e in valid_events]
    if not filtered_events:
        raise ValueError(f"No valid events. Choose from: {valid_events}")
    
    rows = _db_execute_rows("""
        INSERT INTO memory_service.webhooks (tenant_id, url, events, secret)
        VALUES (%s::UUID, %s, %s, %s)
        RETURNING id, created_at
    """, (tenant_id, url, filtered_events, secret), tenant_id=tenant_id)
    
    if rows:
        return {
            "id": str(rows[0][0]),
            "url": url,
            "events": filtered_events,
            "active": True,
            "created_at": str(rows[0][1]),
        }
    raise RuntimeError("Failed to register webhook")


def list_webhooks(tenant_id: str) -> list[dict]:
    """List all webhooks for a tenant."""
    rows = _db_execute_rows("""
        SELECT id, url, events, active, created_at, last_triggered, failure_count
        FROM memory_service.webhooks
        WHERE tenant_id = %s::UUID
        ORDER BY created_at DESC
    """, (tenant_id,), tenant_id=tenant_id)
    
    return [{
        "id": str(r[0]),
        "url": str(r[1]),
        "events": list(r[2]) if r[2] else [],
        "active": bool(r[3]),
        "created_at": str(r[4]),
        "last_triggered": str(r[5]) if r[5] else None,
        "failure_count": int(r[6]) if r[6] else 0,
    } for r in (rows or [])]


def delete_webhook(tenant_id: str, webhook_id: str) -> bool:
    """Delete a webhook."""
    rows = _db_execute_rows("""
        DELETE FROM memory_service.webhooks
        WHERE id = %s::UUID AND tenant_id = %s::UUID
        RETURNING id
    """, (webhook_id, tenant_id), tenant_id=tenant_id)
    return bool(rows)


def trigger_event(tenant_id: str, event_type: str, payload: dict):
    """
    Queue a webhook delivery for all matching webhooks.
    Delivery happens asynchronously in background thread.
    """
    # Find matching webhooks
    rows = _db_execute_rows("""
        SELECT id, url, secret, events
        FROM memory_service.webhooks
        WHERE tenant_id = %s::UUID AND active = true AND failure_count < %s
    """, (tenant_id, MAX_FAILURE_COUNT), tenant_id=tenant_id)
    
    for row in (rows or []):
        webhook_id, url, secret, events = str(row[0]), str(row[1]), row[2], list(row[3]) if row[3] else []
        
        if event_type not in events:
            continue
        
        delivery = {
            "webhook_id": webhook_id,
            "tenant_id": tenant_id,
            "url": url,
            "secret": str(secret) if secret else None,
            "event_type": event_type,
            "payload": {
                "event": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **payload,
            },
        }
        
        with _delivery_lock:
            _delivery_queue.append(delivery)
    
    # Ensure delivery thread is running
    _ensure_delivery_thread()


def _ensure_delivery_thread():
    """Start the background delivery thread if not running."""
    global _delivery_thread
    if _delivery_thread is None or not _delivery_thread.is_alive():
        _delivery_thread = threading.Thread(target=_delivery_worker, daemon=True)
        _delivery_thread.start()


def _delivery_worker():
    """Background worker that delivers queued webhooks."""
    while True:
        delivery = None
        with _delivery_lock:
            if _delivery_queue:
                delivery = _delivery_queue.pop(0)
        
        if delivery is None:
            time.sleep(0.5)
            # Exit thread if queue stays empty for 30 seconds
            empty_count = 0
            while empty_count < 60:
                time.sleep(0.5)
                with _delivery_lock:
                    if _delivery_queue:
                        break
                empty_count += 1
            else:
                return  # Exit thread — will be restarted when needed
            continue
        
        _deliver_webhook(delivery)


def _deliver_webhook(delivery: dict, retry: int = 0):
    """Deliver a single webhook with retry logic."""
    payload_json = json.dumps(delivery["payload"])
    
    headers = {
        "Content-Type": "application/json",
        "X-ZeroLatency-Event": delivery["event_type"],
        "X-ZeroLatency-Delivery": delivery["webhook_id"],
    }
    
    # HMAC signature if secret is configured
    if delivery.get("secret"):
        signature = hmac.new(
            delivery["secret"].encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        headers["X-ZeroLatency-Signature"] = f"sha256={signature}"
    
    success = False
    status_code = None
    response_body = None
    
    try:
        resp = requests.post(
            delivery["url"],
            data=payload_json,
            headers=headers,
            timeout=WEBHOOK_TIMEOUT,
        )
        status_code = resp.status_code
        response_body = resp.text[:500]
        success = 200 <= resp.status_code < 300
    except requests.exceptions.Timeout:
        status_code = 408
        response_body = "Timeout"
    except Exception as e:
        status_code = 0
        response_body = str(e)[:500]
    
    # Log delivery
    try:
        _db_execute_rows("""
            INSERT INTO memory_service.webhook_deliveries 
                (webhook_id, event_type, payload, status_code, response_body, success)
            VALUES (%s::UUID, %s, %s::jsonb, %s, %s, %s)
        """, (
            delivery["webhook_id"], delivery["event_type"],
            payload_json, status_code, response_body, success
        ), tenant_id=delivery["tenant_id"], fetch_results=False)
        
        if success:
            _db_execute_rows("""
                UPDATE memory_service.webhooks 
                SET last_triggered = now(), failure_count = 0
                WHERE id = %s::UUID
            """, (delivery["webhook_id"],), tenant_id=delivery["tenant_id"], fetch_results=False)
        else:
            _db_execute_rows("""
                UPDATE memory_service.webhooks 
                SET failure_count = failure_count + 1
                WHERE id = %s::UUID
            """, (delivery["webhook_id"],), tenant_id=delivery["tenant_id"], fetch_results=False)
    except Exception as e:
        logger.error(f"Failed to log webhook delivery: {e}")
    
    # Retry on failure
    if not success and retry < MAX_RETRIES:
        time.sleep(2 ** retry)  # Exponential backoff: 1s, 2s, 4s
        _deliver_webhook(delivery, retry + 1)
