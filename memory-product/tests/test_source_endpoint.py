"""
Integration tests for GET /memories/{memory_id}/source endpoint.
Run against live service: pytest tests/test_source_endpoint.py -v --tb=short
"""

import os
import pytest
import requests

BASE = "http://localhost:8420"

# Fixtures from CP8 Phase 2 Task 9 scope doc, tenant 44c3080d-c196-407d-a606-4ea9f62ba0fc
RAW_TURN_ID = "9deed596-57f4-47fe-b788-1c640f9f178b"
ATOM_ID = "002e58b3-2e69-4a3d-9548-2a2a7fbc78dc"
TENANT_API_KEY = os.environ.get("ZEROLATENCY_API_KEY", "")


def _headers(key=None):
    k = key if key is not None else TENANT_API_KEY
    return {"X-API-Key": k}


@pytest.mark.integration
def test_raw_turn_returns_verbatim():
    """raw_turn memory returns source_type=verbatim with source_text populated."""
    r = requests.get(f"{BASE}/memories/{RAW_TURN_ID}/source", headers=_headers())
    assert r.status_code == 200, f"Unexpected status: {r.status_code} {r.text}"
    body = r.json()
    assert body["memory_id"] == RAW_TURN_ID
    assert body["memory_type"] == "raw_turn"
    assert body["source_type"] == "verbatim"
    assert "source_text" in body
    assert isinstance(body["source_text"], str) and len(body["source_text"]) > 0
    assert "track1" in body["source_text"], f"Expected track1 sentinel in: {body['source_text'][:100]}"
    assert "source_chain" not in body
    assert body["trace"]["depth"] == 0
    assert RAW_TURN_ID in body["trace"]["raw_turn_ids"]


@pytest.mark.integration
def test_atom_with_parent_returns_derived_chain():
    """Atom with parent_memory_ids returns source_type=derived with source_chain resolved."""
    r = requests.get(f"{BASE}/memories/{ATOM_ID}/source", headers=_headers())
    assert r.status_code == 200, f"Unexpected status: {r.status_code} {r.text}"
    body = r.json()
    assert body["memory_id"] == ATOM_ID
    assert body["source_type"] == "derived"
    assert "source_chain" in body
    assert len(body["source_chain"]) >= 1, f"source_chain is empty: {body}"
    assert body["source_chain"][0]["memory_type"] == "raw_turn"
    assert "source_text" in body["source_chain"][0]
    assert len(body["trace"]["raw_turn_ids"]) >= 1
    assert body["trace"]["depth"] >= 1


@pytest.mark.integration
def test_atom_with_no_parents_returns_empty_chain():
    """Atom with missing/empty parent_memory_ids returns derived with empty source_chain (legacy data)."""
    # Seed via /memories/seed — seed endpoint does not write parent_memory_ids, simulating legacy data
    seed_resp = requests.post(f"{BASE}/memories/seed", headers=_headers(), json={
        "agent_id": "test-source-endpoint",
        "facts": [{"text": "legacy atom with no parent chain", "memory_type": "fact", "importance": 0.1}],
    })
    assert seed_resp.status_code in (200, 201), f"Seed failed: {seed_resp.text}"
    seeded = seed_resp.json()
    mem_ids = seeded.get("memory_ids", [])
    assert len(mem_ids) >= 1, f"No memory_ids in response: {seeded}"
    mem_id = mem_ids[0]

    r = requests.get(f"{BASE}/memories/{mem_id}/source", headers=_headers())
    assert r.status_code == 200, f"Unexpected status: {r.status_code} {r.text}"
    body = r.json()
    assert body["source_type"] == "derived"
    assert body["source_chain"] == []
    assert body["trace"]["depth"] == 0
    assert body["trace"]["raw_turn_ids"] == []


@pytest.mark.integration
def test_404_on_nonexistent_uuid():
    """Non-existent UUID returns 404."""
    r = requests.get(
        f"{BASE}/memories/00000000-0000-0000-0000-000000000000/source",
        headers=_headers(),
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


@pytest.mark.integration
def test_422_on_malformed_uuid():
    """Malformed (non-UUID) memory_id returns 422 or 400."""
    r = requests.get(
        f"{BASE}/memories/not-a-uuid/source",
        headers=_headers(),
    )
    assert r.status_code in (422, 400), f"Expected 422/400, got {r.status_code}: {r.text}"


@pytest.mark.integration
def test_401_on_missing_api_key():
    """Missing X-API-Key returns 401, 403, or 422."""
    r = requests.get(f"{BASE}/memories/{RAW_TURN_ID}/source")
    assert r.status_code in (401, 403, 422), f"Expected 401/403/422, got {r.status_code}: {r.text}"


@pytest.mark.integration
def test_tenant_isolation_returns_404():
    """Fetching another tenant's memory returns 404, not the memory or a 403."""
    # Use the scale-tier key (synwdojae) which is a different tenant
    other_key = "zl_live_synwdojae2ois01oi01mmzdqh791hfek"
    r = requests.get(
        f"{BASE}/memories/{RAW_TURN_ID}/source",
        headers=_headers(key=other_key),
    )
    # Must be 404 (not found for this tenant) — never expose cross-tenant data
    assert r.status_code == 404, f"Expected 404 for cross-tenant, got {r.status_code}: {r.text}"
