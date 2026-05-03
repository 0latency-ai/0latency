#!/usr/bin/env python3
"""
CP8 Phase 2 T6 — Synthesis Cron Worker

Runs daily at 03:00 UTC via systemd timer.
Iterates active tenants on Pro+ tier and triggers synthesis for each.

Per-tenant scheduling (custom times, days-of-week) is Phase 5.
V1: single UTC slot for all tenants.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.synthesis.orchestrator import run_synthesis_for_tenant
from src.storage_multitenant import _db_execute_rows


def main():
    """
    Iterate Pro+ tenants and run synthesis for each.

    Free tier is blocked at orchestrator level (check_synthesis_quota).
    Quota-exceeded tenants get status='failed' with reason in job.result.
    """
    print("[cron] Starting synthesis cron run")

    # Find tenants on Pro+ tier
    # Free tier would hit quota check anyway, but filtering here saves DB roundtrips
    try:
        tenants = _db_execute_rows(
            """
            SELECT id::text AS tenant_id
            FROM memory_service.tenants
            WHERE tier IN ('pro', 'scale', 'enterprise')
            AND active = true
            """,
            fetch_results=True,
        )
    except Exception as e:
        print(f"[cron] FATAL: Failed to fetch tenants: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[cron] Found {len(tenants)} Pro+ tenants")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for row in tenants:
        tenant_id = row[0]  # _db_execute_rows returns tuples

        try:
            # Run synthesis for this tenant
            # Default agent: "default" for v1; Phase 5 will use tenant config
            result = run_synthesis_for_tenant(
                tenant_id=tenant_id,
                agent_id="default",
                role_scope="public",
                force=False,
                max_clusters=5,
                triggered_by="cron",
            )

            status = result["status"]
            synth_count = result["clusters_synthesized"]

            if status == "succeeded":
                success_count += 1
                print(f"[cron] tenant={tenant_id} status={status} synthesized={synth_count}")
            elif status == "skipped":
                skip_count += 1
                print(f"[cron] tenant={tenant_id} status={status} (no clusters)")
            else:
                fail_count += 1
                print(f"[cron] tenant={tenant_id} status={status}", file=sys.stderr)

        except Exception as e:
            fail_count += 1
            print(f"[cron] tenant={tenant_id} FAILED: {e}", file=sys.stderr)
            # Continue to next tenant; don't let one failure block the cron

    print(f"[cron] Cron run complete: success={success_count} skipped={skip_count} failed={fail_count}")

    # Exit 0 even if some tenants failed; systemd tracks per-run success
    sys.exit(0)


if __name__ == "__main__":
    main()
