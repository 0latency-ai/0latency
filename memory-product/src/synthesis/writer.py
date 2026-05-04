"""
CP8 Phase 2 Task 2 — Synthesis Writer (synchronous, single-agent)

End-to-end synthesis path: cluster → LLM → validate → write.

Key design decisions:
- Synchronous by design (T4's jobs module wraps this for async lifecycle)
- Source-quote validation via callback (T3 plugs in the implementation)
- dry_run flag for T5's preview-impact use case
- Rate-limit pre-flight + post-flight increment pattern
- Decision 1: source_memory_ids (evidence chain) vs parent_memory_ids (cluster edge)
  - source_memory_ids (uuid[] column): only IDs the LLM cited
  - metadata.parent_memory_ids (jsonb): every atom in the cluster
"""

import os
import json
import hashlib
import time
import logging
import requests
from dataclasses import dataclass
from typing import Optional, Callable
from uuid import UUID, uuid4

# Import from existing modules
from src.storage_multitenant import (
    _db_execute_rows,
    _get_connection_pool,
    _embed_text,
    set_tenant_context,
)
from src.tier_gates import (
    check_synthesis_quota,
    increment_synthesis_counter,
    get_allowed_model,
)
from src.synthesis.clustering import Cluster

# Performance profiling logger
perf_logger = logging.getLogger("synthesis.perf")


# ============================================================
# Dataclasses
# ============================================================

@dataclass
class ValidationResult:
    """Result from source-quote validation callback (T3 implements)."""
    valid: bool
    cited_ids_in_source_set: list[UUID]
    cited_ids_NOT_in_source_set: list[UUID]  # hallucinations
    failure_reason: Optional[str]


@dataclass
class SynthesisResult:
    """Result from a synthesis attempt."""
    success: bool
    synthesis_id: Optional[UUID]
    audit_event_id: Optional[UUID]
    cluster_size: int
    source_memory_ids: list[UUID]      # what the LLM cited (evidence chain)
    parent_memory_ids: list[UUID]      # full cluster (cluster edge)
    tokens_used: int
    llm_model: str
    rejected_reason: Optional[str]     # rate_limited | validation_failed | empty_cluster | llm_error
    dry_run: bool


# ============================================================
# Helper functions
# ============================================================

