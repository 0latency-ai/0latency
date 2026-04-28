"""Tests for synthesis policy DSL."""

import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.synthesis.policy import (
    DEFAULT_POLICY_ENTERPRISE,
    DEFAULT_POLICY_STANDARD,
    POLICY_JSON_SCHEMA,
    get_default_policy_for_tier,
    load_policy,
    save_policy,
    validate_policy,
)


def test_default_policies_validate():
    """Both default policies should pass validation."""
    is_valid, errors = validate_policy(DEFAULT_POLICY_STANDARD)
    assert is_valid, f"Standard policy invalid: {errors}"

    is_valid, errors = validate_policy(DEFAULT_POLICY_ENTERPRISE)
    assert is_valid, f"Enterprise policy invalid: {errors}"


def test_invalid_consensus_method_rejected():
    """Invalid consensus method should be rejected."""
    policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
    policy["consensus_requirements"]["method"] = "invalid_method"

    is_valid, errors = validate_policy(policy)
    assert not is_valid
    assert len(errors) > 0


def test_invalid_role_rejected():
    """Invalid role should be rejected."""
    policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
    policy["role_visibility"]["default_role"] = "invalid_role"

    is_valid, errors = validate_policy(policy)
    assert not is_valid
    assert len(errors) > 0


def test_min_agents_must_be_positive_int():
    """min_agents must be a positive integer."""
    # Test zero
    policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
    policy["consensus_requirements"]["min_agents"] = 0

    is_valid, errors = validate_policy(policy)
    assert not is_valid

    # Test negative
    policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
    policy["consensus_requirements"]["min_agents"] = -1
    is_valid, errors = validate_policy(policy)
    assert not is_valid

    # Test greater than 10
    policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
    policy["consensus_requirements"]["min_agents"] = 11
    is_valid, errors = validate_policy(policy)
    assert not is_valid


def test_get_default_for_tier_pro_returns_min_agents_1():
    """Pro tier should get min_agents=1."""
    policy = get_default_policy_for_tier("pro")
    assert policy["consensus_requirements"]["min_agents"] == 1


def test_get_default_for_tier_enterprise_returns_min_agents_3():
    """Enterprise tier should get min_agents=3."""
    policy = get_default_policy_for_tier("enterprise")
    assert policy["consensus_requirements"]["min_agents"] == 3


def test_save_policy_invalid_raises_value_error():
    """save_policy should raise ValueError for invalid policy."""
    mock_conn = MagicMock()

    invalid_policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
    invalid_policy["consensus_requirements"]["method"] = "invalid"

    with pytest.raises(ValueError, match="Invalid policy"):
        save_policy("test-tenant-id", invalid_policy, mock_conn)


def test_load_save_roundtrip_via_db():
    """Test loading and saving policy via real database connection."""
    # Get DATABASE_URL from environment
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    import psycopg2

    # Thomas tenant ID
    tenant_id = "44c3080d-c196-407d-a606-4ea9f62ba0fc"

    conn = psycopg2.connect(database_url)

    try:
        # Save original policy
        original_policy = load_policy(tenant_id, conn)

        # Create a modified policy
        modified_policy = copy.deepcopy(DEFAULT_POLICY_STANDARD)
        modified_policy["retention"]["max_age_days"] = 90
        modified_policy["consensus_requirements"]["min_agents"] = 2

        # Save the modified policy
        save_policy(tenant_id, modified_policy, conn)
        conn.commit()

        # Load it back
        loaded_policy = load_policy(tenant_id, conn)

        # Verify the changes
        assert loaded_policy["retention"]["max_age_days"] == 90
        assert loaded_policy["consensus_requirements"]["min_agents"] == 2

    finally:
        # Restore original policy
        save_policy(tenant_id, original_policy, conn)
        conn.commit()
        conn.close()
