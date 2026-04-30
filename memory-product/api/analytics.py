"""
Basic Analytics for 0Latency
Tracks user events and provides dashboard metrics
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage_multitenant import _db_execute, _db_execute_rows
import posthog

logger = logging.getLogger("0latency")

# Initialize PostHog
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")
POSTHOG_HOST = "https://us.i.posthog.com"  # Direct to PostHog, not through reverse proxy

if POSTHOG_API_KEY:
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
    logger.info("PostHog initialized")
else:
    logger.warning("POSTHOG_API_KEY not set - PostHog tracking disabled")


def track_event(
    tenant_id,
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
            INSERT INTO memory_service.analytics_events (tenant_id, event_type, metadata, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (tenant_id, event_type, metadata))
        logger.info(f"Tracked event: {event_type} for tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Failed to track event: {e}")


def track_posthog_event(
    tenant_id,  # Union[str, int] - accepts UUID string or legacy int
    event_name: str,
    properties: Optional[Dict[str, Any]] = None,
    distinct_id: Optional[str] = None
):
    """
    Track event to PostHog

    Args:
        tenant_id: Tenant ID (UUID string or int for legacy)
        event_name: Event name (api_key_created, first_api_call, etc.)
        properties: Additional event properties
        distinct_id: User identifier (defaults to tenant_id)
    """
    if not POSTHOG_API_KEY:
        return

    try:
        user_id = distinct_id or f"tenant_{tenant_id}"
        props = properties or {}
        props["tenant_id"] = tenant_id

        posthog.capture(
            distinct_id=user_id,
            event=event_name,
            properties=props
        )
        logger.debug(f"PostHog event tracked: {event_name} for {user_id}")
    except Exception as e:
        logger.error(f"Failed to track PostHog event: {e}")


def is_first_api_call(tenant_id) -> bool:
    """Check if this is the first API call for a tenant"""
    try:
        result = _db_execute_rows("""
            SELECT COUNT(*) as count FROM memory_service.analytics_events
            WHERE tenant_id = %s AND event_type = 'api_call'
        """, (tenant_id,))
        return result[0][0] == 0 if result else True
    except Exception as e:
        logger.error(f"Failed to check first API call: {e}")
        return False


def is_first_memory_stored(tenant_id) -> bool:
    """Check if this is the first memory extraction for a tenant"""
    try:
        result = _db_execute_rows("""
            SELECT COUNT(*) as count FROM memory_service.analytics_events
            WHERE tenant_id = %s
            AND event_type = 'api_call'
            AND metadata->>'endpoint' = '/extract'
        """, (tenant_id,))
        return result[0][0] == 0 if result else True
    except Exception as e:
        logger.error(f"Failed to check first memory stored: {e}")
        return False


def is_first_memory_recalled(tenant_id) -> bool:
    """Check if this is the first memory recall for a tenant"""
    try:
        result = _db_execute_rows("""
            SELECT COUNT(*) as count FROM memory_service.analytics_events
            WHERE tenant_id = %s
            AND event_type = 'api_call'
            AND metadata->>'endpoint' = '/recall'
        """, (tenant_id,))
        return result[0][0] == 0 if result else True
    except Exception as e:
        logger.error(f"Failed to check first memory recalled: {e}")
        return False


def check_activation_milestone(tenant_id) -> bool:
    """
    Check if tenant hit activation milestone (10 recalls in a single day)
    Returns True if they just hit it (haven't tracked activation_event yet)
    """
    try:
        # Check if activation already tracked
        activation_check = _db_execute_rows("""
            SELECT COUNT(*) as count FROM memory_service.analytics_events
            WHERE tenant_id = %s AND event_type = 'activation'
        """, (tenant_id,))

        if activation_check and activation_check[0]['count'] > 0:
            return False  # Already activated

        # Count recalls today
        recall_count = _db_execute_rows("""
            SELECT COUNT(*) as count FROM memory_service.analytics_events
            WHERE tenant_id = %s
            AND event_type = 'api_call'
            AND metadata->>'endpoint' = '/recall'
            AND created_at > CURRENT_DATE
        """, (tenant_id,))

        if recall_count and recall_count[0]['count'] >= 10:
            # Track activation in memory_service.analytics_events to prevent duplicate triggers
            track_event(tenant_id, "activation", {"recalls_today": recall_count[0]['count']})
            return True

        return False
    except Exception as e:
        logger.error(f"Failed to check activation milestone: {e}")
        return False


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
            total_users = result[0][0] if result else 0
        
        # API calls by timeframe
        where_clause = f"WHERE tenant_id = {tenant_id}" if tenant_id else ""
        
        api_calls_24h = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM memory_service.analytics_events 
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '24 hours'
        """, ())[0]['count'] if _db_execute_rows(f"SELECT COUNT(*) as count FROM memory_service.analytics_events {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call' AND created_at > NOW() - INTERVAL '24 hours'", ()) else 0
        
        api_calls_7d = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM memory_service.analytics_events 
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '7 days'
        """, ())[0]['count'] if _db_execute_rows(f"SELECT COUNT(*) as count FROM memory_service.analytics_events {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call' AND created_at > NOW() - INTERVAL '7 days'", ()) else 0
        
        api_calls_30d = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM memory_service.analytics_events 
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '30 days'
        """, ())[0]['count'] if _db_execute_rows(f"SELECT COUNT(*) as count FROM memory_service.analytics_events {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call' AND created_at > NOW() - INTERVAL '30 days'", ()) else 0
        
        # Active users (made API call in last 7 days)
        active_result = _db_execute_rows(f"""
            SELECT COUNT(DISTINCT tenant_id) as count FROM memory_service.analytics_events
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'api_call'
            AND created_at > NOW() - INTERVAL '7 days'
        """, ())
        active_users = active_result[0][0] if active_result else 0
        
        # Error rate (last 24h)
        total_api_calls = api_calls_24h
        error_result = _db_execute_rows(f"""
            SELECT COUNT(*) as count FROM memory_service.analytics_events
            {where_clause} {'AND' if where_clause else 'WHERE'} event_type = 'error'
            AND created_at > NOW() - INTERVAL '24 hours'
        """, ())
        errors = error_result[0][0] if error_result else 0
        error_rate = (errors / total_api_calls * 100) if total_api_calls > 0 else 0
        
        # Popular endpoints
        popular_endpoints = _db_execute_rows(f"""
            SELECT 
                metadata->>'endpoint' as endpoint,
                COUNT(*) as count
            FROM memory_service.analytics_events
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
    """Create memory_service.analytics_events table if it doesn't exist"""
    _db_execute("""
        CREATE TABLE IF NOT EXISTS memory_service.analytics_events (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            event_type VARCHAR(50) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_analytics_tenant ON memory_service.analytics_events(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_type ON memory_service.analytics_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_analytics_created ON memory_service.analytics_events(created_at);
    """, ())
    logger.info("Analytics table created/verified")


if __name__ == "__main__":
    # Initialize analytics table
    create_analytics_table()
    print("Analytics table ready")