def _anthropic_key() -> str:
    """Get Anthropic API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key.strip('"\'')


def _load_prompt_template(version: str) -> str:
    """Load prompt template from file."""
    import pathlib
    template_path = pathlib.Path(__file__).parent / "prompts" / f"{version}.txt"
    with open(template_path, "r") as f:
        return f.read()


def _call_anthropic(prompt: str, model: str) -> tuple[str, int, int]:
    """
    Call Anthropic API and return (response_text, input_tokens, output_tokens).

    Args:
        prompt: The prompt to send
        model: Anthropic model ID (e.g., "claude-haiku-4-5-20251001")

    Returns:
        Tuple of (response_text, input_tokens, output_tokens)

    Raises:
        RuntimeError: If API call fails
    """
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": _anthropic_key(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    body = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()

        result = resp.json()
        text = result["content"][0]["text"]
        input_tokens = result["usage"]["input_tokens"]
        output_tokens = result["usage"]["output_tokens"]

        return (text, input_tokens, output_tokens)
    except Exception as e:
        raise RuntimeError(f"Anthropic API call failed: {e}")


def _parse_llm_response(response_text: str) -> dict:
    """
    Parse LLM JSON response, handling markdown fences.

    Returns:
        Dict with keys: headline, synthesis, cited_atom_ids

    Raises:
        ValueError: If JSON is invalid or missing required fields
    """
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from LLM: {e}")

    # Validate required fields
    if "headline" not in data or "synthesis" not in data or "cited_atom_ids" not in data:
        raise ValueError(f"Missing required fields in LLM response: {data.keys()}")

    return data


def _compute_cluster_hash(memory_ids: list[UUID]) -> str:
    """Compute deterministic hash of cluster IDs for audit trail."""
    # Sort IDs to ensure deterministic hash
    sorted_ids = sorted(str(id) for id in memory_ids)
    combined = ",".join(sorted_ids)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


# ============================================================
# Main synthesis function
# ============================================================

def synthesize_cluster(
    cluster: Cluster,
    tenant_id: str,
    agent_id: str,
    role_tag: str = "public",
    prompt_version: str = "single_agent_v1",
    llm_model: Optional[str] = None,
    validate_callback: Optional[Callable[[str, list[UUID]], ValidationResult]] = None,
    dry_run: bool = False,
) -> SynthesisResult:
    """
    Run one synthesis attempt against a single cluster.

    Sequence (atomic for accounting; writes are individually transactional):
      1. Pre-flight: tier_gates.check_synthesis_quota(tenant_id) — abort + audit if blocked
      2. Pre-flight: load atoms, separate pinned from regular, fail if cluster is empty
      3. LLM call: format prompt, call Haiku/Sonnet per tier, capture token counts
      4. Parse + schema-validate response
      5. Source-quote validation via validate_callback (T3 plugs in here)
      6. If dry_run: return SynthesisResult with would_write=True, no DB writes
      7. Write synthesis row (memory_type='synthesis')
      8. Write audit event (event_type='synthesis_written')
      9. Increment rate-limit counters
     10. Return SynthesisResult

    Args:
        cluster: Cluster object with memory_ids to synthesize
        tenant_id: Tenant UUID
        agent_id: Agent identifier
        role_tag: Role visibility tag (default: "public")
        prompt_version: Prompt template version (default: "single_agent_v1")
        llm_model: Override model (default: per-tier from tier_gates)
        validate_callback: Optional validation function (T3 supplies this)
        dry_run: If True, skip all DB writes

    Returns:
        SynthesisResult with success status and metadata
    """
    pool = _get_connection_pool()
    conn = None
    synthesis_id_for_logging = None  # Will be set if synthesis succeeds

    try:
        conn = pool.getconn()

        # ============================================================
        # STEP 1: Pre-flight quota check
        # ============================================================

        tenant_load_start = time.perf_counter()

        allowed, reason = check_synthesis_quota(
            tenant_id=tenant_id,
            kind="manual_run",  # T2 is sync, caller (T5/T6) sets the kind
            conn=conn,
            amount=1,
        )

        if not allowed:
            # Write rate_limit_blocked audit event
            if not dry_run:
                set_tenant_context(tenant_id)
                audit_event_id = _write_audit_event(
                    tenant_id=tenant_id,
                    target_memory_id=None,
                    event_type="rate_limit_blocked",
                    actor=agent_id,
                    event_payload={
                        "cluster_size": len(cluster.memory_ids),
                        "reason": reason,
                    }
                )
            else:
                audit_event_id = None

            return SynthesisResult(
                success=False,
                synthesis_id=None,
                audit_event_id=audit_event_id,
                cluster_size=len(cluster.memory_ids),
                source_memory_ids=[],
                parent_memory_ids=cluster.memory_ids,
                tokens_used=0,
                llm_model="",
                rejected_reason="rate_limited",
                dry_run=dry_run,
            )

        # ============================================================
        # STEP 2: Load atoms from cluster
        # ============================================================

        if not cluster.memory_ids:
            return SynthesisResult(
                success=False,
                synthesis_id=None,
                audit_event_id=None,
                cluster_size=0,
                source_memory_ids=[],
                parent_memory_ids=[],
                tokens_used=0,
                llm_model="",
                rejected_reason="empty_cluster",
                dry_run=dry_run,
            )

        # Load atoms from database
        set_tenant_context(tenant_id)
        ids_tuple = tuple(str(id) for id in cluster.memory_ids)
        placeholders = ",".join(["%s"] * len(ids_tuple))

        query = f"""
            SELECT id, headline, full_content, is_pinned
            FROM memory_service.memories
            WHERE id IN ({placeholders})
            AND redaction_state = 'active'
            ORDER BY created_at ASC
        """

        rows = _db_execute_rows(query, ids_tuple, tenant_id=tenant_id, fetch_results=True)

        if not rows:
            return SynthesisResult(
                success=False,
                synthesis_id=None,
                audit_event_id=None,
                cluster_size=len(cluster.memory_ids),
                source_memory_ids=[],
                parent_memory_ids=cluster.memory_ids,
                tokens_used=0,
                llm_model="",
                rejected_reason="empty_cluster",
                dry_run=dry_run,
            )

        # Build atoms block for prompt
        atoms_block = ""
        for row in rows:
            atom_id, headline, full_content, is_pinned = row
            pinned_marker = " [PINNED]" if is_pinned else ""
            atoms_block += f"[{atom_id}]{pinned_marker} {headline}: {full_content}\n\n"

        tenant_load_duration_ms = int((time.perf_counter() - tenant_load_start) * 1000)
        import json
        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "tenant_load",
            "duration_ms": tenant_load_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": None,
            "cluster_size": len(cluster.memory_ids),
        }))

        # ============================================================
        # STEP 3: LLM call
        # ============================================================

        llm_call_start = time.perf_counter()

        # Determine model
        if llm_model is None:
            tier_model = get_allowed_model(tenant_id, conn)
            if tier_model is None:
                # Free tier - should have been caught by quota check, but defensive
                return SynthesisResult(
                    success=False,
                    synthesis_id=None,
                    audit_event_id=None,
                    cluster_size=len(cluster.memory_ids),
                    source_memory_ids=[],
                    parent_memory_ids=cluster.memory_ids,
                    tokens_used=0,
                    llm_model="",
                    rejected_reason="rate_limited",
                    dry_run=dry_run,
                )
            # Map tier model to Anthropic model ID
            model_map = {
                "haiku": "claude-haiku-4-5-20251001",
                "sonnet": "claude-sonnet-4-6",
            }
            llm_model = model_map.get(tier_model, "claude-haiku-4-5-20251001")

        # Load and format prompt
        template = _load_prompt_template(prompt_version)
        prompt = template.format(
            cluster_size=len(cluster.memory_ids),
            atoms_block=atoms_block.strip(),
        )

        # Call LLM
        try:
            response_text, input_tokens, output_tokens = _call_anthropic(prompt, llm_model)
            total_tokens = input_tokens + output_tokens
        except RuntimeError as e:
            return SynthesisResult(
                success=False,
                synthesis_id=None,
                audit_event_id=None,
                cluster_size=len(cluster.memory_ids),
                source_memory_ids=[],
                parent_memory_ids=cluster.memory_ids,
                tokens_used=0,
                llm_model=llm_model,
                rejected_reason="llm_error",
                dry_run=dry_run,
            )

        # ============================================================
        # STEP 4: Parse response
        # ============================================================

        try:
            parsed = _parse_llm_response(response_text)
            headline = parsed["headline"]
            synthesis_text = parsed["synthesis"]
            cited_ids_str = parsed["cited_atom_ids"]

            # Convert cited IDs to UUIDs
            cited_ids = [UUID(id_str) for id_str in cited_ids_str]
        except (ValueError, TypeError) as e:
            return SynthesisResult(
                success=False,
                synthesis_id=None,
                audit_event_id=None,
                cluster_size=len(cluster.memory_ids),
                source_memory_ids=[],
                parent_memory_ids=cluster.memory_ids,
                tokens_used=total_tokens,
                llm_model=llm_model,
                rejected_reason="llm_error",
                dry_run=dry_run,
            )

        # ============================================================
        # STEP 5: Source-quote validation
        # ============================================================

        validation_passed = True
        validation_result = None

        if validate_callback is not None:
            validation_result = validate_callback(synthesis_text, cluster.memory_ids)
            validation_passed = validation_result.valid

            if not validation_passed:
                # Validation failed - write audit event and return
                if not dry_run:
                    audit_event_id = _write_audit_event(
                        tenant_id=tenant_id,
                        target_memory_id=None,
                        event_type="rate_limit_blocked",  # Reuse for validation failures
                        actor=agent_id,
                        event_payload={
                            "cluster_size": len(cluster.memory_ids),
                            "reason": f"validation_failed: {validation_result.failure_reason}",
                            "hallucinated_ids": [str(id) for id in validation_result.cited_ids_NOT_in_source_set],
                        }
                    )
                else:
                    audit_event_id = None

                return SynthesisResult(
                    success=False,
                    synthesis_id=None,
                    audit_event_id=audit_event_id,
                    cluster_size=len(cluster.memory_ids),
                    source_memory_ids=cited_ids,
                    parent_memory_ids=cluster.memory_ids,
                    tokens_used=total_tokens,
                    llm_model=llm_model,
                    rejected_reason="validation_failed",
                    dry_run=dry_run,
                )

        llm_call_duration_ms = int((time.perf_counter() - llm_call_start) * 1000)
        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "llm_call",
            "duration_ms": llm_call_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": None,
            "tokens_used": total_tokens,
        }))

        # ============================================================
        # STEP 6: Dry-run check
        # ============================================================

        if dry_run:
            return SynthesisResult(
                success=True,
                synthesis_id=None,
                audit_event_id=None,
                cluster_size=len(cluster.memory_ids),
                source_memory_ids=cited_ids,
                parent_memory_ids=cluster.memory_ids,
                tokens_used=total_tokens,
                llm_model=llm_model,
                rejected_reason=None,
                dry_run=True,
            )

        # ============================================================
        # STEP 7: Write synthesis row
        # ============================================================

        # Compute confidence score (initial heuristic)
        confidence_score = len(cited_ids) / len(cluster.memory_ids) if cluster.memory_ids else 0.0

        # Compute context (cluster signature)
        cluster_hash = _compute_cluster_hash(cluster.memory_ids)
        context = f"Cluster {cluster_hash} ({len(cluster.memory_ids)} atoms)"

        # Generate embedding
        embedding_start = time.perf_counter()
        embedding = _embed_text(synthesis_text)
        embedding_duration_ms = int((time.perf_counter() - embedding_start) * 1000)
        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "embedding",
            "duration_ms": embedding_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": None,
        }))

        # Insert synthesis row
        db_write_start = time.perf_counter()
        synthesis_id = uuid4()
        insert_query = """
            INSERT INTO memory_service.memories (
                id, tenant_id, agent_id, memory_type,
                headline, context, full_content,
                source_memory_ids, role_tag, redaction_state, confidence_score,
                synthesis_prompt_version, synthesis_version,
                is_pinned, embedding,
                metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s::uuid[], %s, %s, %s,
                %s, %s,
                %s, %s::vector,
                %s::jsonb
            )
        """

        metadata = {
            "parent_memory_ids": [str(id) for id in cluster.memory_ids],
        }

        params = (
            str(synthesis_id),
            tenant_id,
            agent_id,
            "synthesis",
            headline[:200],  # Truncate headline to reasonable length
            context,
            synthesis_text,
            [str(id) for id in cited_ids],  # source_memory_ids (evidence chain)
            role_tag,
            "active",
            confidence_score,
            prompt_version,
            1,  # synthesis_version
            False,  # is_pinned
            embedding,
            json.dumps(metadata),
        )

        _db_execute_rows(insert_query, params, tenant_id=tenant_id, fetch_results=False)

        # ============================================================
        # STEP 8: Write audit event
        # ============================================================

        audit_event_id = _write_audit_event(
            tenant_id=tenant_id,
            target_memory_id=synthesis_id,
            event_type="synthesis_written",
            actor=agent_id,
            event_payload={
                "cluster_id": cluster_hash,
                "cluster_size": len(cluster.memory_ids),
                "prompt_version": prompt_version,
                "llm_model": llm_model,
                "tokens_used": total_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "source_memory_ids_cited": [str(id) for id in cited_ids],
                "validation_passed": validation_passed,
            }
        )

        # ============================================================
        # STEP 9: Increment rate-limit counters
        # ============================================================

        # Increment synthesis run counter
        increment_synthesis_counter(
            tenant_id=tenant_id,
            kind="manual_run",
            conn=conn,
            amount=1,
        )

        # Increment token counter
        increment_synthesis_counter(
            tenant_id=tenant_id,
            kind="llm_tokens",
            conn=conn,
            amount=total_tokens,
        )

        db_write_duration_ms = int((time.perf_counter() - db_write_start) * 1000)
        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "db_write",
            "duration_ms": db_write_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": str(synthesis_id),
        }))

        # ============================================================
        # STEP 10: Return success
        # ============================================================

        return SynthesisResult(
            success=True,
            synthesis_id=synthesis_id,
            audit_event_id=audit_event_id,
            cluster_size=len(cluster.memory_ids),
            source_memory_ids=cited_ids,
            parent_memory_ids=cluster.memory_ids,
            tokens_used=total_tokens,
            llm_model=llm_model,
            rejected_reason=None,
            dry_run=False,
        )

    finally:
        if conn:
            pool.putconn(conn)


def _write_audit_event(
    tenant_id: str,
    target_memory_id: Optional[UUID],
    event_type: str,
    actor: str,
    event_payload: dict,
) -> UUID:
    """
    Write an audit event to synthesis_audit_events table.

    Returns:
        UUID of the created audit event
    """
    event_id = uuid4()

    query = """
        INSERT INTO memory_service.synthesis_audit_events (
            id, tenant_id, target_memory_id, event_type, actor, event_payload
        ) VALUES (
            %s, %s, %s, %s, %s, %s::jsonb
        )
    """

    params = (
        str(event_id),
        tenant_id,
        str(target_memory_id) if target_memory_id else None,
        event_type,
        actor,
        json.dumps(event_payload),
    )

    _db_execute_rows(query, params, tenant_id=tenant_id, fetch_results=False)

    return event_id
