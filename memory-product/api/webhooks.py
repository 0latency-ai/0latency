"""
CP8 P5.4 — Webhook Endpoint Handlers

Provides CRUD endpoints for managing tenant webhooks:
- POST /webhooks - create webhook (Scale/Enterprise only)
- GET /webhooks - list webhooks
- PATCH /webhooks/{id} - update webhook
- POST /webhooks/{id}/rotate-secret - rotate secret (Enterprise only)
- DELETE /webhooks/{id} - soft delete webhook
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from api.webhook_emission import generate_webhook_secret
from storage_multitenant import get_tenant_by_api_key, set_tenant_context, _db_execute_rows

logger = logging.getLogger(__name__)

# Create router for webhook endpoints
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=2048)
    event_types: List[str] = Field(default=["synthesis.replaced"])


class WebhookUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=2048)
    enabled: Optional[bool] = None
    event_types: Optional[List[str]] = None


async def _get_tenant_from_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> dict:
    """Extract and validate API key, return tenant."""
    if not x_api_key:
        raise HTTPException(401, detail="Missing X-API-Key header")

    if not x_api_key.startswith("zl_live_") or len(x_api_key) != 40:
        raise HTTPException(401, detail="Invalid API key format")

    api_key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    tenant = get_tenant_by_api_key(api_key_hash)

    if not tenant:
        raise HTTPException(401, detail="Invalid API key")

    if not tenant["active"]:
        raise HTTPException(401, detail="Account suspended")

    set_tenant_context(tenant["id"])
    return tenant


def _require_tier(tenant: dict, allowed_tiers: List[str], feature_name: str):
    """Helper to enforce tier gates."""
    tenant_tier = tenant.get("plan", "free")
    if tenant_tier not in allowed_tiers:
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"{feature_name}_requires_higher_tier",
                "tenant_tier": tenant_tier,
                "required_tiers": allowed_tiers
            }
        )


@router.post("")
async def create_webhook(
    req: WebhookCreateRequest,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Create a new webhook for the tenant.

    Tier gates:
    - Free/Pro: blocked (403)
    - Scale: max 1 active webhook
    - Enterprise: max 10 active webhooks

    Returns the webhook with secret (returned ONCE only at creation).
    """
    tenant = await _get_tenant_from_api_key(x_api_key)

    # Tier gate: Scale or Enterprise only
    _require_tier(tenant, ["scale", "enterprise"], "webhooks")

    tenant_id = tenant["id"]
    tenant_tier = tenant.get("plan", "free")

    # Validate URL starts with https://
    if not req.url.lower().startswith("https://"):
        raise HTTPException(
            status_code=422,
            detail="Webhook URL must use HTTPS"
        )

    # Check tier-specific webhook count limits
    count_rows = _db_execute_rows(
        """
        SELECT COUNT(*) as count
        FROM memory_service.tenant_webhooks
        WHERE tenant_id = %s AND deleted_at IS NULL
        """,
        (tenant_id,),
        tenant_id=tenant_id
    )

    current_count = count_rows[0][0] if count_rows else 0

    if tenant_tier == "scale" and current_count >= 1:
        raise HTTPException(
            status_code=409,
            detail="Scale tier limited to 1 active webhook"
        )
    elif tenant_tier == "enterprise" and current_count >= 10:
        raise HTTPException(
            status_code=409,
            detail="Enterprise tier limited to 10 active webhooks"
        )

    # Generate secret
    secret = generate_webhook_secret()

    # Validate event types
    valid_event_types = {"synthesis.replaced"}
    filtered_event_types = [e for e in req.event_types if e in valid_event_types]
    if not filtered_event_types:
        raise HTTPException(
            status_code=422,
            detail=f"No valid event types. Supported: {list(valid_event_types)}"
        )

    # Insert webhook
    rows = _db_execute_rows(
        """
        INSERT INTO memory_service.tenant_webhooks
        (tenant_id, name, url, secret, event_types, enabled)
        VALUES (%s, %s, %s, %s, %s, true)
        RETURNING id, created_at
        """,
        (tenant_id, req.name, req.url, secret, filtered_event_types),
        tenant_id=tenant_id
    )

    if not rows:
        raise HTTPException(500, detail="Failed to create webhook")

    webhook_id, created_at = rows[0]

    # Write audit event
    from synthesis.writer import _write_audit_event
    _write_audit_event(
        tenant_id=tenant_id,
        target_memory_id=None,
        event_type="webhook_created",
        actor="api",
        event_payload=json.dumps({
            "webhook_id": str(webhook_id),
            "url": req.url,
            "event_types": filtered_event_types
        })
    )

    logger.info(f"Created webhook {webhook_id} for tenant {tenant_id}")

    return {
        "id": str(webhook_id),
        "name": req.name,
        "url": req.url,
        "secret": secret,  # Returned ONCE only
        "event_types": filtered_event_types,
        "enabled": True,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
    }


