"""Unit tests for the consensus orchestrator (Stage 03)."""
from unittest.mock import MagicMock, patch
import pytest
from src.synthesis.consensus import (
    gather_agent_ids_from_cluster,
    select_consensus_agents,
    run_consensus,
    CONSENSUS_AGENT_COUNT,
)


def test_select_consensus_agents_deterministic():
    """Selection is alphabetical, first N."""
    agents = ['zeta', 'alpha', 'mu', 'beta', 'omega']
    selected = select_consensus_agents(agents, n_wanted=3)
    assert selected == ['alpha', 'beta', 'mu']


def test_select_consensus_agents_fewer_than_wanted():
    """Returns however many are available when fewer than N."""
    agents = ['alpha', 'beta']
    selected = select_consensus_agents(agents, n_wanted=3)
    assert selected == ['alpha', 'beta']


def test_gather_agent_ids_from_empty_cluster():
    """Empty cluster returns empty list without DB hit."""
    fake_db = MagicMock()
    result = gather_agent_ids_from_cluster([], fake_db)
    assert result == []
    fake_db.cursor.assert_not_called()


def test_run_consensus_skips_when_only_one_agent():
    """<2 distinct agents → consensus_eligible=False with skip audit."""
    fake_db = MagicMock()
    fake_cur = MagicMock()
    fake_db.cursor.return_value = fake_cur
    fake_cur.fetchall.return_value = [('only-agent',)]

    with patch('src.synthesis.consensus._write_audit_event') as mock_audit:
        result = run_consensus(
            tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
            cluster_id='test-cluster-1',
            cluster_memory_ids=['00000000-0000-0000-0000-000000000001'],
            role_tag='public',
            db_conn=fake_db,
        )
        assert result['consensus_eligible'] is False
        assert 'only_1_distinct_agents' in result['fallback_reason']
        # Verify the skip audit fired
        audit_calls = [c.kwargs.get('event_type') for c in mock_audit.call_args_list]
        assert 'consensus_skipped_insufficient_agents' in audit_calls


def test_run_consensus_continues_on_per_candidate_failure():
    """If one writer call raises, the others still run; <2 succeeding triggers fallback."""
    fake_db = MagicMock()
    fake_cur = MagicMock()
    fake_db.cursor.return_value = fake_cur
    fake_cur.fetchall.return_value = [('agent-a',), ('agent-b',), ('agent-c',)]

    call_count = [0]
    def flaky_writer(**kwargs):
        call_count[0] += 1
        if kwargs['agent_id'] in ('agent-a', 'agent-b'):
            raise RuntimeError(f"simulated LLM failure for {kwargs['agent_id']}")
        return {
            'agent_id': kwargs['agent_id'],
            'headline': 'h', 'context': 'c', 'full_content': 'f',
            'source_memory_ids': [], 'parent_memory_ids': [],
            'role_tag': kwargs['role_tag'], 'cluster_id': kwargs.get('cluster_id', 'test-cluster-2'),
            'tokens_used': 10,
        }

    with patch('src.synthesis.consensus.synthesize_cluster', side_effect=flaky_writer):
        with patch('src.synthesis.consensus._write_audit_event'):
            result = run_consensus(
                tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
                cluster_id='test-cluster-2',
                cluster_memory_ids=['00000000-0000-0000-0000-000000000001'],
                role_tag='public',
                db_conn=fake_db,
            )
    assert call_count[0] == 3
    assert result['consensus_eligible'] is False
    assert 'only_1_candidates_succeeded' in result['fallback_reason']
    assert result['agents_succeeded'] == ['agent-c']


def test_run_consensus_eligible_when_2_plus_succeed():
    """≥2 successful candidates → consensus_eligible=True."""
    fake_db = MagicMock()
    fake_cur = MagicMock()
    fake_db.cursor.return_value = fake_cur
    fake_cur.fetchall.return_value = [('agent-a',), ('agent-b',), ('agent-c',)]

    def ok_writer(**kwargs):
        return {
            'agent_id': kwargs['agent_id'],
            'headline': f"h-{kwargs['agent_id']}", 'context': 'c', 'full_content': 'f',
            'source_memory_ids': [], 'parent_memory_ids': [],
            'role_tag': kwargs['role_tag'], 'cluster_id': kwargs.get('cluster_id', 'test-cluster-3'),
            'tokens_used': 10,
        }

    with patch('src.synthesis.consensus.synthesize_cluster', side_effect=ok_writer):
        with patch('src.synthesis.consensus._write_audit_event'):
            result = run_consensus(
                tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
                cluster_id='test-cluster-3',
                cluster_memory_ids=['00000000-0000-0000-0000-000000000001'],
                role_tag='public',
                db_conn=fake_db,
            )
    assert result['consensus_eligible'] is True
    assert len(result['candidates']) == 3
    assert set(result['agents_succeeded']) == {'agent-a', 'agent-b', 'agent-c'}
