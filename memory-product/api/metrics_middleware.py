"""
Performance Metrics Middleware
Tracks endpoint performance and database health
"""
import sys
import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger("zerolatency.metrics")

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# In-memory metrics (survives between requests, not between restarts)
_metrics = {
    "requests": defaultdict(int),
    "errors": defaultdict(int),
    "latency": defaultdict(list),
    "last_reset": datetime.now(timezone.utc)
}

def track_request(endpoint: str, status_code: int, latency_ms: int):
    """Track request metrics (in-memory)"""
    _metrics["requests"][endpoint] += 1
    
    if status_code >= 500:
        _metrics["errors"][endpoint] += 1
    
    # Keep last 100 latencies per endpoint for percentile calc
    _metrics["latency"][endpoint].append(latency_ms)
    if len(_metrics["latency"][endpoint]) > 100:
        _metrics["latency"][endpoint] = _metrics["latency"][endpoint][-100:]

def get_metrics_summary():
    """Get current metrics summary"""
    uptime = (datetime.now(timezone.utc) - _metrics["last_reset"]).total_seconds()
    
    summary = {
        "uptime_seconds": int(uptime),
        "total_requests": sum(_metrics["requests"].values()),
        "total_errors": sum(_metrics["errors"].values()),
        "endpoints": {}
    }
    
    for endpoint in _metrics["requests"]:
        latencies = _metrics["latency"].get(endpoint, [])
        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] if len(latencies_sorted) > 20 else latencies_sorted[-1]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)] if len(latencies_sorted) > 100 else latencies_sorted[-1]
        else:
            p50 = p95 = p99 = 0
        
        summary["endpoints"][endpoint] = {
            "requests": _metrics["requests"][endpoint],
            "errors": _metrics["errors"][endpoint],
            "error_rate": round(_metrics["errors"][endpoint] / _metrics["requests"][endpoint] * 100, 2) if _metrics["requests"][endpoint] > 0 else 0,
            "latency_p50": p50,
            "latency_p95": p95,
            "latency_p99": p99,
        }
    
    return summary

async def metrics_middleware(request, call_next):
    """Lightweight metrics tracking middleware"""
    if request.method == "OPTIONS":
        return await call_next(request)

    start_time = time.time()

    try:
        response = await call_next(request)
        
        latency_ms = int((time.time() - start_time) * 1000)
        endpoint = request.url.path
        
        # Track metrics
        track_request(endpoint, response.status_code, latency_ms)
        
        # Add metrics headers
        response.headers["X-Response-Time"] = f"{latency_ms}ms"
        
        return response
    except Exception as e:
        # Track error
        latency_ms = int((time.time() - start_time) * 1000)
        track_request(request.url.path, 500, latency_ms)
        raise
