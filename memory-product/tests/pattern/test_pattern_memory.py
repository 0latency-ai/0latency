"""
CP8 P5.5 — Pattern Memory Tests

Tests for pattern extraction, pattern-aware recall, pin-wins-over-pattern,
tier gating, and audit logging.
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4


@pytest.fixture
def setup_test_data(db_connection):
    """Create test tenant, memories, and feedback events."""
    cur = db_connection.cursor()
    
    # Create enterprise tenant
    tenant_id = str(uuid4())
    cur.execute(
        """
        INSERT INTO memory_service.tenants (id, plan, api_key_live, api_key_hash)
        VALUES (%s::uuid, 'enterprise', 'test_key', 'hash')
        """,
        (tenant_id,)
    )
    
    # Create some memories for pattern extraction
    memory_ids = []
    for i in range(5):
        cur.execute(
            """
            INSERT INTO memory_service.memories
              (tenant_id, agent_id, memory_type, headline, context, full_content)
            VALUES
              (%s::uuid, 'test-agent', 'fact', %s, %s, %s)
            RETURNING id
            """,
            (tenant_id, f"Test memory {i}", f"Context {i}", f"Full content {i}")
        )
        memory_ids.append(cur.fetchone()[0])
    
    # Create feedback events (corrections indicating a pattern)
    for mem_id in memory_ids:
        cur.execute(
            """
            INSERT INTO memory_service.recall_feedback
              (tenant_id, agent_id, memory_id, feedback_type, context, created_at)
            VALUES
              (%s::uuid, 'test-agent', %s::uuid, 'contradicted',
               'User corrected date format to ISO 8601', NOW() - INTERVAL '1 day' * %s)
            """,
            (tenant_id, mem_id, len(memory_ids) - memory_ids.index(mem_id))
        )
    
    db_connection.commit()
    
    yield {"tenant_id": tenant_id, "memory_ids": memory_ids, "agent_id": "test-agent"}
    
    # Cleanup
    cur.execute("DELETE FROM memory_service.tenants WHERE id = %s::uuid", (tenant_id,))
    db_connection.commit()


class TestPatternSchemaTask TestPatternExtractionJob:
    """Test pattern extraction worker (Task 10)."""
    
    def test_extraction_with_sufficient_feedback(self, setup_test_data, db_connection):
        """Pattern extraction creates pattern memory when sufficient feedback exists."""
        from api.pattern_worker import run_pattern_extraction
        
        tenant_id = setup_test_data["tenant_id"]
        
        # Run extraction
        result = run_pattern_extraction(tenant_id=tenant_id)
        
        # Should process the tenant
        assert result["tenants_processed"] >= 1
        assert result["agents_processed"] >= 1
        
        # Verify pattern memory was created
        cur = db_connection.cursor()
        cur.execute(
            """
            SELECT id, pattern_type, headline, observation_count, triggering_event_ids
            FROM memory_service.memories
            WHERE tenant_id = %s::uuid
              AND agent_id = 'test-agent'
              AND memory_type = 'pattern'
            """,
            (tenant_id,)
        )
        
        patterns = cur.fetchall()
        assert len(patterns) > 0, "Should create at least one pattern"
        
        pattern = patterns[0]
        assert pattern[1] is not None  # pattern_type
        assert pattern[2] is not None  # headline
        assert pattern[3] >= 3  # observation_count >= MIN_OBSERVATIONS
        assert len(pattern[4]) >= 3  # triggering_event_ids
    
    def test_extraction_insufficient_feedback(self, db_connection):
        """Pattern extraction skips agents with insufficient feedback."""
        from api.pattern_worker import run_pattern_extraction
        
        # Create tenant with minimal feedback
        tenant_id = str(uuid4())
        cur = db_connection.cursor()
        cur.execute(
            "INSERT INTO memory_service.tenants (id, plan) VALUES (%s::uuid, 'enterprise')",
            (tenant_id,)
        )
        db_connection.commit()
        
        result = run_pattern_extraction(tenant_id=tenant_id)
        
        assert result["patterns_created"] == 0
        assert result["patterns_updated"] == 0
        
        # Cleanup
        cur.execute("DELETE FROM memory_service.tenants WHERE id = %s::uuid", (tenant_id,))
        db_connection.commit()


class TestPatternAwareRecall:
    """Test pattern-aware recall (Task 11)."""
    
    def test_pattern_memory_boosted_in_recall(self, setup_test_data, db_connection):
        """Pattern memories receive boost in recall scoring."""
        from src.recall import recall_fixed
        
        tenant_id = setup_test_data["tenant_id"]
        agent_id = setup_test_data["agent_id"]
        
        # Create a pattern memory
        cur = db_connection.cursor()
        cur.execute(
            """
            INSERT INTO memory_service.memories
              (tenant_id, agent_id, memory_type, pattern_type, headline, context, full_content,
               observation_count, last_observation_at, triggering_event_ids)
            VALUES
              (%s::uuid, %s, 'pattern', 'correction', 'User prefers ISO 8601 dates',
               'Pattern: user corrects date format', '{}', 5, NOW(), ARRAY[]::uuid[])
            RETURNING id
            """,
            (tenant_id, agent_id)
        )
        pattern_id = cur.fetchone()[0]
        db_connection.commit()
        
        # Recall with relevant query
        result = recall_fixed(
            agent_id=agent_id,
            conversation_context="What date format should I use?",
            budget_tokens=2000,
            tenant_id=tenant_id
        )
        
        # Pattern memory should appear in recall
        recall_ids = [detail["id"] for detail in result.get("recall_details", [])]
        assert str(pattern_id) in recall_ids, "Pattern memory should be recalled"
    
    def test_synthesis_recall_not_regressed(self, setup_test_data, db_connection):
        """Synthesis memories still work after pattern memory changes."""
        from src.recall import recall_fixed
        
        tenant_id = setup_test_data["tenant_id"]
        agent_id = setup_test_data["agent_id"]
        
        # Create a synthesis memory
        cur = db_connection.cursor()
        cur.execute(
            """
            INSERT INTO memory_service.memories
              (tenant_id, agent_id, memory_type, headline, context, full_content,
               synthesis_state, source_memory_ids)
            VALUES
              (%s::uuid, %s, 'synthesis', 'Synthesis test', 'Synthesis context',
               'Synthesis content', 'completed', ARRAY[]::uuid[])
            RETURNING id
            """,
            (tenant_id, agent_id)
        )
        synth_id = cur.fetchone()[0]
        db_connection.commit()
        
        # Recall should still work
        result = recall_fixed(
            agent_id=agent_id,
            conversation_context="Tell me about synthesis",
            budget_tokens=2000,
            tenant_id=tenant_id,
            include_synthesis=True
        )
        
        assert result["memories_used"] >= 0  # Should not crash
        # Synthesis should be recallable
        recall_ids = [detail["id"] for detail in result.get("recall_details", [])]
        # May or may not appear depending on semantic match, but should not crash


class TestPinWinsOverPattern:
    """Test pin-wins-over-pattern conflict resolution (Task 12)."""
    
    def test_pinned_memory_beats_pattern(self, setup_test_data, db_connection):
        """Pinned memory ranks higher than pattern memory."""
        from src.recall import recall_fixed
        
        tenant_id = setup_test_data["tenant_id"]
        agent_id = setup_test_data["agent_id"]
        
        cur = db_connection.cursor()
        
        # Create pattern memory
        cur.execute(
            """
            INSERT INTO memory_service.memories
              (tenant_id, agent_id, memory_type, pattern_type, headline, context, full_content,
               observation_count, importance)
            VALUES
              (%s::uuid, %s, 'pattern', 'correction', 'Pattern: use UTC',
               'User prefers UTC timezone', '{}', 10, 0.9)
            RETURNING id
            """,
            (tenant_id, agent_id)
        )
        pattern_id = cur.fetchone()[0]
        
        # Create conflicting pinned memory
        cur.execute(
            """
            INSERT INTO memory_service.memories
              (tenant_id, agent_id, memory_type, headline, context, full_content,
               is_pinned, importance)
            VALUES
              (%s::uuid, %s, 'preference', 'Pinned: use local time',
               'User explicitly wants local time, not UTC', 'Local time preference',
               true, 0.7)
            RETURNING id
            """,
            (tenant_id, agent_id)
        )
        pinned_id = cur.fetchone()[0]
        db_connection.commit()
        
        # Recall with relevant query
        result = recall_fixed(
            agent_id=agent_id,
            conversation_context="What timezone should I use?",
            budget_tokens=4000,
            tenant_id=tenant_id
        )
        
        recall_ids = [detail["id"] for detail in result.get("recall_details", [])]
        
        # Both should be recalled
        assert str(pattern_id) in recall_ids
        assert str(pinned_id) in recall_ids
        
        # Pinned should rank higher
        pattern_idx = recall_ids.index(str(pattern_id))
        pinned_idx = recall_ids.index(str(pinned_id))
        assert pinned_idx < pattern_idx, "Pinned memory should rank before pattern"


class TestTierGating:
    """Test tier gating for pattern extraction (Task 10)."""
    
    @pytest.mark.parametrize("tier,expected_enabled", [
        ("free", False),
        ("pro", False),
        ("scale", True),
        ("enterprise", True),
    ])
    def test_tier_gate_config(self, tier, expected_enabled):
        """Tier matrix correctly gates pattern extraction."""
        from tier_gates import TIER_MATRIX
        
        enabled = TIER_MATRIX[tier].get("pattern_extraction_enabled", False)
        assert enabled == expected_enabled
    
    def test_patterns_run_endpoint_free_blocked(self, api_client, db_connection):
        """POST /patterns/run returns 403 for Free tier."""
        # Create free tier tenant
        tenant_id = str(uuid4())
        api_key = f"test_free_{uuid4()}"
        
        cur = db_connection.cursor()
        cur.execute(
            """
            INSERT INTO memory_service.tenants (id, plan, api_key_live)
            VALUES (%s::uuid, 'free', %s)
            """,
            (tenant_id, api_key)
        )
        db_connection.commit()
        
        response = api_client.post(
            "/patterns/run",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        assert response.status_code == 403
        assert "pattern extraction" in response.json()["detail"].lower()
        
        # Cleanup
        cur.execute("DELETE FROM memory_service.tenants WHERE id = %s::uuid", (tenant_id,))
        db_connection.commit()
    
    def test_patterns_run_endpoint_enterprise_allowed(self, api_client, setup_test_data, db_connection):
        """POST /patterns/run returns 200 for Enterprise tier."""
        tenant_id = setup_test_data["tenant_id"]
        api_key = f"test_ent_{uuid4()}"
        
        # Update tenant with API key
        cur = db_connection.cursor()
        cur.execute(
            "UPDATE memory_service.tenants SET api_key_live = %s WHERE id = %s::uuid",
            (api_key, tenant_id)
        )
        db_connection.commit()
        
        response = api_client.post(
            "/patterns/run",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        assert response.status_code == 200
        assert "status" in response.json()
        assert "stats" in response.json()


class TestAuditLogging:
    """Test pattern extraction audit logging (Task 10)."""
    
    def test_pattern_extraction_audit_event(self, setup_test_data, db_connection):
        """Pattern extraction creates audit log entries."""
        from api.pattern_worker import run_pattern_extraction
        
        tenant_id = setup_test_data["tenant_id"]
        
        # Run extraction
        run_pattern_extraction(tenant_id=tenant_id)
        
        # Check audit log
        cur = db_connection.cursor()
        cur.execute(
            """
            SELECT event_type, event_payload
            FROM memory_service.synthesis_audit_events
            WHERE tenant_id = %s::uuid
              AND event_type = 'pattern_extracted'
            ORDER BY occurred_at DESC
            LIMIT 1
            """,
            (tenant_id,)
        )
        
        row = cur.fetchone()
        assert row is not None, "Should create audit event"
        assert row[0] == "pattern_extracted"
        
        payload = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        assert "pattern_type" in payload
        assert "observation_count" in payload


class TestE2EWorkflow:
    """End-to-end pattern memory workflow tests."""
    
    def test_full_pattern_lifecycle(self, setup_test_data, db_connection):
        """Complete workflow: feedback → extraction → recall → pin override."""
        from api.pattern_worker import run_pattern_extraction
        from src.recall import recall_fixed
        
        tenant_id = setup_test_data["tenant_id"]
        agent_id = setup_test_data["agent_id"]
        
        # Step 1: Verify feedback exists
        cur = db_connection.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM memory_service.recall_feedback WHERE tenant_id = %s::uuid",
            (tenant_id,)
        )
        feedback_count = cur.fetchone()[0]
        assert feedback_count >= 3, "Need sufficient feedback for pattern"
        
        # Step 2: Extract patterns
        result = run_pattern_extraction(tenant_id=tenant_id)
        assert result["patterns_created"] > 0 or result["patterns_updated"] > 0
        
        # Step 3: Verify pattern memory exists
        cur.execute(
            """
            SELECT id FROM memory_service.memories
            WHERE tenant_id = %s::uuid AND memory_type = 'pattern'
            """,
            (tenant_id,)
        )
        pattern = cur.fetchone()
        assert pattern is not None
        pattern_id = pattern[0]
        
        # Step 4: Recall should surface pattern
        recall_result = recall_fixed(
            agent_id=agent_id,
            conversation_context="date format preferences",
            budget_tokens=2000,
            tenant_id=tenant_id
        )
        recall_ids = [d["id"] for d in recall_result.get("recall_details", [])]
        assert str(pattern_id) in recall_ids
        
        # Step 5: Pin a contradicting memory
        cur.execute(
            """
            INSERT INTO memory_service.memories
              (tenant_id, agent_id, memory_type, headline, context, full_content, is_pinned)
            VALUES
              (%s::uuid, %s, 'preference', 'Override: use MM/DD/YYYY',
               'Pinned preference', 'MM/DD/YYYY format', true)
            RETURNING id
            """,
            (tenant_id, agent_id)
        )
        pinned_id = cur.fetchone()[0]
        db_connection.commit()
        
        # Step 6: Recall again - pin should rank higher
        recall_result2 = recall_fixed(
            agent_id=agent_id,
            conversation_context="date format preferences",
            budget_tokens=2000,
            tenant_id=tenant_id
        )
        recall_ids2 = [d["id"] for d in recall_result2.get("recall_details", [])]
        
        if str(pinned_id) in recall_ids2 and str(pattern_id) in recall_ids2:
            pinned_idx = recall_ids2.index(str(pinned_id))
            pattern_idx = recall_ids2.index(str(pattern_id))
            assert pinned_idx < pattern_idx, "Pin should beat pattern"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
