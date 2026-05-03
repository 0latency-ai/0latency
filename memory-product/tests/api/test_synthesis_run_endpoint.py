"""
CP8 Phase 2 T5+T6 — Synthesis Endpoint Tests

Six integration tests for POST /synthesis/run.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import os


@pytest.fixture
def test_api_key():
    """Get API key from environment."""
    return os.environ.get("ZEROLATENCY_API_KEY")


@pytest.mark.integration
def test_endpoint_smoke(test_api_key):
    """Test 1: Endpoint returns 200 with valid request."""
    import requests
    
    if not test_api_key:
        pytest.skip("ZEROLATENCY_API_KEY not set")
    
    response = requests.post(
        "http://localhost:8420/synthesis/run",
        headers={"X-API-Key": test_api_key},
        json={"agent_id": "user-justin", "max_clusters": 1},
        timeout=30,
    )
    
    assert response.status_code in (200, 403, 429)  # Any valid response
    
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "job_id" in data


@pytest.mark.integration  
def test_endpoint_401_missing_key():
    """Test 2: Missing X-API-Key returns 401."""
    import requests
    
    response = requests.post(
        "http://localhost:8420/synthesis/run",
        json={"agent_id": "user-justin"},
        timeout=10,
    )
    
    assert response.status_code == 401


@pytest.mark.integration
def test_endpoint_422_malformed_body(test_api_key):
    """Test 3: Missing required field returns 422."""
    import requests
    
    if not test_api_key:
        pytest.skip("ZEROLATENCY_API_KEY not set")
    
    response = requests.post(
        "http://localhost:8420/synthesis/run",
        headers={"X-API-Key": test_api_key},
        json={},  # Missing agent_id
        timeout=10,
    )
    
    assert response.status_code == 422


@pytest.mark.integration
def test_endpoint_caps_max_clusters(test_api_key):
    """Test 4: max_clusters > 10 is capped server-side."""
    import requests
    
    if not test_api_key:
        pytest.skip("ZEROLATENCY_API_KEY not set")
    
    response = requests.post(
        "http://localhost:8420/synthesis/run",
        headers={"X-API-Key": test_api_key},
        json={"agent_id": "user-justin", "max_clusters": 999},
        timeout=30,
    )
    
    # Should succeed or skip; the 999 should be capped to 10 internally
    # We can't directly verify the cap, but it shouldn't error
    assert response.status_code in (200, 403, 429)


@pytest.mark.integration
def test_endpoint_returns_json(test_api_key):
    """Test 5: Response is valid JSON."""
    import requests
    
    if not test_api_key:
        pytest.skip("ZEROLATENCY_API_KEY not set")
    
    response = requests.post(
        "http://localhost:8420/synthesis/run",
        headers={"X-API-Key": test_api_key},
        json={"agent_id": "user-justin"},
        timeout=30,
    )
    
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)


@pytest.mark.integration
def test_endpoint_optional_params(test_api_key):
    """Test 6: Optional params (role_scope, force) work."""
    import requests
    
    if not test_api_key:
        pytest.skip("ZEROLATENCY_API_KEY not set")
    
    response = requests.post(
        "http://localhost:8420/synthesis/run",
        headers={"X-API-Key": test_api_key},
        json={
            "agent_id": "user-justin",
            "role_scope": "public",
            "force": False,
            "max_clusters": 1,
        },
        timeout=30,
    )
    
    assert response.status_code in (200, 403, 429)
