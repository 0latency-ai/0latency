"""
CP-SYNTHESIS-PERF Stage 1: Profiling instrumentation wrapper.

Non-invasive profiler that collects phase timing data from synthesis operations.
Uses Python logging infrastructure to capture existing perf_logger emissions.
"""

import time
import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Any
from contextlib import contextmanager


@dataclass
class PhaseRecord:
    """Record of a single timed phase."""
    phase_name: str
    duration_ms: int
    metadata: dict[str, Any]


class SynthesisProfiler:
    """Collects phase timing data from synthesis writer + clustering."""
    
    def __init__(self):
        self.phases: list[PhaseRecord] = []
        self.wall_clock_start: Optional[float] = None
        self.wall_clock_end: Optional[float] = None
        self._log_handler = None
    
    def start(self):
        """Start wall-clock timer and attach log handler."""
        self.wall_clock_start = time.perf_counter()
        
        # Attach custom log handler to capture perf_logger emissions
        perf_logger = logging.getLogger("synthesis.perf")
        self._log_handler = _ProfilerLogHandler(self)
        perf_logger.addHandler(self._log_handler)
        perf_logger.setLevel(logging.INFO)
    
    def stop(self):
        """Stop wall-clock timer and detach log handler."""
        self.wall_clock_end = time.perf_counter()
        
        if self._log_handler:
            perf_logger = logging.getLogger("synthesis.perf")
            perf_logger.removeHandler(self._log_handler)
            self._log_handler = None
    
    @property
    def wall_clock_ms(self) -> int:
        """Total wall-clock time in milliseconds."""
        if self.wall_clock_start is None or self.wall_clock_end is None:
            return 0
        return int((self.wall_clock_end - self.wall_clock_start) * 1000)
    
    def add_phase(self, name: str, duration_ms: int, **metadata):
        """Manually add a phase record."""
        record = PhaseRecord(
            phase_name=name,
            duration_ms=duration_ms,
            metadata=metadata
        )
        self.phases.append(record)
    
    def to_dict(self) -> dict:
        """Export profiler data as dictionary."""
        return {
            "wall_clock_ms": self.wall_clock_ms,
            "phases": [asdict(p) for p in self.phases]
        }


class _ProfilerLogHandler(logging.Handler):
    """Logging handler that captures perf_logger emissions."""
    
    def __init__(self, profiler: SynthesisProfiler):
        super().__init__()
        self.profiler = profiler
    
    def emit(self, record):
        """Capture log records from perf_logger."""
        try:
            # Parse JSON log message
            msg = record.getMessage()
            data = json.loads(msg)
            
            # Extract phase info
            if data.get("metric") == "synthesis_perf" and "phase" in data:
                phase_name = data["phase"]
                duration_ms = data.get("duration_ms", 0)
                
                # Extract metadata (everything except metric, phase, duration_ms)
                metadata = {
                    k: v for k, v in data.items()
                    if k not in ["metric", "phase", "duration_ms"]
                }
                
                # Add to profiler
                self.profiler.add_phase(phase_name, duration_ms, **metadata)
        
        except (json.JSONDecodeError, KeyError, ValueError):
            # Not a JSON perf log - ignore
            pass


@contextmanager
def profile_synthesis(tenant_id: str, agent_id: str):
    """Context manager for profiling a synthesis operation.
    
    Usage:
        with profile_synthesis(tenant_id, agent_id) as profiler:
            result = synthesize_cluster(...)
        
        report = profiler.to_dict()
    """
    profiler = SynthesisProfiler()
    profiler.start()
    try:
        yield profiler
    finally:
        profiler.stop()
