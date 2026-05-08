"""
Consolidation Package - Phase 2 of Self-Improving Memory
Classifies and consolidates similar memories.
"""

# Re-export functions from parent consolidation.py module
# to support 'from consolidation import' syntax in tests

import math
from typing import Dict, Any

# Tier access control for consolidation features
CONSOLIDATION_ACCESS = {
    "free": set(),
    "pro": {"list_duplicates", "merge", "dismiss"},
    "scale": {"list_duplicates", "merge", "dismiss", "auto_consolidate"},
    "enterprise": {"list_duplicates", "merge", "dismiss", "auto_consolidate", "custom_threshold"},
}


def check_consolidation_access(tenant: dict, action: str) -> bool:
    """Check if tenant's plan allows a consolidation action."""
    plan = tenant.get("plan", "free")
    allowed = CONSOLIDATION_ACCESS.get(plan, set())
    return action in allowed


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))
    
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    
    return dot_product / (magnitude_a * magnitude_b)


__all__ = [
    'cosine_similarity',
    'check_consolidation_access',
    'CONSOLIDATION_ACCESS',
]
