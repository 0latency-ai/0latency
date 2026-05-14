#!/usr/bin/env python3
"""Scoring-invariants test suite for recall adaptive composite scoring.

Tests ranking correctness against synthetic fixtures covering:
1. Relevant memory beats irrelevant (semantic dominance)
2. Recency flattening doesn't produce query-invariant ranking
3. Type bonuses don't override strong semantic match
4. Scale stability (more candidates don't change relative ordering)
5. Batch vs trickle timestamp equivalence
"""
import math
import sys
import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Setup path
sys.path.insert(0, '/root/.openclaw/workspace/memory-product/src')
sys.path.insert(0, '/root/.openclaw/workspace/memory-product')

# Load env
from pathlib import Path
env_path = Path('/root/.openclaw/workspace/memory-product/.env')
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = val

# Force local embeddings for testing
os.environ['RECALL_USE_VOYAGE'] = 'false'
os.environ['RECALL_KEYWORD_MATCH_ENABLED'] = 'false'
os.environ['RECALL_ENTITY_STRATEGY_ENABLED'] = 'false'
os.environ['RECALL_TYPE_BONUS_ENTITY_AWARE'] = 'false'

from recall import _compute_signal_spread, _compute_adaptive_weights


class TestSignalSpread(unittest.TestCase):
    """Test _compute_signal_spread correctness."""

    def test_empty_list(self):
        self.assertEqual(_compute_signal_spread([]), 0.0)

    def test_single_value(self):
        self.assertEqual(_compute_signal_spread([0.5]), 0.0)

    def test_identical_values(self):
        """All-same values → spread = 0 (degenerate)."""
        self.assertAlmostEqual(_compute_signal_spread([0.5, 0.5, 0.5, 0.5]), 0.0)

    def test_moderate_spread(self):
        """Spread of [0.1, 0.5, 0.9] should be ~0.33."""
        spread = _compute_signal_spread([0.1, 0.5, 0.9])
        self.assertGreater(spread, 0.3)
        self.assertLess(spread, 0.4)

    def test_high_spread(self):
        """[0.0, 1.0] has spread = 0.5."""
        self.assertAlmostEqual(_compute_signal_spread([0.0, 1.0]), 0.5)


class TestAdaptiveWeights(unittest.TestCase):
    """Test _compute_adaptive_weights behavior under various conditions."""

    BASE = dict(base_semantic=0.55, base_recency=0.15,
                base_importance=0.20, base_access=0.10)

    def test_weights_sum_preserved(self):
        """Total weight must equal base total regardless of degeneration."""
        base_total = sum(self.BASE.values())
        # Degenerate case
        result = _compute_adaptive_weights(
            [0.99] * 100, [0.5] * 100, **self.BASE)
        sem, rec, imp, acc = result[:4]
        self.assertAlmostEqual(sem + rec + imp + acc, base_total, places=5)

        # Informative case
        result2 = _compute_adaptive_weights(
            [0.1 * i for i in range(10)],
            [0.1 * i for i in range(10)],
            **self.BASE)
        sem2, rec2, imp2, acc2 = result2[:4]
        self.assertAlmostEqual(sem2 + rec2 + imp2 + acc2, base_total, places=5)

    def test_recency_degenerate_boosts_semantic(self):
        """When recency spread is near-zero, semantic weight increases."""
        result = _compute_adaptive_weights(
            [0.99] * 100,  # All recencies ~identical
            [0.1 * i for i in range(10)],  # Semantic has spread
            **self.BASE)
        sem, rec, imp, acc = result[:4]
        self.assertGreater(sem, self.BASE['base_semantic'])
        self.assertLess(rec, self.BASE['base_recency'])

    def test_fully_degenerate_maximizes_semantic(self):
        """When both recency AND semantic are degenerate, semantic gets maximum boost."""
        result = _compute_adaptive_weights(
            [0.99] * 100,  # Recency: degenerate
            [0.50] * 100,  # Semantic: degenerate (fixed values)
            **self.BASE)
        sem, rec, imp, acc = result[:4]
        # Semantic should get most weight
        self.assertGreater(sem, 0.80)
        # Importance should be reduced
        self.assertLess(imp, self.BASE['base_importance'])

    def test_informative_preserves_weights(self):
        """When both signals are informative, weights stay near base."""
        result = _compute_adaptive_weights(
            [0.1 * i for i in range(10)],  # Recency: high spread
            [0.1 * i for i in range(10)],  # Semantic: high spread
            **self.BASE)
        sem, rec, imp, acc = result[:4]
        self.assertAlmostEqual(sem, self.BASE['base_semantic'], delta=0.02)
        self.assertAlmostEqual(rec, self.BASE['base_recency'], delta=0.02)

    def test_type_bonus_dampened_when_degenerate(self):
        """Type bonus dampening < 1.0 when signals degenerate."""
        result = _compute_adaptive_weights(
            [0.99] * 100, [0.50] * 100, **self.BASE)
        type_dampening = result[4]
        self.assertLess(type_dampening, 0.5)  # Should be well below 1.0

    def test_type_bonus_full_when_informative(self):
        """Type bonus dampening ≈ 1.0 when signals are informative."""
        result = _compute_adaptive_weights(
            [0.1 * i for i in range(10)],
            [0.1 * i for i in range(10)],
            **self.BASE)
        type_dampening = result[4]
        self.assertGreater(type_dampening, 0.8)


