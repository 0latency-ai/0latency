"""
Error tracking and alerting for critical API endpoints
Lightweight integration for observability system
"""
import sys
import os
import logging
from functools import wraps

logger = logging.getLogger("zerolatency.monitoring")

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from observability import ErrorTracker, ErrorLevel, track_error, MetricsCollector
    from observability.alerts import send_alert, AlertLevel
    MONITORING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Observability not available: {e}")
    MONITORING_AVAILABLE = False

def track_critical_errors(func):
    """
    Decorator for critical endpoints - logs errors and sends Telegram alerts for 500s
    """
    if not MONITORING_AVAILABLE:
        return func  # Pass-through if monitoring not available
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Log the error
            error_id = None
            try:
                from observability import log_error
                error_id = log_error(e, level=ErrorLevel.ERROR)
            except Exception:
                pass
            
            # Send Telegram alert for 500 errors (not 400-level user errors)
            if not isinstance(e, Exception) or not hasattr(e, 'status_code') or getattr(e, 'status_code', 500) >= 500:
                try:
                    send_alert(
                        level=AlertLevel.CRITICAL,
                        title=f"API Error: {func.__name__}",
                        message=f"```\n{type(e).__name__}: {str(e)}\nError ID: {error_id}\n```",
                        channel="telegram",
                        target="8544668212"
                    )
                except Exception as alert_error:
                    logger.warning(f"Alert failed: {alert_error}")
            
            # Re-raise the original exception
            raise
    
    return wrapper
