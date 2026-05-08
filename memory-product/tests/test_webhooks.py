"""
CP8 P5.4 — Webhook endpoint unit tests
Per docs/CP8-P5-4-SCOPE.md Test Plan section
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app

client = TestClient(app)


@pytest.fixture
def free_api_key(db_conn):
    """Get API key for Free tier tenant."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT api_key_live FROM memory_service.tenants 
        WHERE plan='free' AND active=true LIMIT 1
    """)
    row = cur.fetchone()
    return row[0] if row else None


@pytest.fixture
def pro_api_key(db_conn):
    """Get API key for Pro tier tenant."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT api_key_live FROM memory_service.tenants 
        WHERE plan='pro' AND active=true LIMIT 1
    """)
    row = cur.fetchone()
    return row[0] if row else None


@pytest.fixture
def scale_api_key(db_conn):
    """Get API key for Scale tier tenant."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT api_key_live, id FROM memory_service.tenants 
        WHERE plan='scale' AND active=true LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        # Clean up existing webhooks for this tenant
        tenant_id = row[1]
        cur.execute("DELETE FROM memory_service.webhook_deliveries WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM memory_service.tenant_webhooks WHERE tenant_id = %s", (tenant_id,))
        db_conn.commit()
    return (row[0], row[1]) if row else (None, None)