class TestScoringInvariants(unittest.TestCase):
    """Integration-level scoring invariant tests using synthetic candidates."""

    def _make_candidate(self, sim, importance, mem_type, days_old=1,
                        access_count=0, reinforcement_count=1,
                        headline="Test memory", is_pinned=False,
                        observation_count=0, superseded_at=None):
        """Create a synthetic candidate dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": "test-%s-%s" % (mem_type, sim),
            "headline": headline,
            "context": "",
            "full_content": "",
            "memory_type": mem_type,
            "importance": importance,
            "access_count": access_count,
            "reinforcement_count": reinforcement_count,
            "created_at": now - timedelta(days=days_old),
            "superseded_at": superseded_at,
            "similarity": sim,
            "is_pinned": is_pinned,
            "observation_count": observation_count,
            "strategy": "vector",
        }

    def _score_candidates(self, candidates, half_life_days=3):
        """Score candidates using the adaptive formula."""
        now = datetime.now(timezone.utc)

        # Compute raw recencies
        raw_recencies = []
        for c in candidates:
            days_since = (now - c["created_at"]).total_seconds() / 86400
            raw_recencies.append(math.exp(-0.693 * days_since / max(half_life_days, 0.01)))

        raw_semantics = [c["similarity"] for c in candidates]

        adaptive = _compute_adaptive_weights(
            raw_recencies, raw_semantics,
            base_semantic=0.55, base_recency=0.15,
            base_importance=0.20, base_access=0.10)
        a_sem, a_rec, a_imp, a_acc, type_dampen = adaptive[:5]

        scored = []
        for idx, c in enumerate(candidates):
            if c.get("superseded_at"):
                continue
            sim = c["similarity"]
            rec = raw_recencies[idx]
            days_since = (now - c["created_at"]).total_seconds() / 86400

            imp = c["importance"] * (1 + 0.1 * min(c["reinforcement_count"], 5))
            imp = min(imp, 1.0)
            acc = min(c["access_count"] / 10, 1.0)

            composite = (a_sem * sim + a_rec * rec + a_imp * imp + a_acc * acc)

            # Type bonus (dampened)
            type_mult = 1.0
            if c["memory_type"] == "identity":
                type_mult = 1.15
            elif c["memory_type"] == "correction":
                type_mult = 1.10
            elif c["memory_type"] == "preference":
                type_mult = 1.15
            elif c["memory_type"] == "decision" and days_since < 7:
                type_mult = 1.2
            elif c["memory_type"] == "synthesis":
                type_mult = 1.15
            elif c["memory_type"] == "pattern":
                pattern_boost = 1.2
                if c.get("observation_count", 0) >= 5:
                    pattern_boost *= 1.1
                if days_since < 3:
                    pattern_boost *= 1.15
                type_mult = pattern_boost

            dampened = 1.0 + (type_mult - 1.0) * type_dampen
            composite *= dampened

            if c.get("is_pinned"):
                composite *= 2.0

            scored.append({**c, "composite": composite})

        scored.sort(key=lambda x: x["composite"], reverse=True)
        return scored

    # --- INVARIANT 1: Relevant beats irrelevant ---

    def test_high_semantic_beats_low_semantic(self):
        """A memory with high semantic similarity outranks one with low."""
        relevant = self._make_candidate(sim=0.85, importance=0.5, mem_type="fact")
        irrelevant = self._make_candidate(sim=0.20, importance=0.5, mem_type="fact")
        scored = self._score_candidates([relevant, irrelevant])
        self.assertEqual(scored[0]["id"], relevant["id"])

    def test_high_semantic_beats_high_importance(self):
        """Semantic relevance beats high importance when semantically distant."""
        relevant = self._make_candidate(sim=0.85, importance=0.3, mem_type="fact")
        high_imp = self._make_candidate(sim=0.20, importance=1.0, mem_type="fact")
        scored = self._score_candidates([relevant, high_imp])
        self.assertEqual(scored[0]["id"], relevant["id"])

    # --- INVARIANT 2: Recency flattening doesn't produce query-invariant ranking ---

    def test_batch_ingestion_semantic_dominates(self):
        """With all same timestamps, ranking is determined by semantic similarity."""
        candidates = [
            self._make_candidate(sim=0.9, importance=0.5, mem_type="fact", days_old=1),
            self._make_candidate(sim=0.7, importance=0.5, mem_type="fact", days_old=1),
            self._make_candidate(sim=0.3, importance=0.5, mem_type="fact", days_old=1),
        ]
        scored = self._score_candidates(candidates)
        # Order should follow semantic similarity
        self.assertGreater(scored[0]["composite"], scored[1]["composite"])
        self.assertGreater(scored[1]["composite"], scored[2]["composite"])
        # The highest semantic should be rank 1
        self.assertAlmostEqual(scored[0]["similarity"], 0.9, places=1)

    def test_batch_ingestion_different_queries(self):
        """Two different 'queries' (different sim patterns) with batch timestamps
        produce different rankings (not query-invariant)."""
        # Query A: favors candidate 1
        candidates_a = [
            self._make_candidate(sim=0.9, importance=0.5, mem_type="fact", days_old=1,
                                headline="Query A relevant"),
            self._make_candidate(sim=0.2, importance=0.8, mem_type="identity", days_old=1,
                                headline="Query A irrelevant"),
        ]
        scored_a = self._score_candidates(candidates_a)
        self.assertEqual(scored_a[0]["headline"], "Query A relevant")

        # Query B: favors candidate 2
        candidates_b = [
            self._make_candidate(sim=0.2, importance=0.5, mem_type="fact", days_old=1,
                                headline="Query B irrelevant"),
            self._make_candidate(sim=0.9, importance=0.8, mem_type="identity", days_old=1,
                                headline="Query B relevant"),
        ]
        scored_b = self._score_candidates(candidates_b)
        self.assertEqual(scored_b[0]["headline"], "Query B relevant")

    # --- INVARIANT 3: Type bonuses don't override strong semantic ---

    def test_type_bonus_cant_override_semantic_gap(self):
        """A fact with high semantic beats an identity with low semantic,
        even though identity has a 1.15x type bonus."""
        high_sem_fact = self._make_candidate(
            sim=0.85, importance=0.5, mem_type="fact")
        low_sem_identity = self._make_candidate(
            sim=0.30, importance=0.5, mem_type="identity")
        scored = self._score_candidates([high_sem_fact, low_sem_identity])
        self.assertEqual(scored[0]["id"], high_sem_fact["id"])

    def test_type_bonus_works_within_tier(self):
        """Within same semantic tier, type bonus should re-rank
        (identity above fact when similarity is similar)."""
        fact = self._make_candidate(
            sim=0.60, importance=0.5, mem_type="fact", days_old=0.5)
        identity = self._make_candidate(
            sim=0.60, importance=0.5, mem_type="identity", days_old=0.5)
        scored = self._score_candidates([fact, identity])
        # Identity should rank above fact due to type bonus
        self.assertEqual(scored[0]["memory_type"], "identity")

    def test_decision_bonus_with_batch_ingestion(self):
        """Decision bonus doesn't override semantically superior memory
        when all timestamps are identical."""
        high_sem = self._make_candidate(
            sim=0.85, importance=0.5, mem_type="fact", days_old=1)
        decision = self._make_candidate(
            sim=0.30, importance=0.8, mem_type="decision", days_old=1)
        scored = self._score_candidates([high_sem, decision])
        self.assertEqual(scored[0]["id"], high_sem["id"])

    # --- INVARIANT 4: Scale stability ---

    def test_adding_irrelevant_doesnt_change_top_rank(self):
        """Adding low-similarity candidates shouldn't change who's #1."""
        relevant = self._make_candidate(sim=0.9, importance=0.5, mem_type="fact")
        medium = self._make_candidate(sim=0.5, importance=0.5, mem_type="fact")

        # Without noise
        scored_clean = self._score_candidates([relevant, medium])
        top_clean = scored_clean[0]["id"]

        # With 50 irrelevant candidates added
        noise = [self._make_candidate(sim=0.1 + i * 0.005, importance=0.3,
                                      mem_type="fact", days_old=1)
                 for i in range(50)]
        scored_noisy = self._score_candidates([relevant, medium] + noise)
        top_noisy = scored_noisy[0]["id"]

        self.assertEqual(top_clean, top_noisy)

    def test_scale_100_vs_10_candidates(self):
        """Relative ordering of top candidates preserved at larger scale."""
        top3 = [
            self._make_candidate(sim=0.9, importance=0.5, mem_type="fact",
                                headline="A"),
            self._make_candidate(sim=0.7, importance=0.5, mem_type="fact",
                                headline="B"),
            self._make_candidate(sim=0.5, importance=0.5, mem_type="fact",
                                headline="C"),
        ]

        # 10 candidates
        small = top3 + [
            self._make_candidate(sim=0.1 + i*0.03, importance=0.3, mem_type="fact")
            for i in range(7)
        ]
        scored_small = self._score_candidates(small)

        # 100 candidates
        big = top3 + [
            self._make_candidate(sim=0.1 + i*0.003, importance=0.3, mem_type="fact")
            for i in range(97)
        ]
        scored_big = self._score_candidates(big)

        # Top 3 order preserved
        for i in range(3):
            self.assertEqual(scored_small[i]["headline"], scored_big[i]["headline"])

    # --- INVARIANT 5: Batch vs trickle equivalence ---

    def test_batch_vs_trickle_semantic_order_preserved(self):
        """Whether memories arrive in batch (same timestamp) or trickle
        (spread timestamps), the top result by semantic should stay on top."""
        # Batch: all same day
        batch = [
            self._make_candidate(sim=0.9, importance=0.5, mem_type="fact",
                                days_old=1, headline="target"),
            self._make_candidate(sim=0.3, importance=0.8, mem_type="identity",
                                days_old=1, headline="noise"),
        ]
        scored_batch = self._score_candidates(batch)

        # Trickle: spread over days
        trickle = [
            self._make_candidate(sim=0.9, importance=0.5, mem_type="fact",
                                days_old=2, headline="target"),
            self._make_candidate(sim=0.3, importance=0.8, mem_type="identity",
                                days_old=0.5, headline="noise"),
        ]
        scored_trickle = self._score_candidates(trickle)

        # The high-semantic memory should be rank 1 in both cases
        self.assertEqual(scored_batch[0]["headline"], "target")
        self.assertEqual(scored_trickle[0]["headline"], "target")

    # --- INVARIANT 6: Pinned always wins ---

    def test_pinned_beats_everything(self):
        """Pinned memory always ranks above unpinned."""
        unpinned = self._make_candidate(sim=0.9, importance=1.0, mem_type="identity")
        pinned = self._make_candidate(sim=0.5, importance=0.5, mem_type="fact",
                                      is_pinned=True)
        scored = self._score_candidates([unpinned, pinned])
        self.assertTrue(scored[0]["is_pinned"])

    # --- INVARIANT 7: Superseded excluded ---

    def test_superseded_excluded(self):
        """Superseded memories don't appear in scored results."""
        active = self._make_candidate(sim=0.5, importance=0.5, mem_type="fact")
        superseded = self._make_candidate(sim=0.9, importance=0.9, mem_type="fact",
                                          superseded_at=datetime.now(timezone.utc))
        scored = self._score_candidates([active, superseded])
        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0]["id"], active["id"])

    # --- INVARIANT 8: Mixed strategy candidates ---

    def test_fixed_similarity_candidates_rank_below_real(self):
        """Candidates with placeholder similarity (0.5 from importance strategy)
        should rank below candidates with high real similarity."""
        real_relevant = self._make_candidate(sim=0.85, importance=0.5, mem_type="fact")
        placeholder = self._make_candidate(sim=0.50, importance=0.9, mem_type="identity")
        scored = self._score_candidates([real_relevant, placeholder])
        self.assertEqual(scored[0]["id"], real_relevant["id"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
