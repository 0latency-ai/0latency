"""Tests for the zerolatency SDK client."""

import httpx
import pytest
import respx

from zerolatency import AuthenticationError, Memory, RateLimitError, ZeroLatencyError

BASE = "https://api.0latency.ai"


@pytest.fixture()
def memory():
    client = Memory("test-key")
    yield client
    client.close()


# -- add ---------------------------------------------------------------------


@respx.mock
def test_add_basic(memory: Memory):
    route = respx.post(f"{BASE}/v1/memories").mock(
        return_value=httpx.Response(200, json={"id": "mem_1", "status": "ok"})
    )
    result = memory.add("remember this")
    assert result == {"id": "mem_1", "status": "ok"}
    assert route.called
    payload = route.calls.last.request.content
    assert b"remember this" in payload


@respx.mock
def test_add_with_agent_and_metadata(memory: Memory):
    respx.post(f"{BASE}/v1/memories").mock(
        return_value=httpx.Response(200, json={"id": "mem_2"})
    )
    result = memory.add("fact", agent_id="a1", metadata={"src": "test"})
    assert result["id"] == "mem_2"


# -- recall ------------------------------------------------------------------


@respx.mock
def test_recall(memory: Memory):
    respx.get(f"{BASE}/v1/memories/recall").mock(
        return_value=httpx.Response(200, json={"memories": [{"content": "dark mode"}]})
    )
    result = memory.recall("preferences")
    assert len(result["memories"]) == 1


@respx.mock
def test_recall_with_params(memory: Memory):
    route = respx.get(f"{BASE}/v1/memories/recall").mock(
        return_value=httpx.Response(200, json={"memories": []})
    )
    memory.recall("q", agent_id="a1", limit=5)
    url = str(route.calls.last.request.url)
    assert "agent_id=a1" in url
    assert "limit=5" in url


# -- extract -----------------------------------------------------------------


@respx.mock
def test_extract(memory: Memory):
    respx.post(f"{BASE}/v1/memories/extract").mock(
        return_value=httpx.Response(200, json={"job_id": "job_1"})
    )
    result = memory.extract([{"role": "user", "content": "hi"}])
    assert result["job_id"] == "job_1"


@respx.mock
def test_extract_status(memory: Memory):
    respx.get(f"{BASE}/v1/memories/extract/job_1").mock(
        return_value=httpx.Response(200, json={"status": "completed"})
    )
    result = memory.extract_status("job_1")
    assert result["status"] == "completed"


# -- health ------------------------------------------------------------------


@respx.mock
def test_health(memory: Memory):
    respx.get(f"{BASE}/v1/health").mock(
        return_value=httpx.Response(200, json={"status": "healthy"})
    )
    assert memory.health()["status"] == "healthy"


# -- errors ------------------------------------------------------------------


@respx.mock
def test_auth_error(memory: Memory):
    respx.post(f"{BASE}/v1/memories").mock(
        return_value=httpx.Response(401, json={"detail": "unauthorized"})
    )
    with pytest.raises(AuthenticationError) as exc_info:
        memory.add("test")
    assert exc_info.value.status_code == 401


@respx.mock
def test_rate_limit_error(memory: Memory):
    respx.post(f"{BASE}/v1/memories").mock(
        return_value=httpx.Response(429, json={"detail": "too many requests"})
    )
    with pytest.raises(RateLimitError) as exc_info:
        memory.add("test")
    assert exc_info.value.status_code == 429


@respx.mock
def test_generic_error(memory: Memory):
    respx.post(f"{BASE}/v1/memories").mock(
        return_value=httpx.Response(500, json={"detail": "internal error"})
    )
    with pytest.raises(ZeroLatencyError) as exc_info:
        memory.add("test")
    assert exc_info.value.status_code == 500
    assert "internal error" in exc_info.value.message


# -- context manager ---------------------------------------------------------


@respx.mock
def test_context_manager():
    respx.get(f"{BASE}/v1/health").mock(
        return_value=httpx.Response(200, json={"status": "healthy"})
    )
    with Memory("test-key") as mem:
        assert mem.health()["status"] == "healthy"


# -- headers -----------------------------------------------------------------


@respx.mock
def test_auth_header(memory: Memory):
    route = respx.get(f"{BASE}/v1/health").mock(
        return_value=httpx.Response(200, json={})
    )
    memory.health()
    auth = route.calls.last.request.headers["authorization"]
    assert auth == "Bearer test-key"
