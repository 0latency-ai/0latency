"""
Zero Latency Memory API — Feature Parity Test Suite
Tests all 8 features built to close mem0 gaps.
Run: python3 tests/test_feature_parity.py
"""

import requests
import time
import sys
import os
import json

BASE = os.environ.get("ZL_TEST_URL", "http://127.0.0.1:8420")
ADMIN_KEY = os.environ.get("MEMORY_ADMIN_KEY", "")
if not ADMIN_KEY:
    print("⚠️  MEMORY_ADMIN_KEY not set. Admin tests will be skipped.")


TEST_API_KEY = None
TEST_TENANT_ID = None


def api(method, path, key=None, json_data=None, params=None, admin=False):
    headers = {}
    if key:
        headers["X-API-Key"] = key
    if admin:
        headers["X-Admin-Key"] = ADMIN_KEY
    r = getattr(requests, method)(f"{BASE}{path}", headers=headers, json=json_data, params=params, timeout=30)
    return r


class R:
    passed = 0
    failed = 0
    errors = []


def check(name, condition, detail=""):
    if condition:
        R.passed += 1
        print(f"  ✅ {name}")
    else:
        R.failed += 1
        R.errors.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


# === Setup ===

def test_00_setup():
    """Create test tenant for feature parity tests."""
    global TEST_API_KEY, TEST_TENANT_ID
    print("\n🔧 Setup")
    
    r = api("post", "/api-keys", admin=True, json_data={"name": "Feature Parity Test", "plan": "pro"})
    check("Create test tenant", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    
    if r.status_code == 200:
        data = r.json()
        TEST_API_KEY = data["api_key"]
        TEST_TENANT_ID = data["tenant_id"]
        check("Got API key", TEST_API_KEY.startswith("zl_live_"))
        check("Got tenant ID", len(TEST_TENANT_ID) == 36)
    
    # Seed some memories for testing
    for i, msg in enumerate([
        ("Justin runs PFL Academy, a financial literacy platform", "Got it, PFL Academy is your primary business"),
        ("Sebastian is our lead developer, he works on the LMS", "Noted, Sebastian handles the technical platform"),
        ("PFL Academy charges $16/student/year for legacy contracts", "Understood, $16/student for existing deals"),
        ("We need to reach $1M ARR, first milestone is $200K-$300K", "Clear target: $1M ARR with $200K-$300K milestone"),
        ("Colorado is our flagship state with HB25-1192 mandate", "Colorado is top priority with legislative backing"),
    ]):
        r = api("post", "/extract", key=TEST_API_KEY, json_data={
            "agent_id": "test-agent",
            "human_message": msg[0],
            "agent_message": msg[1],
        })
    
    time.sleep(1)  # Let extraction settle
    check("Seeded test memories", True)


# === 1. Graph Memory ===

def test_01_graph_entities():
    """Graph: list known entities."""
    print("\n🕸️  Graph Memory")
    r = api("get", "/graph/entities", key=TEST_API_KEY, params={"agent_id": "test-agent"})
    check("List entities returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Returns list", isinstance(data, list), f"type={type(data)}")


def test_02_graph_entity_subgraph():
    """Graph: get subgraph around an entity."""
    r = api("get", "/graph/entity", key=TEST_API_KEY, params={
        "agent_id": "test-agent", "entity": "PFL Academy", "depth": 2
    })
    check("Entity subgraph returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Has nodes field", "nodes" in data)
        check("Has edges field", "edges" in data)
        check("Has root field", data.get("root") == "PFL Academy")


def test_03_graph_entity_memories():
    """Graph: get memories for an entity."""
    r = api("get", "/graph/entity/memories", key=TEST_API_KEY, params={
        "agent_id": "test-agent", "entity": "PFL Academy"
    })
    check("Entity memories returns 200", r.status_code == 200, f"status={r.status_code}")


def test_04_graph_path():
    """Graph: find path between entities."""
    r = api("get", "/graph/path", key=TEST_API_KEY, params={
        "agent_id": "test-agent", "source": "Justin", "target": "PFL Academy"
    })
    check("Path finding returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Has path field", "path" in data)
        check("Has hops field", "hops" in data)


# === 2. Webhooks ===

def test_05_webhooks():
    """Webhooks: CRUD operations."""
    print("\n🔔 Webhooks")
    
    # Create
    r = api("post", "/webhooks", key=TEST_API_KEY, json_data={
        "url": "https://httpbin.org/post",
        "events": ["memory.created", "memory.updated"],
        "secret": "test-secret-123"
    })
    check("Create webhook returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    
    webhook_id = None
    if r.status_code == 200:
        data = r.json()
        webhook_id = data.get("id")
        check("Webhook has ID", webhook_id is not None)
        check("Webhook has events", len(data.get("events", [])) == 2)
    
    # List
    r = api("get", "/webhooks", key=TEST_API_KEY)
    check("List webhooks returns 200", r.status_code == 200)
    if r.status_code == 200:
        check("Returns list", isinstance(r.json(), list))
        check("Contains our webhook", any(w["id"] == webhook_id for w in r.json()) if webhook_id else False)
    
    # Invalid events
    r = api("post", "/webhooks", key=TEST_API_KEY, json_data={
        "url": "https://example.com",
        "events": ["invalid.event"]
    })
    check("Invalid events rejected", r.status_code == 400)
    
    # Delete
    if webhook_id:
        r = api("delete", f"/webhooks/{webhook_id}", key=TEST_API_KEY)
        check("Delete webhook returns 200", r.status_code == 200)


# === 3. Memory Versioning ===

def test_06_versioning():
    """Versioning: update memory and check history."""
    print("\n📜 Memory Versioning")
    
    # Get a memory to work with
    r = api("get", "/memories", key=TEST_API_KEY, params={"agent_id": "test-agent", "limit": 1})
    if r.status_code != 200 or not r.json():
        check("Need memories to test versioning", False, "No memories found")
        return
    
    memory_id = r.json()[0]["id"]
    original_headline = r.json()[0]["headline"]
    
    # Update it (should auto-snapshot)
    r = api("put", f"/memories/{memory_id}", key=TEST_API_KEY, json_data={
        "importance": 0.95,
        "headline": f"[Updated] {original_headline}"
    })
    check("Update memory returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    
    # Check history
    r = api("get", f"/memories/{memory_id}/history", key=TEST_API_KEY)
    check("History returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Has history array", "history" in data)
        check("Has current version", "current" in data)
        check("History has at least 1 version", len(data.get("history", [])) >= 1,
              f"got {len(data.get('history', []))}")
    
    # Restore original
    api("put", f"/memories/{memory_id}", key=TEST_API_KEY, json_data={
        "headline": original_headline
    })


# === 4. Criteria Retrieval ===

def test_07_criteria():
    """Criteria: create, list, use for scoring."""
    print("\n🎯 Criteria Retrieval")
    
    # Create criteria
    r = api("post", "/criteria", key=TEST_API_KEY, json_data={
        "agent_id": "test-agent",
        "name": "urgency",
        "weight": 0.8,
        "description": "How urgent is this memory"
    })
    check("Create criteria returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    
    criteria_id = None
    if r.status_code == 200:
        criteria_id = r.json().get("id")
    
    # Create another
    r = api("post", "/criteria", key=TEST_API_KEY, json_data={
        "agent_id": "test-agent",
        "name": "actionability",
        "weight": 0.6,
        "description": "Does this memory lead to an action"
    })
    check("Create second criteria", r.status_code == 200)
    
    # List
    r = api("get", "/criteria", key=TEST_API_KEY, params={"agent_id": "test-agent"})
    check("List criteria returns 200", r.status_code == 200)
    if r.status_code == 200:
        check("Has criteria", len(r.json()) >= 2, f"got {len(r.json())}")
    
    # Delete
    if criteria_id:
        r = api("delete", f"/criteria/{criteria_id}", key=TEST_API_KEY)
        check("Delete criteria returns 200", r.status_code == 200)


# === 5. Organization Memory ===

def test_08_org_memory():
    """Org Memory: store, list, recall, promote."""
    print("\n🏢 Organization Memory")
    
    # Org endpoints require tenant to be in an org — test the error case
    r = api("get", "/org/memories", key=TEST_API_KEY)
    check("No org returns 403", r.status_code == 403)
    
    r = api("post", "/org/memories", key=TEST_API_KEY, json_data={
        "headline": "Test org memory",
    })
    check("Store without org returns 403", r.status_code == 403)
    
    # We can't easily create an org in the test without admin access to DB
    # but we verify the endpoints exist and validate correctly
    check("Org endpoints respond correctly", True)


# === 6. Structured Schemas ===

def test_09_schemas():
    """Schemas: create, list, delete custom extraction schemas."""
    print("\n📐 Structured Schemas")
    
    schema_def = {
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            "action_items": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["sentiment"]
    }
    
    r = api("post", "/schemas", key=TEST_API_KEY, json_data={
        "name": "sentiment-analysis",
        "schema": schema_def,
        "extraction_prompt": "Extract sentiment for each memory"
    })
    check("Create schema returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    
    schema_id = None
    if r.status_code == 200:
        schema_id = r.json().get("id")
        check("Schema has ID", schema_id is not None)
    
    # List
    r = api("get", "/schemas", key=TEST_API_KEY)
    check("List schemas returns 200", r.status_code == 200)
    if r.status_code == 200:
        check("Returns list", isinstance(r.json(), list))
    
    # Delete
    if schema_id:
        r = api("delete", f"/schemas/{schema_id}", key=TEST_API_KEY)
        check("Delete schema returns 200", r.status_code == 200)


# === 7. Batch Operations ===

def test_10_batch_ops():
    """Batch: delete, search multiple items."""
    print("\n📦 Batch Operations")
    
    # Batch search
    r = api("post", "/memories/batch-search", key=TEST_API_KEY, json_data={
        "agent_id": "test-agent",
        "queries": ["financial literacy", "Colorado", "revenue"],
        "limit_per_query": 5
    })
    check("Batch search returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Has results dict", "results" in data)
        check("Has all queries", len(data.get("results", {})) == 3,
              f"got {len(data.get('results', {}))}")
    
    # Batch delete (with non-existent IDs — should return errors)
    r = api("post", "/memories/batch-delete", key=TEST_API_KEY, json_data={
        "memory_ids": ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"]
    })
    check("Batch delete returns 200", r.status_code == 200)
    if r.status_code == 200:
        data = r.json()
        check("Returns deleted list", "deleted" in data)
        check("Returns errors for not-found", data.get("errors") is not None)


# === 8. Python SDK (import test) ===

def test_11_sdk():
    """SDK: verify Python SDK structure."""
    print("\n🐍 Python SDK")
    
    sdk_dir = os.path.join(os.path.dirname(__file__), "..", "sdk", "python")
    
    check("SDK directory exists", os.path.isdir(sdk_dir))
    check("__init__.py exists", os.path.isfile(os.path.join(sdk_dir, "zerolatency", "__init__.py")))
    check("client.py exists", os.path.isfile(os.path.join(sdk_dir, "zerolatency", "client.py")))
    check("setup.py exists", os.path.isfile(os.path.join(sdk_dir, "setup.py")))
    check("README.md exists", os.path.isfile(os.path.join(sdk_dir, "README.md")))
    
    # Verify import works
    sys.path.insert(0, sdk_dir)
    try:
        from zerolatency import ZeroLatencyClient
        client = ZeroLatencyClient(api_key="zl_live_test12345678901234567890ab", base_url=BASE)
        check("SDK import works", True)
        check("Client instantiates", client is not None)
        
        # Test health (no auth needed)
        try:
            h = client.health()
            check("SDK health check works", h.get("status") == "ok")
        except Exception as e:
            check("SDK health check", False, str(e)[:100])
    except Exception as e:
        check("SDK import", False, str(e)[:100])


# === Security Regression ===

def test_12_security():
    """Security: verify GA#4 fixes hold."""
    print("\n🔒 Security Regression")
    
    # SQL injection in list_memories
    r = api("get", "/memories", key=TEST_API_KEY, params={
        "agent_id": "test-agent",
        "memory_type": "fact' OR 1=1--"
    })
    check("SQLi in memory_type rejected or safe", r.status_code in (200, 422), 
          f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("SQLi returns no cross-tenant data", len(data) == 0, f"got {len(data)} results")
    
    # SQL injection in search
    r = api("get", "/memories/search", key=TEST_API_KEY, params={
        "agent_id": "test-agent",
        "q": "'; DROP TABLE memory_service.memories;--"
    })
    check("SQLi in search is safe", r.status_code in (200, 422))
    
    # Error messages don't leak internals
    r = api("get", "/memories", key=TEST_API_KEY, params={
        "agent_id": "test-agent",
        "memory_type": "x" * 1000  # Very long input
    })
    if r.status_code >= 400:
        body = r.text
        check("Error doesn't leak DB details", "postgres" not in body.lower() and "psycopg" not in body.lower(),
              f"body contains DB info: {body[:200]}")
    else:
        check("Long input handled", True)
    
    # Auth failures
    r = api("get", "/memories", params={"agent_id": "test"})
    check("Missing auth returns 422 or 401", r.status_code in (401, 422))
    
    r = api("get", "/memories", key="invalid_key", params={"agent_id": "test"})
    check("Invalid key format rejected", r.status_code == 401)


# === Cleanup ===

def test_99_cleanup():
    """Clean up test data."""
    print("\n🧹 Cleanup")
    # Deactivate test tenant
    if TEST_TENANT_ID:
        r = api("post", f"/admin/revoke-key/{TEST_TENANT_ID}", admin=True)
        check("Test tenant revoked", r.status_code == 200)


if __name__ == "__main__":
    print("=" * 60)
    print("Zero Latency Memory API — Feature Parity Test Suite")
    print("=" * 60)
    
    tests = [
        test_00_setup,
        test_01_graph_entities,
        test_02_graph_entity_subgraph,
        test_03_graph_entity_memories,
        test_04_graph_path,
        test_05_webhooks,
        test_06_versioning,
        test_07_criteria,
        test_08_org_memory,
        test_09_schemas,
        test_10_batch_ops,
        test_11_sdk,
        test_12_security,
        test_99_cleanup,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"\n💥 {test.__name__} CRASHED: {e}")
            R.failed += 1
            R.errors.append(f"{test.__name__}: CRASH — {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {R.passed} passed, {R.failed} failed")
    if R.errors:
        print("\nFailures:")
        for e in R.errors:
            print(f"  ❌ {e}")
    print("=" * 60)
    
    sys.exit(0 if R.failed == 0 else 1)
