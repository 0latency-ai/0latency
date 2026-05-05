#!/usr/bin/env python3
"""
CP-SYNTHESIS-PERF Stage 1: Profile synthesis writer.

Runs one synthesis pass against a real cluster on user-justin and emits
a structured profile report showing phase-by-phase timing breakdown.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.synthesis.writer import synthesize_cluster
from src.synthesis.clustering import find_clusters, Cluster
from src.synthesis.profiler import SynthesisProfiler
from src.storage_multitenant import _db_execute_rows, set_tenant_context


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def find_suitable_cluster(tenant_id: str, agent_id: str, cluster_id: str = None) -> Cluster:
    """Find or use specified cluster.
    
    If cluster_id provided, fetch that specific cluster from DB.
    Otherwise use known-good cluster from prior synthesis run.
    """
    if cluster_id:
        logger.info(f"Using specified cluster: {cluster_id}")
        # Fetch cluster members from DB
        set_tenant_context(tenant_id)
        
        # Get cluster members
        query = """
            SELECT id, context, embedding
            FROM memory_service.memories
            WHERE tenant_id = %s
              AND cluster_id = %s
              AND deleted_at IS NULL
            ORDER BY created_at DESC
        """
        rows = _db_execute_rows(query, (tenant_id, cluster_id), tenant_id=tenant_id)
        
        if not rows:
            raise ValueError(f"No memories found for cluster {cluster_id}")
        
        # Build Cluster object
        members = [
            {"id": str(row[0]), "context": row[1], "embedding": row[2]}
            for row in rows
        ]
        cluster = Cluster(
            id=cluster_id,
            members=members,
            centroid=None
        )
        logger.info(f"Cluster {cluster_id}: {len(members)} members")
        return cluster
    else:
        logger.info(f"Using known-good cluster for tenant={tenant_id}")
    
    # Known cluster from CP8 P2 Chain B
    from uuid import UUID
    cluster_ids = [
        UUID("6af31b14-900a-4c64-8031-6a7b5a1ea5b3"),
        UUID("9715585e-d1cc-4a27-8e33-47fb8d3bdd3b"),
        UUID("0923fd50-32ef-4a4f-ba91-e01941cc4909"),
        UUID("46eafc5e-2f31-46e7-b803-64fa20cb710d"),
        UUID("357f2074-2412-4849-9473-74328bd4b3df"),
        UUID("598cd922-ad7e-4dde-af3b-bdf51394f3d2"),
        UUID("8896ea6d-d747-460d-9c0c-5d3d3d7f2784"),
        UUID("ab258f03-494b-40a2-9da0-b8f7d8c504ae"),
        UUID("aab371ed-8c18-48c6-98f2-07014b64cdb7"),
        UUID("9be1478c-adee-4a12-82e5-84bae5fbfaa8"),
        UUID("b8931bd5-4693-4da0-88be-f5802a3430bd"),
        UUID("58772303-7644-418e-a39d-3d55ecd3b3ae"),
    ]
    
    # Create minimal cluster object (centroid and signature not needed for profiling)
    cluster = Cluster(
        memory_ids=cluster_ids,
        centroid_embedding=[],
        cluster_signature="Profile cluster (12 atoms from prior synthesis)",
    )
    
    logger.info(f"Using cluster with {len(cluster.memory_ids)} members")
    
    return cluster


def run_profile(tenant_id: str, agent_id: str, cluster: Cluster) -> dict:
    """Run synthesis with profiling enabled.
    
    Returns profiler data dict.
    """
    # Preload embedding model to avoid cold-load during profiling
    logger.info("Preloading embedding model...")
    import time as _preload_time
    _preload_start = _preload_time.time()
    from src.storage_multitenant import _get_local_model
    _get_local_model()  # Force model load + warmup
    _preload_duration = _preload_time.time() - _preload_start
    logger.info(f"Model preloaded in {_preload_duration:.2f}s (excluded from profile)")
    
    logger.info("Starting profiled synthesis run...")
    
    profiler = SynthesisProfiler()
    profiler.start()
    
    try:
        # Run synthesis (dry_run=False to get realistic timing)
        result = synthesize_cluster(
            cluster=cluster,
            tenant_id=tenant_id,
            agent_id=agent_id,
            role_tag="public",
            prompt_version="single_agent_v1",
            dry_run=False,
            persist=True,
        )
        
        if not result.success:
            logger.error(f"Synthesis failed: {result.rejected_reason}")
            sys.exit(1)
        
        logger.info(f"Synthesis succeeded: {result.synthesis_id}")
        logger.info(f"Tokens used: {result.tokens_used}")
        logger.info(f"Model: {result.llm_model}")
    
    finally:
        profiler.stop()
    
    # Get profiler data
    profile_data = profiler.to_dict()
    profile_data["cluster_id"] = str(cluster.memory_ids[0]) if cluster.memory_ids else None
    profile_data["cluster_size"] = len(cluster.memory_ids)
    profile_data["synthesis_result"] = {
        "success": result.success,
        "synthesis_id": str(result.synthesis_id) if result.synthesis_id else None,
        "tokens_used": result.tokens_used,
        "llm_model": result.llm_model,
    }
    
    return profile_data


def write_json_report(profile_data: dict, output_path: Path):
    """Write JSON report."""
    with open(output_path, "w") as f:
        json.dump(profile_data, f, indent=2, default=str)
    
    logger.info(f"JSON report written: {output_path}")


def write_markdown_report(profile_data: dict, output_path: Path):
    """Write human-readable markdown report."""
    
    wall_clock_ms = profile_data["wall_clock_ms"]
    cluster_size = profile_data["cluster_size"]
    cluster_id = profile_data["cluster_id"]
    synthesis_result = profile_data["synthesis_result"]
    phases = profile_data["phases"]
    
    # Calculate total accounted time
    total_accounted_ms = sum(p["duration_ms"] for p in phases)
    coverage_pct = (total_accounted_ms / wall_clock_ms * 100) if wall_clock_ms > 0 else 0
    
    # Find dominant phase
    if phases:
        phases_sorted = sorted(phases, key=lambda p: p["duration_ms"], reverse=True)
        dominant_phase = phases_sorted[0]
        second_phase = phases_sorted[1] if len(phases_sorted) > 1 else None
    else:
        dominant_phase = None
        second_phase = None
    
    # Build report
    lines = []
    lines.append("# Synthesis Writer Profile Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Cluster ID:** {cluster_id}")
    lines.append(f"**Cluster Size:** {cluster_size} memories")
    lines.append(f"**Synthesis ID:** {synthesis_result['synthesis_id']}")
    lines.append(f"**Model:** {synthesis_result['llm_model']}")
    lines.append(f"**Tokens Used:** {synthesis_result['tokens_used']}")
    lines.append("")
    
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total wall-clock:** {wall_clock_ms}ms ({wall_clock_ms/1000:.1f}s)")
    lines.append(f"- **Total accounted:** {total_accounted_ms}ms ({coverage_pct:.1f}% coverage)")
    lines.append(f"- **Phases recorded:** {len(phases)}")
    lines.append("")
    
    lines.append("## Phase Breakdown")
    lines.append("")
    lines.append("| Phase | Duration (ms) | % of Total | Metadata |")
    lines.append("|-------|--------------|-----------|----------|")
    
    for phase in phases_sorted:
        name = phase["phase_name"]
        duration_ms = phase["duration_ms"]
        pct = (duration_ms / wall_clock_ms * 100) if wall_clock_ms > 0 else 0
        
        # Format metadata
        metadata = phase.get("metadata", {})
        meta_str = ", ".join(f"{k}={v}" for k, v in metadata.items() if k != "tenant_id")
        if len(meta_str) > 50:
            meta_str = meta_str[:47] + "..."
        
        lines.append(f"| {name} | {duration_ms} | {pct:.1f}% | {meta_str} |")
    
    lines.append("")
    
    # Write markdown
    content = "\n".join(lines)
    with open(output_path, "w") as f:
        f.write(content)
    
    logger.info(f"Markdown report written: {output_path}")


def main():
    """Main driver."""
    parser = argparse.ArgumentParser(description="Profile synthesis writer")
    parser.add_argument(
        "--cluster-id",
        type=str,
        default=None,
        help="Specific cluster ID to profile (default: use known-good cluster)"
    )
    args = parser.parse_args()
    
    # Configuration
    tenant_id = "44c3080d-c196-407d-a606-4ea9f62ba0fc"
    agent_id = "thomas"
    
    logger.info("="*60)
    logger.info("CP-SYNTHESIS-PERF Stage 1: Profile Synthesis Writer")
    logger.info("="*60)
    
    # Step 1: Find cluster
    cluster = find_suitable_cluster(tenant_id, agent_id, args.cluster_id)
    
    # Step 2: Run profiled synthesis
    profile_data = run_profile(tenant_id, agent_id, cluster)
    
    # Step 3: Write reports
    output_dir = Path("docs/profile")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    json_path = output_dir / f"synthesis-writer-profile-{date_str}.json"
    md_path = output_dir / f"synthesis-writer-profile-{date_str}.md"
    
    write_json_report(profile_data, json_path)
    write_markdown_report(profile_data, md_path)
    
    # Step 4: Summary
    logger.info("="*60)
    logger.info("Profile Complete")
    logger.info(f"Wall-clock: {profile_data['wall_clock_ms']}ms")
    logger.info(f"Phases: {len(profile_data['phases'])}")
    logger.info(f"Reports: {json_path}, {md_path}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
