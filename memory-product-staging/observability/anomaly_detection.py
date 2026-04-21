"""
Anomaly Detection - Statistical pattern detection for 0Latency API
Detects unusual patterns in error rates, latency, and usage
"""
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass

logger = logging.getLogger("0latency.anomaly")


@dataclass
class Anomaly:
    """Represents a detected anomaly"""
    type: str  # error_spike, latency_spike, usage_drop, etc.
    severity: str  # low, medium, high, critical
    metric: str  # What metric triggered it
    current_value: float
    baseline_value: float
    deviation_percent: float
    timestamp: datetime
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'severity': self.severity,
            'metric': self.metric,
            'current_value': self.current_value,
            'baseline_value': self.baseline_value,
            'deviation_percent': self.deviation_percent,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context
        }


class AnomalyDetector:
    """
    Statistical anomaly detection using rolling baselines
    Uses simple but effective techniques:
    - Z-score for outlier detection
    - Rate of change analysis
    - Threshold-based alerts
    """
    
    def __init__(self, window_minutes: int = 60):
        """
        Args:
            window_minutes: Size of rolling window for baseline calculation
        """
        self.window_minutes = window_minutes
        
        # Historical data (metric_name -> deque of (timestamp, value))
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Detected anomalies (last 24 hours)
        self.recent_anomalies: deque = deque(maxlen=1000)
        
        # Sensitivity thresholds (how many std deviations = anomaly)
        self.sensitivity = {
            'error_rate': 2.0,  # 2 std devs
            'latency': 2.5,     # 2.5 std devs
            'usage': 3.0,       # 3 std devs (less sensitive to usage changes)
        }
    
    def record_metric(self, metric_name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a metric value for baseline tracking"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        self.history[metric_name].append((timestamp, value))
    
    def get_baseline_stats(self, metric_name: str) -> Optional[Tuple[float, float]]:
        """
        Calculate baseline mean and std dev for a metric
        Returns: (mean, std_dev) or None if insufficient data
        """
        if metric_name not in self.history:
            return None
        
        # Filter to recent window
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes)
        recent_values = [
            value for timestamp, value in self.history[metric_name]
            if timestamp > cutoff
        ]
        
        if len(recent_values) < 5:  # Need minimum data points
            return None
        
        mean = statistics.mean(recent_values)
        
        if len(recent_values) < 2:
            return (mean, 0.0)
        
        std_dev = statistics.stdev(recent_values)
        return (mean, std_dev)
    
    def detect_anomaly(
        self,
        metric_name: str,
        current_value: float,
        category: str = 'error_rate',  # error_rate, latency, usage
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Anomaly]:
        """
        Detect if current value is anomalous compared to baseline
        
        Args:
            metric_name: Name of the metric
            current_value: Current observed value
            category: Category for sensitivity threshold
            context: Additional context about the measurement
            
        Returns:
            Anomaly object if anomaly detected, None otherwise
        """
        # Record this measurement
        self.record_metric(metric_name, current_value)
        
        # Get baseline stats
        baseline_stats = self.get_baseline_stats(metric_name)
        if not baseline_stats:
            logger.debug(f"Insufficient data for anomaly detection: {metric_name}")
            return None
        
        mean, std_dev = baseline_stats
        
        # Avoid division by zero
        if std_dev == 0:
            # If current value differs from constant baseline, it's anomalous
            if abs(current_value - mean) > mean * 0.5:  # 50% change
                deviation_pct = ((current_value - mean) / (mean or 1)) * 100
                severity = self._calculate_severity(abs(deviation_pct))
                
                anomaly = Anomaly(
                    type='sudden_change',
                    severity=severity,
                    metric=metric_name,
                    current_value=current_value,
                    baseline_value=mean,
                    deviation_percent=deviation_pct,
                    timestamp=datetime.now(timezone.utc),
                    context=context or {}
                )
                
                self.recent_anomalies.append(anomaly)
                return anomaly
            
            return None
        
        # Calculate z-score (number of standard deviations from mean)
        z_score = (current_value - mean) / std_dev
        
        # Check against threshold
        threshold = self.sensitivity.get(category, 2.5)
        
        if abs(z_score) > threshold:
            # Anomaly detected!
            deviation_pct = ((current_value - mean) / mean) * 100
            severity = self._calculate_severity(abs(z_score), threshold)
            
            # Determine anomaly type
            if z_score > 0:
                anomaly_type = f"{category}_spike"
            else:
                anomaly_type = f"{category}_drop"
            
            anomaly = Anomaly(
                type=anomaly_type,
                severity=severity,
                metric=metric_name,
                current_value=current_value,
                baseline_value=mean,
                deviation_percent=deviation_pct,
                timestamp=datetime.now(timezone.utc),
                context=context or {
                    'z_score': round(z_score, 2),
                    'std_dev': round(std_dev, 2),
                    'threshold': threshold
                }
            )
            
            self.recent_anomalies.append(anomaly)
            logger.warning(
                f"ANOMALY DETECTED: {anomaly.type} - {metric_name} = {current_value:.2f} "
                f"(baseline: {mean:.2f}, z-score: {z_score:.2f})"
            )
            
            return anomaly
        
        return None
    
    def _calculate_severity(self, z_score_or_pct: float, threshold: float = 2.0) -> str:
        """Calculate severity level based on deviation magnitude"""
        if z_score_or_pct > threshold * 2.5:
            return 'critical'
        elif z_score_or_pct > threshold * 1.5:
            return 'high'
        elif z_score_or_pct > threshold:
            return 'medium'
        else:
            return 'low'
    
    def check_error_rate_anomaly(self, current_error_rate: float, endpoint: str = "global") -> Optional[Anomaly]:
        """Convenience method for error rate anomaly detection"""
        return self.detect_anomaly(
            metric_name=f"error_rate_{endpoint}",
            current_value=current_error_rate,
            category='error_rate',
            context={'endpoint': endpoint}
        )
    
    def check_latency_anomaly(self, current_latency_ms: float, endpoint: str) -> Optional[Anomaly]:
        """Convenience method for latency anomaly detection"""
        return self.detect_anomaly(
            metric_name=f"latency_{endpoint}",
            current_value=current_latency_ms,
            category='latency',
            context={'endpoint': endpoint}
        )
    
    def check_usage_anomaly(self, current_request_rate: float, endpoint: str = "global") -> Optional[Anomaly]:
        """Convenience method for usage anomaly detection"""
        return self.detect_anomaly(
            metric_name=f"usage_{endpoint}",
            current_value=current_request_rate,
            category='usage',
            context={'endpoint': endpoint}
        )
    
    def get_recent_anomalies(self, hours: int = 24, severity: Optional[str] = None) -> List[Anomaly]:
        """
        Get recent anomalies
        
        Args:
            hours: Look back this many hours
            severity: Filter by severity (low/medium/high/critical)
            
        Returns:
            List of anomalies
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        anomalies = [
            a for a in self.recent_anomalies
            if a.timestamp > cutoff
        ]
        
        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]
        
        return sorted(anomalies, key=lambda a: a.timestamp, reverse=True)
    
    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get summary of recent anomalies"""
        recent = self.get_recent_anomalies(hours=24)
        
        # Group by type
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        
        for anomaly in recent:
            by_type[anomaly.type] += 1
            by_severity[anomaly.severity] += 1
        
        return {
            'total_anomalies_24h': len(recent),
            'by_type': dict(by_type),
            'by_severity': dict(by_severity),
            'critical_count': by_severity.get('critical', 0),
            'high_count': by_severity.get('high', 0),
            'last_anomaly': recent[0].to_dict() if recent else None
        }


# Global instance
_anomaly_detector = AnomalyDetector(window_minutes=60)


def check_error_rate_anomaly(current_error_rate: float, endpoint: str = "global") -> Optional[Anomaly]:
    """Check if current error rate is anomalous"""
    return _anomaly_detector.check_error_rate_anomaly(current_error_rate, endpoint)


def check_latency_anomaly(current_latency_ms: float, endpoint: str) -> Optional[Anomaly]:
    """Check if current latency is anomalous"""
    return _anomaly_detector.check_latency_anomaly(current_latency_ms, endpoint)


def check_usage_anomaly(current_request_rate: float, endpoint: str = "global") -> Optional[Anomaly]:
    """Check if current request rate is anomalous"""
    return _anomaly_detector.check_usage_anomaly(current_request_rate, endpoint)


def get_recent_anomalies(hours: int = 24, severity: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get recent anomalies"""
    anomalies = _anomaly_detector.get_recent_anomalies(hours, severity)
    return [a.to_dict() for a in anomalies]


def get_anomaly_summary() -> Dict[str, Any]:
    """Get summary of recent anomalies"""
    return _anomaly_detector.get_anomaly_summary()
