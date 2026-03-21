"""
Zero Latency Memory API — Full Test Suite
Run: python3 -m pytest tests/test_api_full.py -v
Or:  python3 tests/test_api_full.py
"""

import requests
import time
import sys
import os
import hashlib

BASE = os.environ.get("ZL_TEST_URL", "http://127.0.0.1:8420")
ADMIN_KEY = os.environ.get("MEMORY_ADMIN_KEY", "")

# Will be set during test_01
TEST_API_KEY = None
TEST_TENANT_ID = None


def api(method, path, key=None, json=None, params=None, admin=False):
    headers = {}
    if key:
        headers["X-API-Key"] = key
    if admin and ADMIN_KEY:
        headers["X-Admin-Key"] = ADMIN_KEY
    r = getattr(requests, method)(f"{BASE}{path}", headers=headers, json=json, params=params, timeout=30)
    return r


class Results:
    passed = 0
    failed = 0
    errors = []


def check(name, condition, detail=""):
    if condition:
        Results.passed += 1
        print(f"  ✅ {name}")
    else:
        Results.failed += 1
        Results.errors.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


def test_01_health():
    """Health endpoint returns ok with DB stats."""
    print("\n🧪 Health")
    r = api("get", "/health")
    check("returns 200", r.status_code == 200)
    d = r.json()
    check("status is ok", d["status"] == "ok")
    check("version present", d["version"] == "0.1.0")
    check("memories_total is int", isinstance(d["memories_total"], int), f"got {d['memories_total']}")
    check("has X-Request-ID", "x-request-id" in r.headers)


def test_02_auth():
    """Authentication checks."""
    print("\n🧪 Auth")
    r = api("get", "/memories", params={"agent_id": "test"})
    check("no key → 422", r.status_code == 422)  # Missing header
    
    r = api("get", "/memories", key="bad_key", params={"agent_id": "test"})
    check("bad format → 401", r.status_code == 401)
    
    r = api("get", "/memories", key="zl_live_00000000000000000000000000000000", params={"agent_id": "test"})
    check("invalid key → 401", r.status_code == 401)


