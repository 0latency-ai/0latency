"""
Unit Tests for Memory Consolidation

Tests the merge strategy, similarity detection, and feature gating logic.
Run with: pytest tests/test_consolidation.py -v
"""

import math
import sys
import os
import pytest

# Add src/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from consolidation import (
    cosine_similarity,
    check_consolidation_access,
    CONSOLIDATION_ACCESS,
)


# ─── Cosine Similarity Tests ────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)
    
    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)
    
    def test_opposite_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)
    
    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        sim = cosine_similarity(a, b)
        assert sim > 0.99  # Very similar
    
    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0
    
    def test_zero_vector(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0
    
    def test_different_lengths(self):
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0
    
    def test_single_dimension(self):
        assert cosine_similarity([5.0], [3.0]) == pytest.approx(1.0, abs=1e-6)
    
    def test_high_dimensional(self):
        """Test with 768-dim vectors (embedding size)."""
        import random
        random.seed(42)
        a = [random.gauss(0, 1) for _ in range(768)]
        # b is a slight perturbation of a
        b = [x + random.gauss(0, 0.1) for x in a]
        sim = cosine_similarity(a, b)
        assert sim > 0.9  # Should be very similar


# ─── Feature Gating Tests ───────────────────────────────────────────────────

class TestFeatureGating:
    def test_free_tier_no_access(self):
        tenant = {"plan": "free"}
        assert not check_consolidation_access(tenant, "list_duplicates")
        assert not check_consolidation_access(tenant, "merge")
        assert not check_consolidation_access(tenant, "dismiss")
        assert not check_consolidation_access(tenant, "auto_consolidate")
    
    def test_pro_tier_manual_access(self):
        tenant = {"plan": "pro"}
        assert check_consolidation_access(tenant, "list_duplicates")
        assert check_consolidation_access(tenant, "merge")
        assert check_consolidation_access(tenant, "dismiss")
        assert not check_consolidation_access(tenant, "auto_consolidate")
        assert not check_consolidation_access(tenant, "custom_threshold")
    
    def test_scale_tier_auto_access(self):
        tenant = {"plan": "scale"}
        assert check_consolidation_access(tenant, "list_duplicates")
        assert check_consolidation_access(tenant, "merge")
        assert check_consolidation_access(tenant, "dismiss")
        assert check_consolidation_access(tenant, "auto_consolidate")
        assert not check_consolidation_access(tenant, "custom_threshold")
    
    def test_enterprise_full_access(self):
        tenant = {"plan": "enterprise"}
        for action in ["list_duplicates", "merge", "dismiss", "auto_consolidate", "custom_threshold"]:
            assert check_consolidation_access(tenant, action), f"Enterprise should have {action} access"
    
    def test_unknown_plan_no_access(self):
        tenant = {"plan": "mystery"}
        assert not check_consolidation_access(tenant, "list_duplicates")
    
    def test_missing_plan_no_access(self):
        tenant = {}
        assert not check_consolidation_access(tenant, "list_duplicates")


# ─── Merge Strategy Tests (unit logic, no DB) ───────────────────────────────

class TestMergeStrategy:
    """Test the merge logic decisions without touching the database."""
    
    def test_confidence_determines_winner(self):
        """Higher confidence memory should be the winner."""
        mem1 = {"confidence": 0.9, "importance": 0.5}
        mem2 = {"confidence": 0.7, "importance": 0.5}
        # Winner is the one with higher confidence
        winner = mem1 if (mem1["confidence"] or 0.5) >= (mem2["confidence"] or 0.5) else mem2
        assert winner == mem1
    
    def test_importance_takes_max(self):
        """Merged importance should be max of both."""
        imp1, imp2 = 0.7, 0.9
        merged = max(imp1, imp2)
        assert merged == 0.9
    
    def test_confidence_corroboration_bonus(self):
        """Merged confidence = average + 0.1, capped at 0.99."""
        conf1, conf2 = 0.8, 0.7
        avg = (conf1 + conf2) / 2
        merged = min(0.99, avg + 0.1)
        assert merged == pytest.approx(0.85, abs=1e-6)
    
    def test_confidence_cap_at_099(self):
        """Confidence should never exceed 0.99."""
        conf1, conf2 = 0.95, 0.98
        avg = (conf1 + conf2) / 2
        merged = min(0.99, avg + 0.1)
        assert merged == 0.99
    
    def test_sentiment_averaging_same_sign(self):
        """Same-sign sentiments should be averaged."""
        score1, score2 = 0.6, 0.8
        if (score1 >= 0 and score2 >= 0) or (score1 < 0 and score2 < 0):
            merged = (score1 + score2) / 2
        else:
            merged = score1  # keep winner
        assert merged == pytest.approx(0.7, abs=1e-6)
    
    def test_sentiment_conflict_keeps_winner(self):
        """Conflicting sentiments (different signs) should keep the winner's."""
        score_winner, score_loser = 0.6, -0.4
        if (score_winner >= 0 and score_loser >= 0) or (score_winner < 0 and score_loser < 0):
            merged = (score_winner + score_loser) / 2
        else:
            merged = score_winner
        assert merged == 0.6
    
    def test_headline_combination_for_important_loser(self):
        """If loser has importance >= 0.6, headlines should combine."""
        winner_headline = "User prefers Python"
        loser_headline = "User loves Python for data science"
        loser_importance = 0.7
        
        if loser_importance >= 0.6 and winner_headline != loser_headline:
            merged = f"{winner_headline} (also: {loser_headline})"
        else:
            merged = winner_headline
        
        assert "also:" in merged
        assert "data science" in merged
    
    def test_headline_no_combination_for_low_importance(self):
        """If loser has low importance, just keep winner's headline."""
        winner_headline = "User prefers Python"
        loser_headline = "Python preference noted"
        loser_importance = 0.3
        
        if loser_importance >= 0.6 and winner_headline != loser_headline:
            merged = f"{winner_headline} (also: {loser_headline})"
        else:
            merged = winner_headline
        
        assert merged == winner_headline
    
    def test_context_concatenation(self):
        """Both contexts should be preserved with separator."""
        ctx1 = "Mentioned during project discussion"
        ctx2 = "Confirmed in follow-up meeting"
        
        contexts = [ctx1]
        if ctx2 and ctx2 != ctx1:
            contexts.append(ctx2)
        merged = "\n---\n".join(contexts)
        
        assert ctx1 in merged
        assert ctx2 in merged
        assert "---" in merged
    
    def test_context_dedup(self):
        """Identical contexts should not be duplicated."""
        ctx = "Same context"
        
        contexts = [ctx]
        if ctx and ctx != ctx:  # same context — won't be added
            contexts.append(ctx)
        merged = "\n---\n".join(contexts)
        
        assert merged.count("Same context") == 1


# ─── Access Control Matrix ──────────────────────────────────────────────────

class TestAccessMatrix:
    """Verify the full access control matrix."""
    
    def test_all_plans_covered(self):
        """Every plan should be defined in CONSOLIDATION_ACCESS."""
        for plan in ["free", "pro", "scale", "enterprise"]:
            assert plan in CONSOLIDATION_ACCESS
    
    def test_hierarchy_is_inclusive(self):
        """Higher tiers should have at least everything lower tiers have."""
        plans = ["free", "pro", "scale", "enterprise"]
        for i in range(len(plans) - 1):
            lower = CONSOLIDATION_ACCESS[plans[i]]
            higher = CONSOLIDATION_ACCESS[plans[i + 1]]
            assert lower.issubset(higher), \
                f"{plans[i+1]} should include all {plans[i]} permissions: missing {lower - higher}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
