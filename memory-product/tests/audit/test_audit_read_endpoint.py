"""HTTP-level integration tests for GET /audit/events endpoint.

Tests the Enterprise-tier-gated audit log read endpoint using FastAPI TestClient.
Requires DATABASE_URL env var (tests are skipped otherwise).
"""

import sys
import os

# Add parent directory to path for api.main import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import base64
from uuid import uuid4
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
import pytest

# Try to import FastAPI TestClient - if it fails, skip endpoint tests
try:
    from fastapi.testclient import TestClient
    from api.main import app
    FASTAPI_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    FASTAPI_AVAILABLE = False
    SKIP_REASON = f"FastAPI or api.main import failed: {e}"


# ============================================================
# Test fixtures and helpers
# ============================================================

@pytest.fixture(scope="module")
def db_conn():
    """Get database connection from environment."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; skipping DB integration tests")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    yield conn
    conn.close()


def create_tenant(db_conn, plan="free"):
    """Create a test tenant with specified plan."""
    tenant_id = str(uuid4())
    api_key = f"zl_live_{uuid4().hex[:24]}"
    
    import hashlib
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    db_conn.rollback()

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.tenants (id, name, api_key_hash, plan, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (tenant_id, f"test-audit-{plan}-{tenant_id[:8]}", api_key_hash, plan),
        )
    db_conn.commit()

    return {"id": tenant_id, "api_key": api_key, "plan": plan}


def cleanup_tenant(db_conn, tenant_id):
    """Delete a test tenant."""
    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM memory_service.tenants WHERE id = %s", (tenant_id,))
    db_conn.commit()


def insert_audit_event(db_conn, tenant_id, event_type, **kwargs):
    """Insert a test audit event."""
    event_id = str(uuid4())
    
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.synthesis_audit_events (
                id, tenant_id, target_memory_id, event_type, actor, occurred_at, event_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                event_id,
                tenant_id,
                kwargs.get('target_memory_id'),
                event_type,
                kwargs.get('actor', 'system'),
                kwargs.get('occurred_at', datetime.now(timezone.utc)),
                json.dumps(kwargs.get('event_payload', {}))
            )
        )
    db_conn.commit()
    return event_id


# ============================================================
# Tests
# ============================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_free_tier_blocked(db_conn):
    """Free tier tenants get 403."""
    tenant = create_tenant(db_conn, plan="free")
    client = TestClient(app)
    
    try:
        response = client.get("/audit/events", headers={"X-API-Key": tenant["api_key"]})
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "audit_read_requires_enterprise"
        assert data["detail"]["tenant_tier"] == "free"
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_pro_tier_blocked(db_conn):
    """Pro tier tenants get 403."""
    tenant = create_tenant(db_conn, plan="pro")
    client = TestClient(app)
    
    try:
        response = client.get("/audit/events", headers={"X-API-Key": tenant["api_key"]})
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "audit_read_requires_enterprise"
        assert data["detail"]["tenant_tier"] == "pro"
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_scale_tier_blocked(db_conn):
    """Scale tier tenants get 403."""
    tenant = create_tenant(db_conn, plan="scale")
    client = TestClient(app)
    
    try:
        response = client.get("/audit/events", headers={"X-API-Key": tenant["api_key"]})
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "audit_read_requires_enterprise"
        assert data["detail"]["tenant_tier"] == "scale"
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_enterprise_tier_allowed(db_conn):
    """Enterprise tier tenants get 200."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Insert a test event
        insert_audit_event(db_conn, tenant["id"], "synthesis_written")
        
        response = client.get("/audit/events", headers={"X-API-Key": tenant["api_key"]})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "returned" in data
        assert "has_more" in data
        assert data["returned"] >= 1  # At least the event we inserted (plus self-audit)
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_filter_single_event_type(db_conn):
    """Filter by single event_type returns only matching rows."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Insert multiple event types
        insert_audit_event(db_conn, tenant["id"], "synthesis_written")
        insert_audit_event(db_conn, tenant["id"], "redacted")
        insert_audit_event(db_conn, tenant["id"], "synthesis_written")
        
        response = client.get(
            "/audit/events?event_type=synthesis_written",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned events should be synthesis_written (or read from self-audit)
        for event in data["events"]:
            assert event["event_type"] in ["synthesis_written", "read"]
        
        # Should have at least the 2 synthesis_written events
        synthesis_written_count = sum(1 for e in data["events"] if e["event_type"] == "synthesis_written")
        assert synthesis_written_count == 2
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_filter_multiple_event_types_union(db_conn):
    """Filter by multiple event_types returns union."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Insert various event types
        insert_audit_event(db_conn, tenant["id"], "synthesis_written")
        insert_audit_event(db_conn, tenant["id"], "redacted")
        insert_audit_event(db_conn, tenant["id"], "resynthesized")
        insert_audit_event(db_conn, tenant["id"], "state_transition")
        
        response = client.get(
            "/audit/events?event_type=redacted&event_type=resynthesized",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Filter out self-audit events
        non_read_events = [e for e in data["events"] if e["event_type"] != "read"]
        
        # All non-read events should be either redacted or resynthesized
        for event in non_read_events:
            assert event["event_type"] in ["redacted", "resynthesized"]
        
        # Should have exactly 2 matching events
        assert len(non_read_events) == 2
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_filter_target_memory_id(db_conn):
    """Filter by target_memory_id returns only matching rows."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        target_id = str(uuid4())
        other_id = str(uuid4())
        
        # Insert events with different target_memory_ids
        insert_audit_event(db_conn, tenant["id"], "synthesis_written", target_memory_id=target_id)
        insert_audit_event(db_conn, tenant["id"], "redacted", target_memory_id=other_id)
        insert_audit_event(db_conn, tenant["id"], "synthesis_written", target_memory_id=target_id)
        
        response = client.get(
            f"/audit/events?target_memory_id={target_id}",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Filter out self-audit events (which have target_memory_id=null)
        non_read_events = [e for e in data["events"] if e["event_type"] != "read"]
        
        # All events should have the target_id
        for event in non_read_events:
            assert event["target_memory_id"] == target_id
        
        # Should have exactly 2 matching events
        assert len(non_read_events) == 2
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_filter_actor(db_conn):
    """Filter by actor returns only matching rows."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Insert events with different actors
        insert_audit_event(db_conn, tenant["id"], "synthesis_written", actor="user-justin")
        insert_audit_event(db_conn, tenant["id"], "redacted", actor="system")
        insert_audit_event(db_conn, tenant["id"], "synthesis_written", actor="user-justin")
        
        response = client.get(
            "/audit/events?actor=user-justin",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Filter out self-audit events
        non_read_events = [e for e in data["events"] if e["event_type"] != "read"]
        
        # All events should have actor=user-justin
        for event in non_read_events:
            assert event["actor"] == "user-justin"
        
        # Should have exactly 2 matching events
        assert len(non_read_events) == 2
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_filter_since_until_window(db_conn):
    """Filter by since/until returns only rows in time window."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=2)
        future = now + timedelta(hours=2)
        
        # Insert events at different times
        insert_audit_event(db_conn, tenant["id"], "synthesis_written", occurred_at=past)
        insert_audit_event(db_conn, tenant["id"], "redacted", occurred_at=now)
        insert_audit_event(db_conn, tenant["id"], "synthesis_written", occurred_at=future)
        
        # Query for events in window [past+30min, future-30min]
        since = (past + timedelta(minutes=30)).isoformat()
        until = (future - timedelta(minutes=30)).isoformat()
        
        response = client.get(
            f"/audit/events?since={since}&until={until}",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Filter out self-audit events
        non_read_events = [e for e in data["events"] if e["event_type"] != "read"]
        
        # Should only have the 'now' event
        assert len(non_read_events) == 1
        assert non_read_events[0]["event_type"] == "redacted"
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_pagination_complete_no_overlap(db_conn):
    """Insert 150 events, page through with limit=50, verify all 150 returned exactly once."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Insert 150 events
        event_ids = set()
        for i in range(150):
            event_id = insert_audit_event(db_conn, tenant["id"], "synthesis_written")
            event_ids.add(event_id)
        
        # Paginate through all events
        all_returned_ids = set()
        cursor = None
        page_count = 0
        
        while True:
            url = "/audit/events?limit=50&event_type=synthesis_written"
            if cursor:
                url += f"&cursor={cursor}"
            
            response = client.get(url, headers={"X-API-Key": tenant["api_key"]})
            assert response.status_code == 200
            data = response.json()
            
            # Collect IDs from this page
            for event in data["events"]:
                all_returned_ids.add(event["id"])
            
            page_count += 1
            
            if not data["has_more"]:
                break
            
            cursor = data["next_cursor"]
            assert cursor is not None
            
            # Safety: prevent infinite loop
            assert page_count <= 10, "Too many pages, possible infinite loop"
        
        # Verify all 150 events were returned exactly once
        assert len(all_returned_ids) == 150
        assert all_returned_ids == event_ids
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_limit_clamped_to_500(db_conn):
    """Request limit=10000 returns at most 500."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Insert 600 events
        for i in range(600):
            insert_audit_event(db_conn, tenant["id"], "synthesis_written")
        
        response = client.get(
            "/audit/events?limit=10000&event_type=synthesis_written",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return at most 500 (plus potentially 1 self-audit event)
        assert data["returned"] <= 501
        # But should have more available
        assert data["has_more"] == True
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_invalid_cursor_returns_400(db_conn):
    """Invalid cursor returns 400."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        response = client.get(
            "/audit/events?cursor=invalid_base64!!!",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_cursor"
    finally:
        cleanup_tenant(db_conn, tenant["id"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_self_audit_event_written(db_conn):
    """Enterprise call writes a 'read' event with correct payload shape."""
    tenant = create_tenant(db_conn, plan="enterprise")
    client = TestClient(app)
    
    try:
        # Make a query with filters
        response = client.get(
            "/audit/events?event_type=synthesis_written&actor=system&limit=10",
            headers={"X-API-Key": tenant["api_key"]}
        )
        assert response.status_code == 200
        
        # Query the audit table directly for the 'read' event
        with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT event_type, actor, event_payload
                FROM memory_service.synthesis_audit_events
                WHERE tenant_id = %s AND event_type = 'read'
                ORDER BY occurred_at DESC
                LIMIT 1
                """,
                (tenant["id"],)
            )
            row = cur.fetchone()
        
        assert row is not None
        assert row["event_type"] == "read"
        assert row["actor"] == "system"
        
        # Verify payload shape
        payload = row["event_payload"]
        assert "filters" in payload
        assert "returned" in payload
        assert "endpoint" in payload
        assert payload["endpoint"] == "GET /audit/events"
        assert payload["filters"]["limit"] == 10
    finally:
        cleanup_tenant(db_conn, tenant["id"])
