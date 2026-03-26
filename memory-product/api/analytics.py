"""
Basic Analytics for 0Latency
Tracks user events and provides dashboard metrics
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from storage_multitenant import _db_execute, _db_execute_rows

logger = logging.getLogger("0latency")

def track_event(
    tenant_id: int,
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Track an analytics event
    
    Args:
        tenant_id: Tenant ID
        event_type: Event type (signup, login, api_call, error, upgrade)
        metadata: Additional event data (endpoint, error_type, etc.)
    """
    try:
        _db_execute("""
            INSERT INTO analytics_events (tenant_id, event_type, metadata, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (tenant_id, event_type, metadata))
        logger.info(f"Tracked event: {event_type} for tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Failed to track event: {e}")


def get_dashboard_stats(tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get analytics for dashboard
    
    Args:
        tenant_id: If provided, stats for specific tenant. Otherwise, global stats.
    
    Returns:
        Dictionary with metrics:
        - total_users
        - api_calls_24h, api_calls_7d, api_calls_30d
        - active_users
        - error_rate
        - popular_endpoints
    """
    try:
        # Total users
        if tenant_id:
            total_users = 1
        else:
            result = _db_execute_rows("SELECT COUNT(*) as count FROM tenants", ())
            total_users = result[0]['count'] if result else 0
        
        # API calls by timeframe
        where_clause = f"WHERE tenant_id = {tenant_id}" if tenant_id else ""
        
        api_calls_24h = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM analytics_events 
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '24 hours'
        """, ())[0]['count'] if _db_execute_rows(f"SELECT COUNT(*) as count FROM analytics_events {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call' AND created_at > NOW() - INTERVAL '24 hours'", ()) else 0
        
        api_calls_7d = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM analytics_events 
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '7 days'
        """, ())[0]['count'] if _db_execute_rows(f"SELECT COUNT(*) as count FROM analytics_events {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call' AND created_at > NOW() - INTERVAL '7 days'", ()) else 0
        
        api_calls_30d = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM analytics_events 
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '30 days'
        """, ())[0]['count'] if _db_execute_rows(f"SELECT COUNT(*) as count FROM analytics_events {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call' AND created_at > NOW() - INTERVAL '30 days'", ()) else 0
        
        # Active users (made API call in last 7 days)
        active_result = _db_execute_rows(f"""
            SELECT COUNT(DISTINCT tenant_id) as count FROM analytics_events
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '7 days'
        """, ())
        active_users = active_result[0]['count'] if active_result else 0
        
        # Error rate (last 24h)
        total_api_calls = api_calls_24h
        error_result = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM analytics_events
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'error'
            AND created_at > NOW() - INTERVAL '24 hours'
        """, ())
        errors = error_result[0]['count'] if error_result else 0
        error_rate = (errors / total_api_calls * 100) if total_api_calls > 0 else 0
        
        # Popular endpoints
        popular_endpoints = _db_execute_rows(f"""
            SELECT 
                metadata->>'endpoint' as endpoint,
                COUNT(*) as count
            FROM analytics_events
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND metadata->>'endpoint' IS NOT NULL
            AND created_at > NOW() - INTERVAL '7 days'
            GROUP BY metadata->>'endpoint'
            ORDER BY count DESC
            LIMIT 10
        """, ())
        
        return {
            "total_users": total_users,
            "api_calls_24h": api_calls_24h,
            "api_calls_7d": api_calls_7d,
            "api_calls_30d": api_calls_30d,
            "active_users": active_users,
            "error_rate": round(error_rate, 2),
            "popular_endpoints": popular_endpoints or []
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        return {
            "total_users": 0,
            "api_calls_24h": 0,
            "api_calls_7d": 0,
            "api_calls_30d": 0,
            "active_users": 0,
            "error_rate": 0,
            "popular_endpoints": []
        }


def create_analytics_table():
    """Create analytics_events table if it doesn't exist"""
    _db_execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            event_type VARCHAR(50) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_analytics_tenant ON analytics_events(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics_events(created_at);
    """, ())
    logger.info("Analytics table created/verified")


if __name__ == "__main__":
    # Initialize analytics table
    create_analytics_table()
    print("Analytics table ready")