def test_03_create_tenant():
    """Create test tenant via admin endpoint."""
    global TEST_API_KEY, TEST_TENANT_ID
    print("\n🧪 Create Tenant")
    
    if not ADMIN_KEY:
        print("  ⚠️  Skipped (no MEMORY_ADMIN_KEY set)")
        return
    
    r = api("post", "/api-keys", admin=True, json={"name": "CI Test Tenant", "plan": "pro"})
    check("admin create → 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    
    if r.status_code == 200:
        d = r.json()
        TEST_API_KEY = d["api_key"]
        TEST_TENANT_ID = d["tenant_id"]
        check("key format correct", TEST_API_KEY.startswith("zl_live_") and len(TEST_API_KEY) == 40)
        check("plan is pro", d["plan"] == "pro")
        check("memory_limit is 50000", d["memory_limit"] == 50000)


def test_04_tenant_info():
    """Tenant info endpoint."""
    print("\n🧪 Tenant Info")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped (no test tenant)")
        return
    
    r = api("get", "/tenant-info", key=TEST_API_KEY)
    check("returns 200", r.status_code == 200)
    d = r.json()
    check("correct tenant id", d["id"] == TEST_TENANT_ID)
    check("correct plan", d["plan"] == "pro")


def test_05_extract():
    """Extract memories from conversation."""
    print("\n🧪 Extract")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r = api("post", "/extract", key=TEST_API_KEY, json={
        "agent_id": "ci_test",
        "human_message": "My name is Alice and I work at Google in Mountain View. I love sushi.",
        "agent_message": "Nice to meet you Alice! Google is a great company."
    })
    check("returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        check("memories_stored > 0", d["memories_stored"] > 0, f"got {d['memories_stored']}")
        check("memory_ids present", len(d["memory_ids"]) > 0)


def test_06_list_memories():
    """List memories."""
    print("\n🧪 List Memories")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # Small delay for extraction to complete
    time.sleep(1)
    
    r = api("get", "/memories", key=TEST_API_KEY, params={"agent_id": "ci_test", "limit": 10})
    check("returns 200", r.status_code == 200)
    memories = r.json()
    check("returns list", isinstance(memories, list))
    check("has memories", len(memories) > 0, f"got {len(memories)}")
    
    if memories:
        m = memories[0]
        check("has id", "id" in m)
        check("has headline", "headline" in m)
        check("has memory_type", "memory_type" in m)
        check("has importance", "importance" in m)


def test_07_recall():
    """Recall memories."""
    print("\n🧪 Recall")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r = api("post", "/recall", key=TEST_API_KEY, json={
        "agent_id": "ci_test",
        "conversation_context": "order lunch for the team",
        "budget_tokens": 1000
    })
    check("returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        check("has context_block", "context_block" in d)
        check("has memories_used", "memories_used" in d)
        check("has tokens_used", "tokens_used" in d)
        check("within budget", d["tokens_used"] <= 1000, f"used {d['tokens_used']}")


def test_08_recall_edge_cases():
    """Recall with edge case inputs."""
    print("\n🧪 Recall Edge Cases")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # Empty agent (no memories)
    r = api("post", "/recall", key=TEST_API_KEY, json={
        "agent_id": "nonexistent_agent_xyz",
        "conversation_context": "test",
        "budget_tokens": 500
    })
    check("empty agent → 200", r.status_code == 200)
    d = r.json()
    check("empty agent → 0 memories", d["memories_used"] == 0)
    
    # Minimum budget
    r = api("post", "/recall", key=TEST_API_KEY, json={
        "agent_id": "ci_test",
        "conversation_context": "test query",
        "budget_tokens": 500
    })
    check("min budget → 200", r.status_code == 200)


def test_09_sql_injection():
    """SQL injection attempts are neutralized."""
    print("\n🧪 SQL Injection Prevention")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # SQLi in memory_type filter
    r = api("get", "/memories", key=TEST_API_KEY, params={
        "agent_id": "test",
        "memory_type": "fact' OR 1=1--"
    })
    check("SQLi in memory_type → safe", r.status_code == 200)
    check("SQLi returns empty (not all data)", len(r.json()) == 0)
    
    # SQLi in agent_id
    r = api("get", "/memories", key=TEST_API_KEY, params={
        "agent_id": "'; DROP TABLE memories;--"
    })
    check("SQLi in agent_id → safe", r.status_code == 200)
    
    # SQLi in recall conversation_context
    r = api("post", "/recall", key=TEST_API_KEY, json={
        "agent_id": "ci_test",
        "conversation_context": "'; DROP TABLE memories;--",
        "budget_tokens": 500
    })
    check("SQLi in recall context → safe", r.status_code == 200)


def test_10_tenant_isolation():
    """Verify cross-tenant isolation."""
    print("\n🧪 Tenant Isolation")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # List memories — should only see CI test tenant's data
    r = api("get", "/memories", key=TEST_API_KEY, params={"agent_id": "thomas", "limit": 200})
    check("cross-tenant read → empty", len(r.json()) == 0,
          f"got {len(r.json())} memories (should be 0 — thomas belongs to different tenant)")


def test_11_usage():
    """Usage endpoint."""
    print("\n🧪 Usage")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r = api("get", "/usage", key=TEST_API_KEY, params={"days": 1})
    check("returns 200", r.status_code == 200)
    d = r.json()
    check("has tenant_id", d["tenant_id"] == TEST_TENANT_ID)
    check("has memories_stored", "memories_stored" in d)
    check("has memory_usage_pct", "memory_usage_pct" in d)
    check("has endpoints list", isinstance(d["endpoints"], list))


def test_12_key_rotation():
    """Key rotation lifecycle."""
    global TEST_API_KEY
    print("\n🧪 Key Rotation")
    if not TEST_API_KEY or not ADMIN_KEY:
        print("  ⚠️  Skipped")
        return
    
    old_key = TEST_API_KEY
    
    # Rotate
    r = api("post", f"/admin/rotate-key/{TEST_TENANT_ID}", admin=True)
    check("rotate → 200", r.status_code == 200)
    new_key = r.json()["new_api_key"]
    check("new key format", new_key.startswith("zl_live_"))
    check("new key differs", new_key != old_key)
    
    # Old key rejected
    r = api("get", "/tenant-info", key=old_key)
    check("old key → 401", r.status_code == 401)
    
    # New key works
    r = api("get", "/tenant-info", key=new_key)
    check("new key → 200", r.status_code == 200)
    
    TEST_API_KEY = new_key


def test_13_revocation():
    """Key revocation and reactivation."""
    print("\n🧪 Revocation")
    if not TEST_API_KEY or not ADMIN_KEY:
        print("  ⚠️  Skipped")
        return
    
    # Revoke
    r = api("post", f"/admin/revoke-key/{TEST_TENANT_ID}", admin=True)
    check("revoke → 200", r.status_code == 200)
    
    # Key rejected
    r = api("get", "/tenant-info", key=TEST_API_KEY)
    check("revoked key → 401", r.status_code == 401)
    
    # Reactivate
    r = api("post", f"/admin/reactivate/{TEST_TENANT_ID}", admin=True)
    check("reactivate → 200", r.status_code == 200)
    
    # Key works again
    r = api("get", "/tenant-info", key=TEST_API_KEY)
    check("reactivated key → 200", r.status_code == 200)


def test_14_validation():
    """Request validation."""
    print("\n🧪 Validation")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # Missing required fields
    r = api("post", "/extract", key=TEST_API_KEY, json={"agent_id": "test"})
    check("missing fields → 422", r.status_code == 422)
    
    # Budget out of range
    r = api("post", "/recall", key=TEST_API_KEY, json={
        "agent_id": "test",
        "conversation_context": "test",
        "budget_tokens": 100  # Below 500 minimum
    })
    check("budget too low → 422", r.status_code == 422)


def test_15_search():
    """Search endpoint."""
    print("\n🧪 Search")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r = api("get", "/memories/search", key=TEST_API_KEY, params={
        "agent_id": "ci_test",
        "q": "Alice"
    })
    check("search returns 200", r.status_code == 200)
    results = r.json()
    check("search returns list", isinstance(results, list))
    
    # Validate input limits
    r = api("get", "/memories/search", key=TEST_API_KEY, params={
        "agent_id": "ci_test",
        "q": ""
    })
    check("empty search → 422", r.status_code == 422)


def test_16_export():
    """Export endpoint."""
    print("\n🧪 Export")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r = api("get", "/memories/export", key=TEST_API_KEY, params={"agent_id": "ci_test"})
    check("export returns 200", r.status_code == 200)
    d = r.json()
    check("has agent_id", d["agent_id"] == "ci_test")
    check("has exported_at", "exported_at" in d)
    check("has memories array", isinstance(d["memories"], list))
    check("has total_memories", isinstance(d["total_memories"], int))
    
    if d["memories"]:
        m = d["memories"][0]
        check("export has full_content", "full_content" in m)
        check("export has entities", "entities" in m)
        check("export has confidence", "confidence" in m)


def test_17_delete():
    """Delete endpoint."""
    print("\n🧪 Delete")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # First create a memory to delete
    r = api("post", "/extract", key=TEST_API_KEY, json={
        "agent_id": "ci_delete_test",
        "human_message": "I live on Mars and my pet dragon is named Sparky",
        "agent_message": "Mars sounds lovely! Sparky is an excellent dragon name."
    })
    if r.status_code == 200 and r.json()["memory_ids"]:
        mem_id = r.json()["memory_ids"][0]
        
        # Delete it
        r = api("delete", f"/memories/{mem_id}", key=TEST_API_KEY)
        check("delete returns 200", r.status_code == 200)
        check("returns deleted id", r.json()["deleted"] == mem_id)
        
        # Delete again — should 404
        r = api("delete", f"/memories/{mem_id}", key=TEST_API_KEY)
        check("re-delete → 404", r.status_code == 404)
    else:
        check("setup for delete test", False, "extraction returned no memories")
    
    # Bad UUID
    r = api("delete", "/memories/00000000-0000-0000-0000-000000000000", key=TEST_API_KEY)
    check("nonexistent → 404", r.status_code == 404)


def test_18_batch_extract():
    """Batch extract endpoint."""
    print("\n🧪 Batch Extract")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r = api("post", "/extract/batch", key=TEST_API_KEY, json={
        "turns": [
            {
                "agent_id": "ci_batch",
                "human_message": "I work at NASA",
                "agent_message": "NASA is amazing!"
            },
            {
                "agent_id": "ci_batch",
                "human_message": "My favorite planet is Saturn",
                "agent_message": "Saturn's rings are beautiful!"
            }
        ]
    })
    check("batch returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        check("turns_processed = 2", d["turns_processed"] == 2)
        check("memories stored", d["memories_stored"] >= 0)


def test_19_health_enhanced():
    """Health endpoint has pool and redis info."""
    print("\n🧪 Health Enhanced")
    r = api("get", "/health")
    d = r.json()
    check("has db_pool", "db_pool" in d)
    check("has redis", "redis" in d)
    check("redis connected", d["redis"] == "connected")


def test_20_pagination():
    """Pagination with offset."""
    print("\n🧪 Pagination")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    r1 = api("get", "/memories", key=TEST_API_KEY, params={"agent_id": "ci_test", "limit": 1, "offset": 0})
    check("page 1 returns 200", r1.status_code == 200)
    
    r2 = api("get", "/memories", key=TEST_API_KEY, params={"agent_id": "ci_test", "limit": 1, "offset": 100})
    check("high offset returns 200", r2.status_code == 200)
    check("high offset returns empty", len(r2.json()) == 0)


def test_21_input_limits():
    """Input length validation."""
    print("\n🧪 Input Limits")
    if not TEST_API_KEY:
        print("  ⚠️  Skipped")
        return
    
    # Agent ID too long
    r = api("get", "/memories", key=TEST_API_KEY, params={"agent_id": "a" * 200, "limit": 1})
    check("agent_id too long → 422", r.status_code == 422)
    
    # Search query too long
    r = api("get", "/memories/search", key=TEST_API_KEY, params={"agent_id": "test", "q": "x" * 600})
    check("search query too long → 422", r.status_code == 422)


def test_22_dashboard():
    """Dashboard serves HTML."""
    print("\n🧪 Dashboard")
    r = api("get", "/dashboard")
    check("returns 200", r.status_code == 200)
    check("returns HTML", "<!DOCTYPE html>" in r.text)
    check("has Zero Latency title", "Zero Latency" in r.text)


def test_23_v1_path():
    """API v1 path works via nginx."""
    print("\n🧪 API Versioning")
    r = requests.get("https://164.90.156.169/api/v1/health", verify=False, timeout=10)
    check("/api/v1/health returns 200", r.status_code == 200)
    check("v1 returns valid JSON", "status" in r.json())


def test_99_cleanup():
    """Clean up test tenant."""
    print("\n🧧 Cleanup")
    if TEST_TENANT_ID and ADMIN_KEY:
        # Deactivate test tenant (don't delete data — just disable)
        r = api("post", f"/admin/revoke-key/{TEST_TENANT_ID}", admin=True)
        check("cleanup: deactivated test tenant", r.status_code == 200)


def main():
    global ADMIN_KEY
    if not ADMIN_KEY:
        try:
            with open("/etc/systemd/system/zerolatency-api.service") as f:
                for line in f:
                    if "MEMORY_ADMIN_KEY=" in line:
                        ADMIN_KEY = line.split("MEMORY_ADMIN_KEY=")[1].strip().strip('"')
                        break
        except Exception:
            pass
    
    print("=" * 60)
    print("Zero Latency Memory API — Full Test Suite")
    print(f"Target: {BASE}")
    print(f"Admin key: {'set' if ADMIN_KEY else 'NOT SET (admin tests will skip)'}")
    print("=" * 60)
    
    tests = [
        test_01_health,
        test_02_auth,
        test_03_create_tenant,
        test_04_tenant_info,
        test_05_extract,
        test_06_list_memories,
        test_07_recall,
        test_08_recall_edge_cases,
        test_09_sql_injection,
        test_10_tenant_isolation,
        test_11_usage,
        test_12_key_rotation,
        test_13_revocation,
        test_14_validation,
        test_15_search,
        test_16_export,
        test_17_delete,
        test_18_batch_extract,
        test_19_health_enhanced,
        test_20_pagination,
        test_21_input_limits,
        test_22_dashboard,
        test_23_v1_path,
        test_99_cleanup,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            Results.failed += 1
            Results.errors.append(f"{test.__name__}: EXCEPTION: {e}")
            print(f"  💥 {test.__name__} EXCEPTION: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {Results.passed} passed, {Results.failed} failed")
    if Results.errors:
        print("\nFailures:")
        for err in Results.errors:
            print(f"  ❌ {err}")
    print("=" * 60)
    
    return 0 if Results.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
