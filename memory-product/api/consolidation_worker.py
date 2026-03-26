#!/usr/bin/env python3
"""
Consolidation Background Worker

Runs daily (via cron or on-demand) to detect and optionally auto-merge
duplicate memories across all active agents.

Usage:
    python consolidation_worker.py                    # Detect only
    python consolidation_worker.py --auto-merge       # Detect + auto-merge (similarity > 0.95)
    python consolidation_worker.py --threshold 0.90   # Custom similarity threshold
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# Add src/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from storage_multitenant import _db_execute_rows, set_tenant_context
from consolidation import run_consolidation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)
logger = logging.getLogger("consolidation_worker")


def get_active_agents(days: int = 30) -> list[dict]:
    """Get agents with memories created in the last N days, grouped by tenant."""
    rows = _db_execute_rows("""
        SELECT DISTINCT m.agent_id, m.tenant_id, t.plan,
               COUNT(*) as memory_count
        FROM memory_service.memories m
        JOIN memory_service.tenants t ON m.tenant_id = t.id
        WHERE m.created_at > NOW() - make_interval(days => %s)
            AND m.superseded_at IS NULL
            AND t.active = true
        GROUP BY m.agent_id, m.tenant_id, t.plan
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
    """, (days,), tenant_id="00000000-0000-0000-0000-000000000000")
    
    agents = []
    for r in (rows or []):
        agents.append({
            "agent_id": str(r[0]),
            "tenant_id": str(r[1]),
            "plan": str(r[2]),
            "memory_count": int(r[3]),
        })
    return agents


def run_worker(
    auto_merge: bool = False,
    similarity_threshold: float = 0.85,
    auto_merge_threshold: float = 0.95,
    days: int = 30,
):
    """Main worker loop: consolidate all active agents."""
    start = datetime.now(timezone.utc)
    logger.info(f"Consolidation worker started. auto_merge={auto_merge} threshold={similarity_threshold}")
    
    agents = get_active_agents(days)
    logger.info(f"Found {len(agents)} active agents to consolidate")
    
    total_found = 0
    total_stored = 0
    total_merged = 0
    errors = 0
    
    for agent in agents:
        agent_id = agent["agent_id"]
        tenant_id = agent["tenant_id"]
        plan = agent["plan"]
        
        # Only auto-merge for scale/enterprise tenants
        should_auto_merge = auto_merge and plan in ("scale", "enterprise")
        
        try:
            set_tenant_context(tenant_id)
            result = run_consolidation(
                agent_id=agent_id,
                tenant_id=tenant_id,
                similarity_threshold=similarity_threshold,
                auto_merge=should_auto_merge,
                auto_merge_threshold=auto_merge_threshold,
            )
            
            total_found += result["duplicates_found"]
            total_stored += result["pairs_stored"]
            total_merged += result["auto_merged"]
            
            if result["duplicates_found"] > 0:
                logger.info(
                    f"  agent={agent_id} tenant={tenant_id[:8]}... "
                    f"found={result['duplicates_found']} stored={result['pairs_stored']} "
                    f"merged={result['auto_merged']}"
                )
        except Exception as e:
            errors += 1
            logger.error(f"  agent={agent_id} tenant={tenant_id[:8]}... ERROR: {e}")
    
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        f"Consolidation worker complete. "
        f"agents={len(agents)} found={total_found} stored={total_stored} "
        f"merged={total_merged} errors={errors} elapsed={elapsed:.1f}s"
    )
    
    return {
        "agents_processed": len(agents),
        "duplicates_found": total_found,
        "pairs_stored": total_stored,
        "auto_merged": total_merged,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memory Consolidation Worker")
    parser.add_argument("--auto-merge", action="store_true", help="Auto-merge high-confidence duplicates")
    parser.add_argument("--threshold", type=float, default=0.85, help="Similarity threshold for detection")
    parser.add_argument("--merge-threshold", type=float, default=0.95, help="Threshold for auto-merge")
    parser.add_argument("--days", type=int, default=30, help="Look back N days for active agents")
    args = parser.parse_args()
    
    result = run_worker(
        auto_merge=args.auto_merge,
        similarity_threshold=args.threshold,
        auto_merge_threshold=args.merge_threshold,
        days=args.days,
    )
    
    print(f"\n=== Summary ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
