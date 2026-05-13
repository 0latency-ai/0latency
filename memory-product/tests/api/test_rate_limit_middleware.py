"""
Integration test: rate-limit middleware returns 429 (not 500).

Exercises the full middleware path via TestClient so the bug where
HTTPException leaked as 500 through ServerErrorMiddleware is covered.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from unittest.mock import patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware_security import security_middleware
from security.rate_limiter_enhanced import (
    _in_memory_buckets,
    GLOBAL_IP_LIMIT_RPM,
)


TEST_LIMIT = 3  # small limit for fast tests


def _make_app():
    """Build a minimal FastAPI app with only the security middleware."""
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.middleware("http")(security_middleware)
    return app


@pytest.fixture(autouse=True)
def _clean_buckets():
    """Clear in-memory rate-limit state before every test."""
    _in_memory_buckets.clear()
    yield
    _in_memory_buckets.clear()


@patch("security.rate_limiter_enhanced._get_redis", return_value=None)
@patch("security.rate_limiter_enhanced.GLOBAL_IP_LIMIT_RPM", TEST_LIMIT)
def test_rate_limit_returns_429_not_500(_mock_redis):
    """Hit /ping TEST_LIMIT+1 times; last response must be 429 with Retry-After."""
    app = _make_app()
    client = TestClient(app)

    # First TEST_LIMIT requests should succeed
    for i in range(TEST_LIMIT):
        resp = client.get("/ping")
        assert resp.status_code == 200, f"Request {i+1} should be 200, got {resp.status_code}"

    # Next request should be rate-limited
    resp = client.get("/ping")
    assert resp.status_code == 429, (
        f"Expected 429 after exceeding limit, got {resp.status_code}"
    )

    # Verify Retry-After header is present and parseable as int
    retry_after = resp.headers.get("Retry-After")
    assert retry_after is not None, "Retry-After header missing from 429 response"
    assert int(retry_after) > 0, "Retry-After must be a positive integer"

    # Verify response body contains rate-limit detail
    body = resp.json()
    assert "detail" in body
    assert body["detail"]["error"] == "rate_limit_exceeded"