@router.get("")
async def list_webhooks(x_api_key: str = Header(None, alias="X-API-Key")):
    """
    List all active webhooks for the tenant.

    Filters out soft-deleted webhooks (deleted_at IS NOT NULL).
    Does NOT return the secret field.
    """
    tenant = await _get_tenant_from_api_key(x_api_key)

    # Tier gate: Scale or Enterprise only
    _require_tier(tenant, ["scale", "enterprise"], "webhooks")

    tenant_id = tenant["id"]

    rows = _db_execute_rows(
        """
        SELECT id, name, url, event_types, enabled, created_at, updated_at,
               last_success_at, last_failure_at, consecutive_failures
        FROM memory_service.tenant_webhooks
        WHERE tenant_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC
        """,
        (tenant_id,),
        tenant_id=tenant_id
    )

    webhooks = []
    for row in rows:
        (webhook_id, name, url, event_types, enabled, created_at, updated_at,
         last_success_at, last_failure_at, consecutive_failures) = row

        webhooks.append({
            "id": str(webhook_id),
            "name": name,
            "url": url,
            "event_types": event_types,
            "enabled": enabled,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
            "last_success_at": last_success_at.isoformat() if last_success_at and hasattr(last_success_at, "isoformat") else (str(last_success_at) if last_success_at else None),
            "last_failure_at": last_failure_at.isoformat() if last_failure_at and hasattr(last_failure_at, "isoformat") else (str(last_failure_at) if last_failure_at else None),
            "consecutive_failures": consecutive_failures
        })

    return {"webhooks": webhooks}


@router.patch("/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    req: WebhookUpdateRequest,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Update a webhook's mutable fields.

    Mutable: name, url, enabled, event_types
    Immutable: secret (use rotate-secret endpoint)
    """
    tenant = await _get_tenant_from_api_key(x_api_key)

    # Tier gate: Scale or Enterprise only
    _require_tier(tenant, ["scale", "enterprise"], "webhooks")

    tenant_id = tenant["id"]

    # Build update query dynamically based on provided fields
    updates = []
    params = []

    if req.name is not None:
        updates.append("name = %s")
        params.append(req.name)

    if req.url is not None:
        if not req.url.lower().startswith("https://"):
            raise HTTPException(422, detail="Webhook URL must use HTTPS")
        updates.append("url = %s")
        params.append(req.url)

    if req.enabled is not None:
        updates.append("enabled = %s")
        params.append(req.enabled)

    if req.event_types is not None:
        valid_event_types = {"synthesis.replaced"}
        filtered = [e for e in req.event_types if e in valid_event_types]
        if not filtered:
            raise HTTPException(422, detail="No valid event types")
        updates.append("event_types = %s")
        params.append(filtered)

    if not updates:
        raise HTTPException(400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    params.extend([webhook_id, tenant_id])

    # Update webhook
    rows = _db_execute_rows(
        f"""
        UPDATE memory_service.tenant_webhooks
        SET {', '.join(updates)}
        WHERE id = %s::uuid AND tenant_id = %s AND deleted_at IS NULL
        RETURNING id
        """,
        tuple(params),
        tenant_id=tenant_id
    )

    if not rows:
        raise HTTPException(404, detail="Webhook not found")

    # Write audit event
    from synthesis.writer import _write_audit_event
    _write_audit_event(
        tenant_id=tenant_id,
        target_memory_id=None,
        event_type="webhook_updated",
        actor="api",
        event_payload=json.dumps({
            "webhook_id": webhook_id,
            "fields_updated": [k for k in req.dict(exclude_unset=True).keys()]
        })
    )

    logger.info(f"Updated webhook {webhook_id} for tenant {tenant_id}")

    return {"updated": webhook_id}


@router.post("/{webhook_id}/rotate-secret")
async def rotate_webhook_secret(
    webhook_id: str,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Rotate the webhook secret (Enterprise only).

    Generates a new 32-byte secret, returns it ONCE, persists it.
    Old secret is immediately invalidated.
    """
    tenant = await _get_tenant_from_api_key(x_api_key)

    # Tier gate: Enterprise only
    _require_tier(tenant, ["enterprise"], "webhook_secret_rotation")

    tenant_id = tenant["id"]

    # Generate new secret
    new_secret = generate_webhook_secret()

    # Update webhook
    rows = _db_execute_rows(
        """
        UPDATE memory_service.tenant_webhooks
        SET secret = %s, updated_at = NOW()
        WHERE id = %s::uuid AND tenant_id = %s AND deleted_at IS NULL
        RETURNING id
        """,
        (new_secret, webhook_id, tenant_id),
        tenant_id=tenant_id
    )

    if not rows:
        raise HTTPException(404, detail="Webhook not found")

    # Write audit event
    from synthesis.writer import _write_audit_event
    _write_audit_event(
        tenant_id=tenant_id,
        target_memory_id=None,
        event_type="webhook_updated",
        actor="api",
        event_payload=json.dumps({
            "webhook_id": webhook_id,
            "action": "secret_rotated"
        })
    )

    logger.info(f"Rotated secret for webhook {webhook_id} (tenant {tenant_id})")

    return {
        "webhook_id": webhook_id,
        "secret": new_secret  # Returned ONCE only
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Soft delete a webhook.

    Sets deleted_at = NOW(). Row stays in DB forever.
    In-flight deliveries are NOT cancelled.
    """
    tenant = await _get_tenant_from_api_key(x_api_key)

    # Tier gate: Scale or Enterprise only
    _require_tier(tenant, ["scale", "enterprise"], "webhooks")

    tenant_id = tenant["id"]

    # Soft delete
    rows = _db_execute_rows(
        """
        UPDATE memory_service.tenant_webhooks
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE id = %s::uuid AND tenant_id = %s AND deleted_at IS NULL
        RETURNING id
        """,
        (webhook_id, tenant_id),
        tenant_id=tenant_id
    )

    if not rows:
        raise HTTPException(404, detail="Webhook not found")

    # Write audit event
    from synthesis.writer import _write_audit_event
    _write_audit_event(
        tenant_id=tenant_id,
        target_memory_id=None,
        event_type="webhook_deleted",
        actor="api",
        event_payload=json.dumps({
            "webhook_id": webhook_id
        })
    )

    logger.info(f"Soft deleted webhook {webhook_id} for tenant {tenant_id}")

    return {"deleted": webhook_id}
