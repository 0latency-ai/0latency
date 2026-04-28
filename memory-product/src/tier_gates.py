"""Tier-based feature gates and rate limits.

This module is the canonical source of truth for all tier-gated behavior in the
0Latency memory service. Every synthesis-related gate (rate limits, model selection,
role visibility, consensus, webhooks, audit log access) reads from the TIER_MATRIX
defined here.

No other module should hardcode tier names or limits. All tier checks should go
through the functions provided in this module.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# Canonical tier configuration matrix
TIER_MATRIX: dict[str, dict[str, Any]] = {
    "free": {
        "manual_runs_per_month": 0,
        "synthesis_runs_per_month": 0,
        "consensus_runs_per_month": 0,
        "llm_tokens_per_month": 0,
        "model": None,
        "allowed_roles": [],
        "consensus": False,
        "decision_journals": False,
        "webhooks": False,
        "audit_log_read": False,
        "cron_enabled": False,
    },
    "pro": {
        "manual_runs_per_month": 10,
        "synthesis_runs_per_month": 10,
        "consensus_runs_per_month": 0,
        "llm_tokens_per_month": 50_000,
        "model": "haiku",
        "allowed_roles": ["public"],
        "consensus": False,
        "decision_journals": False,
        "webhooks": False,
        "audit_log_read": False,
        "cron_enabled": False,
    },
    "scale": {
        "manual_runs_per_month": 200,
        "synthesis_runs_per_month": 200,
        "consensus_runs_per_month": 0,
        "llm_tokens_per_month": 1_000_000,
        "model": "haiku",
        "allowed_roles": ["public", "engineering", "product", "revenue", "legal"],
        "consensus": False,
        "decision_journals": False,
        "webhooks": True,
        "audit_log_read": False,
        "cron_enabled": True,
    },
    "enterprise": {
        "manual_runs_per_month": 1_000,
        "synthesis_runs_per_month": 1_000,
        "consensus_runs_per_month": 100,
        "llm_tokens_per_month": 10_000_000,
        "model": "sonnet",
        "allowed_roles": ["public", "engineering", "product", "revenue", "legal"],
        "consensus": True,
        "decision_journals": True,
        "webhooks": True,
        "audit_log_read": True,
        "cron_enabled": True,
    },
}


# Valid tier identifiers
VALID_TIERS = list(TIER_MATRIX.keys())


def get_tier(tenant_id: str, conn) -> str:
    """Get the tier (plan) for a given tenant.

    Args:
        tenant_id: Tenant UUID
        conn: psycopg connection (sync)

    Returns:
        Tier name (one of VALID_TIERS), defaulting to "free" if NULL or unrecognized
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT plan FROM memory_service.tenants WHERE id = %s",
            (tenant_id,)
        )
        row = cur.fetchone()

        if not row or not row[0]:
            return "free"

        plan = row[0]
        if plan not in VALID_TIERS:
            logger.warning(
                "Unrecognized tier '%s' for tenant %s; defaulting to 'free'",
                plan,
                tenant_id
            )
            return "free"

        return plan


def check_synthesis_quota(
    tenant_id: str,
    kind: str,
    conn,
    amount: int = 1,
) -> tuple[bool, str]:
    """Check if a synthesis operation is within quota for the tenant's tier.

    Args:
        tenant_id: Tenant UUID
        kind: Operation type - one of "manual_run", "cron_run", "consensus_run", "llm_tokens"
        conn: psycopg connection (sync)
        amount: Number of units to check (default: 1)

    Returns:
        (allowed, reason) tuple. reason is empty string if allowed, otherwise
        contains a human-readable error message.
    """
    tier = get_tier(tenant_id, conn)
    matrix = TIER_MATRIX[tier]

    # Map kind to matrix key and check feature gate if applicable
    if kind == "manual_run":
        limit_key = "manual_runs_per_month"
        current_col = "synthesis_runs_this_month"
    elif kind == "cron_run":
        if not matrix["cron_enabled"]:
            reason = f"{tier.capitalize()} tier does not support scheduled synthesis"
            logger.info("Quota check failed for %s: %s", tenant_id, reason)
            return (False, reason)
        limit_key = "synthesis_runs_per_month"
        current_col = "synthesis_runs_this_month"
    elif kind == "consensus_run":
        if not matrix["consensus"]:
            reason = f"{tier.capitalize()} tier does not support consensus synthesis"
            logger.info("Quota check failed for %s: %s", tenant_id, reason)
            return (False, reason)
        limit_key = "consensus_runs_per_month"
        current_col = "consensus_runs_this_month"
    elif kind == "llm_tokens":
        limit_key = "llm_tokens_per_month"
        current_col = "llm_tokens_this_month"
    else:
        raise ValueError(f"Unknown synthesis kind: {kind}")

    limit = matrix[limit_key]

    # Get current usage from synthesis_rate_limits table
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {current_col} FROM memory_service.synthesis_rate_limits WHERE tenant_id = %s",
            (tenant_id,)
        )
        row = cur.fetchone()
        current = row[0] if row else 0

    # Check if adding amount would exceed limit (strict >)
    if current + amount > limit:
        reason = (
            f"{tier.capitalize()} tier limited to {limit:,} "
            f"{kind.replace('_', ' ')}s/month; current: {current:,}"
        )
        logger.info("Quota check failed for %s: %s", tenant_id, reason)
        return (False, reason)

    logger.debug("Quota check passed for %s: %s (current: %d, limit: %d)",
                 tenant_id, kind, current, limit)
    return (True, "")


