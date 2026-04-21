"""
Alert Manager - Intelligent alerting with rate limiting and multi-channel delivery
Sends critical alerts to Telegram with smart throttling and escalation
"""
import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from collections import defaultdict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
# from storage_multitenant import get_db_connection  # Not critical for Telegram alerts

logger = logging.getLogger("0latency.alerts")

# Configuration
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8544668212")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Alert thresholds
ERROR_RATE_THRESHOLD = 10  # errors per minute
SLOW_QUERY_THRESHOLD_MS = 5000  # 5 seconds
MEMORY_THRESHOLD_PERCENT = 90
DISK_THRESHOLD_PERCENT = 90


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertManager:
    """
    Manages alert delivery with intelligent throttling and escalation
    """
    
    def __init__(self):
        # Alert cooldown tracking (alert_key -> last_sent_timestamp)
        self.alert_cache: Dict[str, float] = {}
        
        # Cooldown periods (in seconds) based on severity
        self.cooldown_periods = {
            AlertLevel.INFO: 3600,      # 1 hour
            AlertLevel.WARNING: 1800,   # 30 minutes
            AlertLevel.ERROR: 900,      # 15 minutes
            AlertLevel.CRITICAL: 300,   # 5 minutes
        }
        
        # Alert counters for escalation
        self.alert_counts: Dict[str, int] = defaultdict(int)
        self.conn = None
    
    def get_connection(self):
        """Get database connection"""
        # DB persistence disabled for now - alerts work via Telegram only
        return None
    
    def should_send_alert(self, alert_key: str, level: AlertLevel) -> bool:
        """
        Determine if alert should be sent based on cooldown period
        
        Args:
            alert_key: Unique identifier for this alert type
            level: Severity level
            
        Returns:
            True if alert should be sent, False if throttled
        """
        now = time.time()
        cooldown = self.cooldown_periods[level]
        
        if alert_key in self.alert_cache:
            time_since_last = now - self.alert_cache[alert_key]
            
            if time_since_last < cooldown:
                logger.debug(f"Alert throttled: {alert_key} (sent {time_since_last:.0f}s ago)")
                return False
        
        # Update cache
        self.alert_cache[alert_key] = now
        self.alert_counts[alert_key] += 1
        
        return True
    
    def send_telegram(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        disable_preview: bool = True
    ) -> bool:
        """
        Send alert to Telegram
        
        Args:
            message: Alert message
            level: Severity level
            disable_preview: Disable link preview in Telegram
            
        Returns:
            True if sent successfully
        """
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("No TELEGRAM_BOT_TOKEN - alert not sent")
            return False
        
        # Format message with emoji and severity
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🔥",
        }
        
        emoji = emoji_map.get(level, "📊")
        formatted = (
            f"{emoji} *0Latency Alert*\n\n"
            f"*{level.value.upper()}*\n\n"
            f"{message}\n\n"
            f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_"
        )
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            response = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": formatted,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": disable_preview,
                },
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"Alert sent: {level.value}")
                return True
            else:
                logger.error(f"Failed to send alert: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.exception(f"Exception sending Telegram alert: {e}")
            return False
    
    def _send_telegram_alert(self, message: str, level: AlertLevel) -> bool:
        """Send alert via Telegram using openclaw message tool"""
        try:
            import subprocess
            emoji = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "critical": "🔴"}[level.value]
            full_message = f"{emoji} **{level.value.upper()}**\n\n{message}"
            
            result = subprocess.run(
                ["openclaw", "message", "send", "--channel", "telegram", "--target", "8544668212", "--message", full_message],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Telegram alert failed: {e}")
            return False
    
    def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.ERROR,
        alert_type: str = "general",
        context: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> bool:
        """
        Send an alert with throttling and logging
        
        Args:
            message: Alert message
            level: Severity level
            alert_type: Type of alert (for grouping/throttling)
            context: Additional context to log
            force: Skip throttling (use sparingly)
            
        Returns:
            True if alert was sent
        """
        alert_key = f"{alert_type}:{level.value}"
        
        # Check throttling
        if not force and not self.should_send_alert(alert_key, level):
            return False
        
        # Log to database
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, level, message, context, sent_at
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                alert_type,
                level.value,
                message,
                str(context) if context else None,
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            
        except Exception as e:
            logger.exception(f"Failed to log alert to database: {e}")
        
        # Send via Telegram (direct Bot API, not subprocess)
        success = self.send_telegram(message, level)
        
        # Log to application logger
        log_func = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.ERROR: logger.error,
            AlertLevel.CRITICAL: logger.critical,
        }.get(level, logger.info)
        
        log_func(f"ALERT: {message}", extra={'alert_type': alert_type, 'level': level.value})
        
        return success
    
    def check_error_rate(self, error_stats: Dict[str, Any]) -> List[str]:
        """
        Check if error rate exceeds threshold and send alerts
        
        Returns:
            List of alert messages sent
        """
        alerts_sent = []
        
        error_rate = error_stats.get('error_rate_per_minute', 0)
        
        if error_rate > ERROR_RATE_THRESHOLD:
            message = (
                f"⚠️ High Error Rate Detected\n\n"
                f"Current rate: {error_rate:.1f} errors/minute\n"
                f"Threshold: {ERROR_RATE_THRESHOLD} errors/minute\n"
                f"Total errors (24h): {error_stats.get('total_errors', 0)}\n"
                f"Unique error groups: {error_stats.get('unique_error_groups', 0)}"
            )
            
            if self.send_alert(
                message,
                level=AlertLevel.ERROR,
                alert_type="high_error_rate"
            ):
                alerts_sent.append(message)
        
        return alerts_sent
    
    def check_database_health(self, db_stats: Dict[str, Any]) -> List[str]:
        """
        Check database health and send alerts if needed
        
        Returns:
            List of alert messages sent
        """
        alerts_sent = []
        
        # Check for database connection failure
        if db_stats.get('status') == 'unhealthy':
            message = (
                f"🔥 Database Connection Failed\n\n"
                f"Error: {db_stats.get('error', 'Unknown error')}\n"
                f"This is a critical issue requiring immediate attention."
            )
            
            if self.send_alert(
                message,
                level=AlertLevel.CRITICAL,
                alert_type="database_failure"
            ):
                alerts_sent.append(message)
        
        # Check for slow queries
        slow_queries = db_stats.get('slow_query_count', 0)
        if slow_queries > 10:
            message = (
                f"⚠️ Slow Database Queries Detected\n\n"
                f"Count: {slow_queries} queries >5s\n"
                f"This may indicate performance issues."
            )
            
            if self.send_alert(
                message,
                level=AlertLevel.WARNING,
                alert_type="slow_queries"
            ):
                alerts_sent.append(message)
        
        return alerts_sent
    
    def check_system_health(self, system_stats: Dict[str, Any]) -> List[str]:
        """
        Check system resource health and alert if needed
        
        Returns:
            List of alert messages sent
        """
        alerts_sent = []
        
        # Memory check
        memory = system_stats.get('memory', {})
        if memory.get('percent', 0) > MEMORY_THRESHOLD_PERCENT:
            message = (
                f"⚠️ High Memory Usage\n\n"
                f"Current: {memory['percent']:.1f}%\n"
                f"Used: {memory['used_gb']:.1f} GB / {memory['total_gb']:.1f} GB\n"
                f"Threshold: {MEMORY_THRESHOLD_PERCENT}%"
            )
            
            if self.send_alert(
                message,
                level=AlertLevel.WARNING,
                alert_type="high_memory"
            ):
                alerts_sent.append(message)
        
        # Disk check
        disk = system_stats.get('disk', {})
        if disk.get('percent', 0) > DISK_THRESHOLD_PERCENT:
            message = (
                f"⚠️ High Disk Usage\n\n"
                f"Current: {disk['percent']:.1f}%\n"
                f"Used: {disk['used_gb']:.1f} GB / {disk['total_gb']:.1f} GB\n"
                f"Threshold: {DISK_THRESHOLD_PERCENT}%"
            )
            
            if self.send_alert(
                message,
                level=AlertLevel.WARNING,
                alert_type="high_disk"
            ):
                alerts_sent.append(message)
        
        return alerts_sent
    
    def check_api_failures(self, endpoint_stats: List[Dict[str, Any]]) -> List[str]:
        """
        Check for API/external service failures
        
        Returns:
            List of alert messages sent
        """
        alerts_sent = []
        
        for stats in endpoint_stats:
            endpoint = stats.get('endpoint', 'unknown')
            error_rate = stats.get('error_rate', 0)
            
            # Alert if >20% error rate on any endpoint
            if error_rate > 0.2 and stats.get('request_count', 0) > 5:
                message = (
                    f"❌ High Error Rate on Endpoint\n\n"
                    f"Endpoint: {endpoint}\n"
                    f"Error rate: {error_rate*100:.1f}%\n"
                    f"Errors: {stats.get('error_count', 0)} / {stats.get('request_count', 0)} requests"
                )
                
                if self.send_alert(
                    message,
                    level=AlertLevel.ERROR,
                    alert_type=f"endpoint_errors_{endpoint}"
                ):
                    alerts_sent.append(message)
        
        return alerts_sent
    
    def run_all_checks(self) -> Dict[str, List[str]]:
        """
        Run all monitoring checks and send alerts as needed
        
        Returns:
            Dictionary of check results
        """
        from .error_tracker import get_error_stats
        from .metrics import get_metrics_summary
        
        results = {
            'error_rate': [],
            'database': [],
            'system': [],
            'endpoints': [],
        }
        
        try:
            # Get current metrics
            error_stats = get_error_stats(hours=1)
            metrics = get_metrics_summary()
            
            # Run checks
            results['error_rate'] = self.check_error_rate(error_stats)
            results['database'] = self.check_database_health(metrics.get('database', {}))
            results['system'] = self.check_system_health(metrics.get('system', {}))
            results['endpoints'] = self.check_api_failures(metrics.get('endpoints', []))
            
        except Exception as e:
            logger.exception(f"Failed to run monitoring checks: {e}")
            self.send_alert(
                f"Monitoring system failure: {str(e)}",
                level=AlertLevel.CRITICAL,
                alert_type="monitoring_failure",
                force=True
            )
        
        return results


# Global instance
_alert_manager = AlertManager()


def send_alert(message: str, level: str = "error", **kwargs) -> bool:
    """
    Convenience function to send an alert
    
    Args:
        message: Alert message
        level: Severity level (info/warning/error/critical)
        **kwargs: Additional arguments for AlertManager.send_alert()
    """
    alert_level = AlertLevel(level)
    return _alert_manager.send_alert(message, level=alert_level, **kwargs)


def check_alert_thresholds() -> Dict[str, List[str]]:
    """
    Convenience function to run all alert checks
    """
    return _alert_manager.run_all_checks()
