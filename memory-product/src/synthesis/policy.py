"""Synthesis policy DSL parser and validator.

This module defines the JSON schema for synthesis policies and provides functions
to validate, load, and save policies. Synthesis policies control:
- Redaction cascade behavior (how synthesis nodes react to source changes)
- Role visibility (which tenant roles can see which synthesis outputs)
- Retention rules (archival and expiration)
- Consensus requirements (multi-agent synthesis configuration)

All synthesis operations should read policy from this module via load_policy().
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


# Default policy for Free/Pro/Scale tiers
DEFAULT_POLICY_STANDARD: dict[str, Any] = {
    "redaction_rules": {
        "on_source_redacted": "resynthesize_without",
        "on_source_modified": "mark_pending_review",
        "cascade_depth": "evidence_chain_only",
    },
    "role_visibility": {
        "default_role": "public",
        "produce_for_roles": ["public"],
        "cross_role_read": False,
    },
    "retention": {
        "max_age_days": None,
        "auto_archive": False,
    },
    "consensus_requirements": {
        "method": "majority_vote",
        "min_agents": 1,
        "tie_breaker": "highest_confidence",
    },
}


# Default policy for Enterprise tier
DEFAULT_POLICY_ENTERPRISE: dict[str, Any] = {
    "redaction_rules": {
        "on_source_redacted": "resynthesize_without",
        "on_source_modified": "mark_pending_review",
        "cascade_depth": "evidence_chain_only",
    },
    "role_visibility": {
        "default_role": "public",
        "produce_for_roles": ["public", "engineering", "product", "revenue", "legal"],
        "cross_role_read": False,
    },
    "retention": {
        "max_age_days": None,
        "auto_archive": False,
    },
    "consensus_requirements": {
        "method": "majority_vote",
        "min_agents": 3,
        "tie_breaker": "highest_confidence",
    },
}


# JSON Schema for synthesis policy validation
POLICY_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["redaction_rules", "role_visibility", "retention", "consensus_requirements"],
    "additionalProperties": False,
    "properties": {
        "redaction_rules": {
            "type": "object",
            "required": ["on_source_redacted", "on_source_modified", "cascade_depth"],
            "additionalProperties": False,
            "properties": {
                "on_source_redacted": {
                    "type": "string",
                    "enum": ["invalidate", "resynthesize_without", "mark_pending_review"],
                },
                "on_source_modified": {
                    "type": "string",
                    "enum": ["invalidate", "resynthesize_without", "mark_pending_review"],
                },
                "cascade_depth": {
                    "type": "string",
                    "enum": ["evidence_chain_only", "full_cluster"],
                },
            },
        },
        "role_visibility": {
            "type": "object",
            "required": ["default_role", "produce_for_roles", "cross_role_read"],
            "additionalProperties": False,
            "properties": {
                "default_role": {
                    "type": "string",
                    "enum": ["public", "engineering", "product", "revenue", "legal"],
                },
                "produce_for_roles": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["public", "engineering", "product", "revenue", "legal"],
                    },
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "cross_role_read": {
                    "type": "boolean",
                },
            },
        },
        "retention": {
            "type": "object",
            "required": ["max_age_days", "auto_archive"],
            "additionalProperties": False,
            "properties": {
                "max_age_days": {
                    "oneOf": [
                        {"type": "null"},
                        {"type": "integer", "minimum": 1},
                    ],
                },
                "auto_archive": {
                    "type": "boolean",
                },
            },
        },
        "consensus_requirements": {
            "type": "object",
            "required": ["method", "min_agents", "tie_breaker"],
            "additionalProperties": False,
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["single_agent", "majority_vote", "weighted", "unanimous"],
                },
                "min_agents": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                },
                "tie_breaker": {
                    "type": "string",
                    "enum": ["highest_confidence", "most_recent", "most_sources"],
                },
            },
        },
    },
}


def validate_policy(policy: dict) -> tuple[bool, list[str]]:
    """Validate a policy dictionary against the JSON schema.

    Args:
        policy: Policy dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_error_messages). If valid, error list is empty.
    """
    try:
        import jsonschema
    except ImportError:
        logger.error("jsonschema library not installed; cannot validate policy")
        return (False, ["jsonschema library not installed"])

    try:
        jsonschema.validate(instance=policy, schema=POLICY_JSON_SCHEMA)
        return (True, [])
    except jsonschema.ValidationError as e:
        error_path = ".".join(str(p) for p in e.path) if e.path else "root"
        error_msg = f"{error_path}: {e.message}"
        logger.debug("Policy validation failed: %s", error_msg)
        return (False, [error_msg])
    except jsonschema.SchemaError as e:
        logger.error("Invalid JSON schema: %s", e.message)
        return (False, [f"Schema error: {e.message}"])


def load_policy(tenant_id: str, conn) -> dict:
    """Load the synthesis policy for a tenant.

    Args:
        tenant_id: Tenant UUID
        conn: psycopg connection (sync)

    Returns:
        Policy dictionary

    Raises:
        ValueError: If tenant not found or policy is invalid
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT synthesis_policy FROM memory_service.tenants WHERE id = %s",
            (tenant_id,),
        )
        row = cur.fetchone()

        if not row:
            raise ValueError(f"Tenant {tenant_id} not found")

        policy = row[0]
        if not policy:
            raise ValueError(f"Tenant {tenant_id} has no synthesis policy")

        # Validate the stored policy (defensive check)
        is_valid, errors = validate_policy(policy)
        if not is_valid:
            logger.warning(
                "Tenant %s has invalid policy in database: %s",
                tenant_id,
                errors,
            )
            raise ValueError(f"Invalid policy stored for tenant {tenant_id}: {errors}")

        return policy


def save_policy(tenant_id: str, policy: dict, conn) -> None:
    """Save a synthesis policy for a tenant.

    Args:
        tenant_id: Tenant UUID
        policy: Policy dictionary to save
        conn: psycopg connection (sync)

    Raises:
        ValueError: If policy is invalid or tenant not found

    Note:
        Caller is responsible for transaction boundaries.
    """
    # Validate policy first
    is_valid, errors = validate_policy(policy)
    if not is_valid:
        raise ValueError(f"Invalid policy: {errors}")

    with conn.cursor() as cur:
        # Import json to serialize the policy
        import json

        cur.execute(
            "UPDATE memory_service.tenants SET synthesis_policy = %s WHERE id = %s",
            (json.dumps(policy), tenant_id),
        )

        if cur.rowcount == 0:
            raise ValueError(f"Tenant {tenant_id} not found")

    logger.info("Saved synthesis policy for tenant %s", tenant_id)


def get_default_policy_for_tier(tier: str) -> dict:
    """Get the default policy for a given tier.

    Args:
        tier: Tier name (free, pro, scale, enterprise)

    Returns:
        Default policy dictionary for the tier

    Note:
        Enterprise tier gets multi-agent consensus defaults and all role visibility.
        All other tiers get single-agent defaults and public-only visibility.
    """
    if tier == "enterprise":
        return copy.deepcopy(DEFAULT_POLICY_ENTERPRISE)
    else:
        return copy.deepcopy(DEFAULT_POLICY_STANDARD)
