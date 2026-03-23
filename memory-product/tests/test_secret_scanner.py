"""
Tests for secret scanner integration.
Tests the scanner logic, API endpoints, and extraction guard behavior.
"""
import sys
import os
import pytest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from secret_scanner import scan_message, SECRET_PATTERNS


# ═══════════════════════════════════════════════════
# Unit tests for scan_message()
# ═══════════════════════════════════════════════════

class TestScanMessage:
    """Test the core secret detection logic."""

    def test_clean_text_returns_empty(self):
        """Normal text should not trigger any detections."""
        result = scan_message("The user prefers Python and hates meetings before 10am.")
        assert result == []

    def test_short_text_returns_empty(self):
        """Very short text should be skipped."""
        assert scan_message("hi") == []
        assert scan_message("") == []
        assert scan_message(None) == []

    def test_detects_pypi_token(self):
        """Should detect PyPI tokens."""
        text = "Here's my token: pypi-" + "A" * 60
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "PyPI Token" for f in result)

    def test_detects_github_pat(self):
        """Should detect GitHub personal access tokens."""
        text = "My GitHub token is ghp_" + "a" * 40
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "GitHub PAT" for f in result)

    def test_detects_openai_key(self):
        """Should detect OpenAI API keys."""
        text = "OPENAI_API_KEY=sk-" + "x" * 48
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "OpenAI Key" for f in result)

    def test_detects_anthropic_key(self):
        """Should detect Anthropic API keys."""
        text = "key: sk-ant-" + "y" * 40
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Anthropic Key" for f in result)

    def test_detects_stripe_secret(self):
        """Should detect Stripe secret keys."""
        text = "STRIPE_KEY=sk_live_" + "z" * 30
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Stripe Secret" for f in result)

    def test_detects_stripe_test_key(self):
        """Should detect Stripe test keys."""
        text = "sk_test_" + "a" * 30
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Stripe Secret" for f in result)

    def test_detects_aws_access_key(self):
        """Should detect AWS access key IDs."""
        text = "AWS_ACCESS_KEY_ID=AKIA" + "A" * 16
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "AWS Access Key" for f in result)

    def test_detects_slack_bot_token(self):
        """Should detect Slack bot tokens."""
        text = "SLACK_TOKEN=xoxb-1234567890-abcdefghij"
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Slack Bot Token" for f in result)

    def test_detects_sendgrid_key(self):
        """Should detect SendGrid API keys."""
        text = "SG." + "a" * 22 + "." + "b" * 43
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "SendGrid Key" for f in result)

    def test_detects_google_api_key(self):
        """Should detect Google API keys."""
        text = "AIza" + "x" * 35
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Google API Key" for f in result)

    def test_detects_bearer_token(self):
        """Should detect bearer tokens."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Bearer Token" for f in result)

    def test_detects_generic_secret_assignment(self):
        """Should detect generic secret assignments."""
        text = 'api_key = "' + "x" * 40 + '"'
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Generic Long Secret" for f in result)

    def test_detects_supadata_key(self):
        """Should detect Supadata API keys."""
        text = "sd_" + "a" * 32
        result = scan_message(text)
        assert len(result) >= 1
        assert any(f["pattern"] == "Supadata Key" for f in result)

    def test_redaction_format(self):
        """Redacted output should show first 6 and last 4 chars."""
        token = "ghp_" + "a" * 40  # 44 chars total
        result = scan_message(f"token: {token}")
        assert len(result) >= 1
        finding = next(f for f in result if f["pattern"] == "GitHub PAT")
        # Should be "ghp_aa...aaaa" format
        assert finding["redacted"].startswith("ghp_aa")
        assert "..." in finding["redacted"]
        assert len(finding["redacted"]) < len(token)

    def test_multiple_secrets_in_one_text(self):
        """Should detect multiple different secrets in the same text."""
        text = (
            f"OPENAI_API_KEY=sk-{'x' * 48}\n"
            f"GITHUB_TOKEN=ghp_{'a' * 40}\n"
            f"STRIPE_KEY=sk_live_{'z' * 30}\n"
        )
        result = scan_message(text)
        pattern_names = {f["pattern"] for f in result}
        assert "OpenAI Key" in pattern_names
        assert "GitHub PAT" in pattern_names
        assert "Stripe Secret" in pattern_names

    def test_position_tracking(self):
        """Findings should include position information."""
        text = "prefix " + "ghp_" + "a" * 40
        result = scan_message(text)
        assert len(result) >= 1
        assert result[0]["position"] == 7  # after "prefix "
        assert result[0]["length"] == 44


# ═══════════════════════════════════════════════════
# Tests for SECRET_PATTERNS list
# ═══════════════════════════════════════════════════

class TestPatternRegistry:
    """Test the pattern registry itself."""

    def test_patterns_not_empty(self):
        assert len(SECRET_PATTERNS) > 0

    def test_all_patterns_have_three_elements(self):
        for pattern in SECRET_PATTERNS:
            assert len(pattern) == 3, f"Pattern {pattern[0]} should have (name, regex, description)"

    def test_all_pattern_names_unique(self):
        names = [p[0] for p in SECRET_PATTERNS]
        assert len(names) == len(set(names)), "Duplicate pattern names found"

    def test_pattern_count_reasonable(self):
        """Should have a meaningful number of patterns."""
        assert len(SECRET_PATTERNS) >= 15


# ═══════════════════════════════════════════════════
# Tests for check_for_secrets() guard
# ═══════════════════════════════════════════════════

class TestCheckForSecrets:
    """Test the extraction guard function."""

    def test_clean_text_passes(self):
        from api.security import check_for_secrets
        # Should not raise
        check_for_secrets("The user likes Python and dark mode.")

    def test_none_passes(self):
        from api.security import check_for_secrets
        check_for_secrets(None)

    def test_empty_passes(self):
        from api.security import check_for_secrets
        check_for_secrets("")

    def test_secret_raises_422(self):
        from api.security import check_for_secrets
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            check_for_secrets(f"my key is sk-{'x' * 48}")
        assert exc_info.value.status_code == 422
        assert "Secret detected" in exc_info.value.detail
        assert "refusing to store" in exc_info.value.detail

    def test_error_message_includes_pattern_name(self):
        from api.security import check_for_secrets
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            check_for_secrets(f"ghp_{'a' * 40}")
        assert "GitHub PAT" in exc_info.value.detail


# ═══════════════════════════════════════════════════
# Tests for API endpoints (using TestClient)
# ═══════════════════════════════════════════════════

class TestScanEndpoint:
    """Test POST /api/v1/scan endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.security import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_scan_clean_text(self, client):
        resp = client.post("/api/v1/scan", json={"text": "The user prefers dark mode and Python."})
        assert resp.status_code == 200
        data = resp.json()
        assert data["clean"] is True
        assert data["secrets_found"] == 0
        assert data["findings"] == []

    def test_scan_with_secret(self, client):
        resp = client.post("/api/v1/scan", json={"text": f"key: sk-{'x' * 48}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["clean"] is False
        assert data["secrets_found"] >= 1
        assert len(data["findings"]) >= 1
        assert data["findings"][0]["pattern"] == "OpenAI Key"
        # Verify redaction
        assert "..." in data["findings"][0]["redacted"]

    def test_scan_empty_text_rejected(self, client):
        resp = client.post("/api/v1/scan", json={"text": ""})
        assert resp.status_code == 422  # Pydantic validation (min_length=1)

    def test_scan_missing_text_rejected(self, client):
        resp = client.post("/api/v1/scan", json={})
        assert resp.status_code == 422

    def test_scan_multiple_secrets(self, client):
        text = f"sk-{'x' * 48} and ghp_{'a' * 40}"
        resp = client.post("/api/v1/scan", json={"text": text})
        assert resp.status_code == 200
        data = resp.json()
        assert data["secrets_found"] >= 2
        patterns = {f["pattern"] for f in data["findings"]}
        assert "OpenAI Key" in patterns
        assert "GitHub PAT" in patterns


class TestPatternsEndpoint:
    """Test GET /api/v1/security/patterns endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.security import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_list_patterns(self, client):
        resp = client.get("/api/v1/security/patterns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patterns"] == len(SECRET_PATTERNS)
        assert len(data["patterns"]) == len(SECRET_PATTERNS)

    def test_pattern_structure(self, client):
        resp = client.get("/api/v1/security/patterns")
        data = resp.json()
        for p in data["patterns"]:
            assert "name" in p
            assert "description" in p
            assert len(p["name"]) > 0
            assert len(p["description"]) > 0

    def test_known_patterns_present(self, client):
        resp = client.get("/api/v1/security/patterns")
        names = {p["name"] for p in resp.json()["patterns"]}
        assert "OpenAI Key" in names
        assert "GitHub PAT" in names
        assert "Stripe Secret" in names
        assert "AWS Access Key" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