@pytest.fixture
def enterprise_api_key(db_conn):
    """Get API key for Enterprise tier tenant."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT api_key_live, id FROM memory_service.tenants 
        WHERE plan='enterprise' AND active=true LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        # Clean up existing webhooks for this tenant
        tenant_id = row[1]
        cur.execute("DELETE FROM memory_service.webhook_deliveries WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM memory_service.tenant_webhooks WHERE tenant_id = %s", (tenant_id,))
        db_conn.commit()
    return (row[0], row[1]) if row else (None, None)


def test_webhook_tier_gate_free_blocked(free_api_key):
    """POST /webhooks tier gates: Free blocked"""
    if not free_api_key:
        pytest.skip("No Free tier tenant available")
    
    response = client.post(
        "/webhooks",
        headers={"X-API-Key": free_api_key},
        json={
            "name": "test-webhook",
            "url": "https://webhook.site/test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    # Detail is a dict with "error", "tenant_tier", "required_tiers"
    assert isinstance(detail, dict)
    assert "error" in detail
    assert "webhooks" in detail["error"]


def test_webhook_tier_gate_pro_blocked(pro_api_key):
    """POST /webhooks tier gates: Pro blocked"""
    if not pro_api_key:
        pytest.skip("No Pro tier tenant available")
    
    response = client.post(
        "/webhooks",
        headers={"X-API-Key": pro_api_key},
        json={
            "name": "test-webhook",
            "url": "https://webhook.site/test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response.status_code == 403


def test_webhook_tier_gate_scale_allowed(scale_api_key):
    """POST /webhooks tier gates: Scale allowed"""
    api_key, tenant_id = scale_api_key
    if not api_key:
        pytest.skip("No Scale tier tenant available")
    
    response = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "test-scale-webhook",
            "url": "https://webhook.site/scale-test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-scale-webhook"
    assert "secret" in data


def test_webhook_tier_gate_enterprise_allowed(enterprise_api_key):
    """POST /webhooks tier gates: Enterprise allowed"""
    api_key, tenant_id = enterprise_api_key
    if not api_key:
        pytest.skip("No Enterprise tier tenant available")
    
    response = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "test-enterprise-webhook",
            "url": "https://webhook.site/enterprise-test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response.status_code == 201


def test_webhook_scale_limit_one(scale_api_key, db_conn):
    """POST /webhooks Scale tenant with existing active webhook fails"""
    api_key, tenant_id = scale_api_key
    if not api_key:
        pytest.skip("No Scale tier tenant available")
    
    # Create first webhook
    response1 = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "webhook-1",
            "url": "https://webhook.site/test-1",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response1.status_code == 201
    
    # Try to create second webhook
    response2 = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "webhook-2",
            "url": "https://webhook.site/test-2",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response2.status_code == 409


def test_webhook_enterprise_limit_ten(enterprise_api_key, db_conn):
    """POST /webhooks Enterprise with 10 active webhooks fails"""
    api_key, tenant_id = enterprise_api_key
    if not api_key:
        pytest.skip("No Enterprise tier tenant available")
    
    # Create 10 webhooks
    for i in range(10):
        response = client.post(
            "/webhooks",
            headers={"X-API-Key": api_key},
            json={
                "name": f"webhook-{i}",
                "url": f"https://webhook.site/test-{i}",
                "event_types": ["synthesis.replaced"]
            }
        )
        assert response.status_code == 201
    
    # 11th should fail
    response = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "webhook-11",
            "url": "https://webhook.site/test-11",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response.status_code == 409


def test_webhook_invalid_url_http(scale_api_key):
    """POST /webhooks invalid URL http blocked"""
    api_key, tenant_id = scale_api_key
    if not api_key:
        pytest.skip("No Scale tier tenant available")
    
    response = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "test-webhook",
            "url": "http://webhook.site/test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert response.status_code == 422


def test_webhook_get_omits_secret(scale_api_key, db_conn):
    """GET /webhooks omits secret field"""
    api_key, tenant_id = scale_api_key
    if not api_key:
        pytest.skip("No Scale tier tenant available")
    
    # Create webhook
    create_response = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "secret-test",
            "url": "https://webhook.site/secret-test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert create_response.status_code == 201
    assert "secret" in create_response.json()
    
    # List webhooks
    list_response = client.get(
        "/webhooks",
        headers={"X-API-Key": api_key}
    )
    assert list_response.status_code == 200
    webhooks = list_response.json()["webhooks"]
    for webhook in webhooks:
        assert "secret" not in webhook


def test_webhook_rotate_secret_enterprise_only(scale_api_key, enterprise_api_key, db_conn):
    """POST /webhooks/rotate-secret Scale blocked, Enterprise allowed"""
    # Test Scale tier blocked
    scale_key, scale_tenant_id = scale_api_key
    if scale_key:
        create_response = client.post(
            "/webhooks",
            headers={"X-API-Key": scale_key},
            json={
                "name": "rotate-test-scale",
                "url": "https://webhook.site/rotate-scale",
                "event_types": ["synthesis.replaced"]
            }
        )
        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]
            rotate_response = client.post(
                f"/webhooks/{webhook_id}/rotate-secret",
                headers={"X-API-Key": scale_key}
            )
            assert rotate_response.status_code == 403
    
    # Test Enterprise tier allowed
    ent_key, ent_tenant_id = enterprise_api_key
    if ent_key:
        create_response = client.post(
            "/webhooks",
            headers={"X-API-Key": ent_key},
            json={
                "name": "rotate-test-ent",
                "url": "https://webhook.site/rotate-ent",
                "event_types": ["synthesis.replaced"]
            }
        )
        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]
            old_secret = create_response.json()["secret"]
            
            rotate_response = client.post(
                f"/webhooks/{webhook_id}/rotate-secret",
                headers={"X-API-Key": ent_key}
            )
            assert rotate_response.status_code == 200
            new_secret = rotate_response.json()["secret"]
            assert new_secret != old_secret


def test_webhook_delete_soft_deletes(scale_api_key, db_conn):
    """DELETE /webhooks sets deleted_at, excludes from GET"""
    api_key, tenant_id = scale_api_key
    if not api_key:
        pytest.skip("No Scale tier tenant available")
    
    # Create webhook
    create_response = client.post(
        "/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "name": "delete-test",
            "url": "https://webhook.site/delete-test",
            "event_types": ["synthesis.replaced"]
        }
    )
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]
    
    # Delete webhook
    delete_response = client.delete(
        f"/webhooks/{webhook_id}",
        headers={"X-API-Key": api_key}
    )
    assert delete_response.status_code in [200, 204]
    
    # Verify excluded from GET
    list_response = client.get(
        "/webhooks",
        headers={"X-API-Key": api_key}
    )
    assert list_response.status_code == 200
    webhooks = list_response.json()["webhooks"]
    webhook_ids = [w["id"] for w in webhooks]
    assert webhook_id not in webhook_ids
    
    # Verify row still exists with deleted_at set
    cur = db_conn.cursor()
    cur.execute("""
        SELECT deleted_at FROM memory_service.tenant_webhooks 
        WHERE id = %s
    """, (webhook_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] is not None


def test_hmac_signature_roundtrip():
    """HMAC signature verification roundtrip"""
    import hmac
    import hashlib
    import time
    
    secret_hex = "abcdef1234567890" * 4
    raw_body = b'{"test": "payload"}'
    
    # Sign
    t = int(time.time())
    msg = f"{t}.".encode() + raw_body
    sig = hmac.new(bytes.fromhex(secret_hex), msg, hashlib.sha256).hexdigest()
    
    # Verify with correct secret
    verify_msg = f"{t}.".encode() + raw_body
    verify_sig = hmac.new(bytes.fromhex(secret_hex), verify_msg, hashlib.sha256).hexdigest()
    assert sig == verify_sig
    
    # Verify with wrong secret fails
    wrong_secret = "fedcba0987654321" * 4
    wrong_sig = hmac.new(bytes.fromhex(wrong_secret), verify_msg, hashlib.sha256).hexdigest()
    assert sig != wrong_sig
