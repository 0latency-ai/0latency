"""
Metrics Collector - APM and Performance Monitoring
Tracks request latency, database performance, and system metrics
"""
import os
import sys
import time
import psutil
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from functools import wraps
from collections import defaultdict, deque

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
# from storage_multitenant import get_db_connection  # Not needed for in-memory metrics

logger = logging.getLogger("0latency.metrics")


class MetricsCollector:
    """
    In-memory metrics collection with periodic database persistence
    Tracks latency, throughput, and performance metrics
    """
    
    def __init__(self, window_size: int = 1000):
        """
        Args:
            window_size: Number of recent requests to keep in memory per endpoint
        """
        self.window_size = window_size
        
        # In-memory storage (endpoint -> deque of request times)
        self.request_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.database_latencies: deque = deque(maxlen=window_size)
        self.embedding_latencies: deque = deque(maxlen=window_size)
        
        # Request counters
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # Slow query tracking
        self.slow_queries: deque = deque(maxlen=100)
        self.slow_threshold_ms = 5000  # 5 seconds
        
        self.conn = None
    
    def get_connection(self):
        """Get database connection (reuse or create)"""
        # DB persistence disabled - using in-memory metrics only
        return None
    
    def track_request(
        self,
        endpoint: str,
        duration_ms: float,
        status_code: int = 200,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track a request's performance
        """
        self.request_latencies[endpoint].append({
            'duration_ms': duration_ms,
            'timestamp': time.time(),
            'status_code': status_code,
            'tenant_id': tenant_id,
        })
        
        self.request_counts[endpoint] += 1
        
        if status_code >= 400:
            self.error_counts[endpoint] += 1
        
        # Log slow requests
        if duration_ms > self.slow_threshold_ms:
            logger.warning(
                f"SLOW_REQUEST: {endpoint} took {duration_ms:.0f}ms",
                extra={
                    'endpoint': endpoint,
                    'duration_ms': duration_ms,
                    'tenant_id': tenant_id,
                }
            )
    
    def track_database_query(self, duration_ms: float, query: str = ""):
        """Track database query performance"""
        self.database_latencies.append({
            'duration_ms': duration_ms,
            'timestamp': time.time(),
        })
        
        if duration_ms > self.slow_threshold_ms:
            self.slow_queries.append({
                'query': query[:500],  # Truncate long queries
                'duration_ms': duration_ms,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })
            
            logger.warning(
                f"SLOW_QUERY: {duration_ms:.0f}ms",
                extra={'duration_ms': duration_ms, 'query_preview': query[:200]}
            )
    
    def track_embedding_api(self, duration_ms: float, provider: str = "openai"):
        """Track embedding API call latency"""
        self.embedding_latencies.append({
            'duration_ms': duration_ms,
            'timestamp': time.time(),
            'provider': provider,
        })
    
    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """
        Get performance statistics for a specific endpoint
        """
        if endpoint not in self.request_latencies or len(self.request_latencies[endpoint]) == 0:
            return {
                'endpoint': endpoint,
                'request_count': 0,
                'error_count': 0,
            }
        
        latencies = [req['duration_ms'] for req in self.request_latencies[endpoint]]
        
        return {
            'endpoint': endpoint,
            'request_count': self.request_counts[endpoint],
            'error_count': self.error_counts[endpoint],
            'error_rate': self.error_counts[endpoint] / max(self.request_counts[endpoint], 1),
            'latency_ms': {
                'min': min(latencies),
                'max': max(latencies),
                'mean': statistics.mean(latencies),
                'p50': statistics.median(latencies),
                'p95': self._percentile(latencies, 0.95),
                'p99': self._percentile(latencies, 0.99),
            },
        }
    
    def get_all_endpoint_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all tracked endpoints"""
        return [
            self.get_endpoint_stats(endpoint)
            for endpoint in self.request_latencies.keys()
        ]
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database performance metrics"""
        if len(self.database_latencies) == 0:
            return {
                'query_count': 0,
                'slow_query_count': len(self.slow_queries),
            }
        
        latencies = [q['duration_ms'] for q in self.database_latencies]
        
        return {
            'query_count': len(self.database_latencies),
            'slow_query_count': len(self.slow_queries),
            'latency_ms': {
                'min': min(latencies),
                'max': max(latencies),
                'mean': statistics.mean(latencies),
                'p50': statistics.median(latencies),
                'p95': self._percentile(latencies, 0.95),
                'p99': self._percentile(latencies, 0.99),
            },
            'recent_slow_queries': list(self.slow_queries)[-10:],  # Last 10 slow queries
        }
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding API performance metrics"""
        if len(self.embedding_latencies) == 0:
            return {'call_count': 0}
        
        latencies = [e['duration_ms'] for e in self.embedding_latencies]
        
        return {
            'call_count': len(self.embedding_latencies),
            'latency_ms': {
                'min': min(latencies),
                'max': max(latencies),
                'mean': statistics.mean(latencies),
                'p50': statistics.median(latencies),
                'p95': self._percentile(latencies, 0.95),
            },
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system resource utilization"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                    'percent': memory.percent,
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'percent': disk.percent,
                },
                'cpu_percent': psutil.cpu_percent(interval=1),
            }
        except Exception as e:
            logger.exception(f"Failed to get system stats: {e}")
            return {}
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary
        """
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'endpoints': self.get_all_endpoint_stats(),
            'database': self.get_database_stats(),
            'embedding_api': self.get_embedding_stats(),
            'system': self.get_system_stats(),
        }
    
    def persist_metrics(self):
        """
        Persist current metrics to database (called periodically)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            timestamp = datetime.now(timezone.utc)
            summary = self.get_metrics_summary()
            
            # Store snapshot in metrics table
            cursor.execute("""
                INSERT INTO performance_metrics (
                    timestamp, endpoint_stats, database_stats,
                    embedding_stats, system_stats
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                timestamp,
                str(summary['endpoints']),
                str(summary['database']),
                str(summary['embedding_api']),
                str(summary['system']),
            ))
            
            conn.commit()
            cursor.close()
            
            logger.info("Metrics persisted to database")
            
        except Exception as e:
            logger.exception(f"Failed to persist metrics: {e}")
    
    def check_alert_conditions(self) -> List[Dict[str, Any]]:
        """
        Check for conditions that should trigger alerts
        
        Returns:
            List of alert conditions that are currently met
        """
        alerts = []
        
        # Check error rates
        for endpoint, stats in [(e, self.get_endpoint_stats(e)) for e in self.request_latencies.keys()]:
            if stats['request_count'] > 10 and stats['error_rate'] > 0.1:  # >10% error rate
                alerts.append({
                    'type': 'high_error_rate',
                    'endpoint': endpoint,
                    'error_rate': stats['error_rate'],
                    'message': f"{endpoint} has {stats['error_rate']*100:.1f}% error rate",
                })
        
        # Check slow database queries
        if len(self.slow_queries) > 5:  # More than 5 slow queries recently
            alerts.append({
                'type': 'slow_queries',
                'count': len(self.slow_queries),
                'message': f"{len(self.slow_queries)} slow database queries detected",
            })
        
        # Check system resources
        system = self.get_system_stats()
        if system.get('memory', {}).get('percent', 0) > 90:
            alerts.append({
                'type': 'high_memory',
                'percent': system['memory']['percent'],
                'message': f"Memory usage at {system['memory']['percent']}%",
            })
        
        if system.get('disk', {}).get('percent', 0) > 90:
            alerts.append({
                'type': 'high_disk',
                'percent': system['disk']['percent'],
                'message': f"Disk usage at {system['disk']['percent']}%",
            })
        
        return alerts
    
    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile from sorted data"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]


# Global instance
_metrics_collector = MetricsCollector()


def track_request(endpoint: str, **kwargs):
    """Convenience function to track a request"""
    _metrics_collector.track_request(endpoint, **kwargs)


def get_metrics_summary() -> Dict[str, Any]:
    """Convenience function to get metrics summary"""
    return _metrics_collector.get_metrics_summary()


def get_endpoint_stats(endpoint: str) -> Dict[str, Any]:
    """Convenience function to get endpoint stats"""
    return _metrics_collector.get_endpoint_stats(endpoint)


def track_performance(endpoint: str = None):
    """
    Decorator to automatically track endpoint performance
    
    Usage:
        @track_performance(endpoint="POST /memories/add")
        async def add_memory_endpoint(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Extract endpoint from request if not provided
                endpoint_name = endpoint
                if not endpoint_name:
                    for arg in args:
                        if hasattr(arg, 'url'):
                            endpoint_name = f"{arg.method} {arg.url.path}"
                            break
                
                if endpoint_name:
                    _metrics_collector.track_request(
                        endpoint_name,
                        duration_ms,
                        status_code
                    )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                endpoint_name = endpoint or func.__name__
                _metrics_collector.track_request(
                    endpoint_name,
                    duration_ms,
                    status_code
                )
        
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:
            return async_wrapper
        return sync_wrapper
    
    return decorator