def increment_synthesis_counter(
    tenant_id: str,
    kind: str,
    conn,
    amount: int = 1,
) -> None:
    """Increment synthesis usage counters for a tenant.

    Args:
        tenant_id: Tenant UUID
        kind: Operation type - one of "manual_run", "cron_run", "consensus_run", "llm_tokens"
        conn: psycopg connection (sync)
        amount: Number of units to increment (default: 1)

    Note:
        Caller is responsible for transaction boundaries.
    """
    # Map kind to column pairs
    if kind in ("manual_run", "cron_run"):
        daily_col = "synthesis_runs_today"
        monthly_col = "synthesis_runs_this_month"
    elif kind == "consensus_run":
        # Consensus has no daily column
        daily_col = None
        monthly_col = "consensus_runs_this_month"
    elif kind == "llm_tokens":
        daily_col = "llm_tokens_today"
        monthly_col = "llm_tokens_this_month"
    else:
        raise ValueError(f"Unknown synthesis kind: {kind}")

    with conn.cursor() as cur:
        if daily_col:
            cur.execute(
                f"""
                UPDATE memory_service.synthesis_rate_limits
                SET {daily_col} = {daily_col} + %s,
                    {monthly_col} = {monthly_col} + %s,
                    updated_at = NOW()
                WHERE tenant_id = %s
                """,
                (amount, amount, tenant_id)
            )
        else:
            cur.execute(
                f"""
                UPDATE memory_service.synthesis_rate_limits
                SET {monthly_col} = {monthly_col} + %s,
                    updated_at = NOW()
                WHERE tenant_id = %s
                """,
                (amount, tenant_id)
            )


def get_allowed_model(tenant_id: str, conn) -> str | None:
    """Get the allowed LLM model for a tenant's tier.

    Args:
        tenant_id: Tenant UUID
        conn: psycopg connection (sync)

    Returns:
        Model identifier string, or None if no model is allowed (free tier)
    """
    tier = get_tier(tenant_id, conn)
    return TIER_MATRIX[tier]["model"]


def get_allowed_roles(tenant_id: str, conn) -> list[str]:
    """Get the allowed message roles for a tenant's tier.

    Args:
        tenant_id: Tenant UUID
        conn: psycopg connection (sync)

    Returns:
        List of allowed role names (e.g., ["user", "assistant", "system"])
    """
    tier = get_tier(tenant_id, conn)
    return TIER_MATRIX[tier]["allowed_roles"]


def is_feature_enabled(tenant_id: str, feature: str, conn) -> bool:
    """Check if a feature is enabled for a tenant's tier.

    Args:
        tenant_id: Tenant UUID
        feature: Feature name - one of "consensus", "decision_journals", "webhooks",
                "audit_log_read", "cron_enabled"
        conn: psycopg connection (sync)

    Returns:
        True if the feature is enabled for this tier, False otherwise

    Raises:
        ValueError: If feature name is not recognized
    """
    valid_features = {
        "consensus",
        "decision_journals",
        "webhooks",
        "audit_log_read",
        "cron_enabled",
    }

    if feature not in valid_features:
        raise ValueError(f"Unknown feature: {feature}")

    tier = get_tier(tenant_id, conn)
    return TIER_MATRIX[tier][feature]


if __name__ == "__main__":
    # Sanity check: print the tier matrix as JSON
    print(json.dumps(TIER_MATRIX, indent=2))
