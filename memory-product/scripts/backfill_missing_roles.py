#!/usr/bin/env python3
"""
Backfill missing tenant roles for existing tenants.
Idempotent - safe to run multiple times.

Usage:
    python3 scripts/backfill_missing_roles.py [--schema memory_service] [--staging]
"""

import sys
import os
import psycopg2
from typing import List, Tuple

def get_db_connection(staging: bool = False):
    """Get database connection from environment."""
    # Load .env if it exists
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    
    var_name = "STAGING_DATABASE_URL" if staging else "DATABASE_URL"
    conn_str = os.environ.get(var_name, "")
    if not conn_str:
        raise ValueError(f"{var_name} environment variable not set")
    
    return psycopg2.connect(conn_str)


def find_tenants_without_roles(conn, schema: str = "memory_service") -> List[Tuple[str, str]]:
    """Find all tenants that don't have any roles."""
    cur = conn.cursor()
    
    query = f"""
        SELECT t.id, t.name
        FROM {schema}.tenants t
        WHERE t.id NOT IN (
            SELECT DISTINCT tenant_id 
            FROM {schema}.tenant_roles
        )
        AND t.active = true
        ORDER BY t.created_at;
    """
    
    cur.execute(query)
    results = cur.fetchall()
    cur.close()
    
    return results


def backfill_roles(conn, tenant_id: str, tenant_name: str, schema: str = "memory_service") -> int:
    """Backfill default roles for a tenant. Returns number of roles added."""
    # Default roles from migration 013_cp8_tenant_roles.sql (verbatim)
    default_roles = [
        ('public', 'Public role - visible to all consumers within this tenant'),
        ('engineering', 'Engineering team role - technical context and implementation details'),
        ('product', 'Product team role - feature context and user-facing decisions'),
        ('revenue', 'Revenue team role - sales, pricing, and business metrics'),
        ('legal', 'Legal team role - compliance, contracts, and risk management')
    ]
    
    cur = conn.cursor()
    roles_added = 0
    
    for role_name, description in default_roles:
        try:
            cur.execute(f"""
                INSERT INTO {schema}.tenant_roles (tenant_id, role_name, description)
                VALUES (%s::UUID, %s, %s)
                ON CONFLICT (tenant_id, role_name) DO NOTHING
                RETURNING id
            """, (tenant_id, role_name, description))
            
            if cur.fetchone():
                roles_added += 1
        except Exception as e:
            print(f"  ERROR seeding role {role_name} for tenant {tenant_id}: {e}")
            raise
    
    cur.close()
    conn.commit()
    
    return roles_added


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill missing tenant roles')
    parser.add_argument('--schema', default='memory_service', help='Database schema name')
    parser.add_argument('--staging', action='store_true', help='Run against staging database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()
    
    try:
        conn = get_db_connection(staging=args.staging)
        env_name = "STAGING" if args.staging else "PRODUCTION"
        print(f"Connected to {env_name} database (schema: {args.schema})")
        
        # Find tenants without roles
        tenants = find_tenants_without_roles(conn, args.schema)
        
        if not tenants:
            print("✓ All tenants have roles. Nothing to backfill.")
            return 0
        
        print(f"Found {len(tenants)} tenant(s) without roles:")
        for tenant_id, tenant_name in tenants:
            print(f"  - {tenant_id} ({tenant_name})")
        
        if args.dry_run:
            print("\n[DRY RUN] Would backfill roles for these tenants")
            return 0
        
        # Confirm for production
        if not args.staging:
            confirm = input(f"\nBackfill {len(tenants)} tenants in PRODUCTION? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return 1
        
        # Backfill each tenant
        print(f"\nBackfilling roles...")
        total_roles_added = 0
        
        for tenant_id, tenant_name in tenants:
            try:
                roles_added = backfill_roles(conn, tenant_id, tenant_name, args.schema)
                total_roles_added += roles_added
                print(f"  ✓ {tenant_id} ({tenant_name}): added {roles_added} roles")
            except Exception as e:
                print(f"  ✗ {tenant_id} ({tenant_name}): FAILED - {e}")
                conn.rollback()
                raise
        
        print(f"\n✓ Backfilled {len(tenants)} tenant(s) with {total_roles_added} total roles")
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
