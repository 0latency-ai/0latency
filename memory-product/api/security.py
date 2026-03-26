"""
Security endpoints and Sentinel integration for Zero Latency Memory API.

0Latency Sentinel: Automatic credential detection and data loss prevention for AI memory.

Scans inbound memory content for API keys, tokens, passwords, PII, and other
secrets before storage. Supports per-tenant configuration:
  - warn:   Flag detections in response, store original (default)
  - redact: Replace secrets with [REDACTED], store redacted version
  - block:  Refuse to store content with secrets
  - off:    No scanning
"""
import sys
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel import (
    SentinelScanner, SentinelResult, SentinelMode, SentinelAction,
    SentinelAuditLogger, SentinelFinding, Confidence,
    scan_message, SECRET_PATTERNS, SENTINEL_PATTERNS,
)

logger = logging.getLogger("sentinel.api")

router = APIRouter()

# Global scanner instance
_scanner = SentinelScanner()

# Audit logger (initialized lazily with DB connection)
_audit_logger: Optional[SentinelAuditLogger] = None


def _get_audit_logger() -> SentinelAuditLogger:
    """Get or create audit logger with DB connection."""
    global _audit_logger
    if _audit_logger is None:
        try:
            from storage_multitenant import _db_execute_rows
            _audit_logger = SentinelAuditLogger(db_execute_fn=_db_execute_rows)
        except Exception:
            _audit_logger = SentinelAuditLogger()
    return _audit_logger


def _get_tenant_sentinel_mode(tenant: dict) -> SentinelMode:
    """Get sentinel mode for a tenant. Defaults to WARN."""
    mode_str = tenant.get("sentinel_mode", "warn")
    try:
        return SentinelMode(mode_str)
    except ValueError:
        return SentinelMode.WARN


# ═══════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════

class ScanRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)


class ScanFinding(BaseModel):
    pattern: str
    pattern_category: str = "unknown"
    description: str
    confidence: str = "medium"
    redacted: str
    position: int
    length: int


class ScanResponse(BaseModel):
    secrets_found: int
    findings: list[ScanFinding]
    clean: bool


class SentinelResultResponse(BaseModel):
    """Sentinel scan result included in memory storage responses."""
    detected: list[dict]
    action: str
    mode: str
    secrets_found: int
    high_confidence: int
    has_secrets: bool
    scan_time_ms: int


class PatternInfo(BaseModel):
    name: str
    category: str
    description: str
    confidence: str


class PatternsResponse(BaseModel):
    total_patterns: int
    patterns: list[PatternInfo]


class MetricsResponse(BaseModel):
    period_days: int
    total_detections: int
    by_category: dict
    by_action: dict
    daily_breakdown: list[dict]


# ═══════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════

@router.post("/api/v1/scan", response_model=ScanResponse, tags=["Security"])
async def scan_text(req: ScanRequest):
    """Scan text for potential secrets. Returns detected secrets (redacted).
    
    No authentication required — public utility endpoint.
    Use for pre-flight checks before storing memory content.
    """
    result = _scanner.scan(req.text)
    return ScanResponse(
        secrets_found=len(result.detected),
        findings=[
            ScanFinding(
                pattern=f.pattern_name,
                pattern_category=f.pattern_category,
                description=f.description,
                confidence=f.confidence.value,
                redacted=f.redacted,
                position=f.position,
                length=f.length,
            )
            for f in result.detected
        ],
        clean=not result.has_secrets,
    )


@router.get("/api/v1/security/patterns", response_model=PatternsResponse, tags=["Security"])
async def list_security_patterns():
    """Returns the list of secret patterns Sentinel scans for.
    
    Transparency: shows exactly what 0Latency detects to prevent
    accidental secret storage in AI memory.
    """
    patterns = [
        PatternInfo(
            name=name, 
            category=cat,
            description=desc,
            confidence=conf.value,
        )
        for name, cat, _regex, desc, conf in SENTINEL_PATTERNS
    ]
    return PatternsResponse(
        total_patterns=len(patterns),
        patterns=patterns,
    )


@router.get("/api/v1/sentinel/metrics", tags=["Security"])
async def sentinel_metrics(
    days: int = Query(7, ge=1, le=90),
):
    """Get Sentinel detection metrics. Dashboard-ready aggregations.
    
    Returns detections per day, by category, by action taken.
    SOC2/compliance: Data Loss Prevention (DLP) metrics for AI Memory.
    """
    audit = _get_audit_logger()
    metrics = audit.get_metrics(days=days)
    return metrics


# ═══════════════════════════════════════════════════
# Middleware / Guard Functions
# ═══════════════════════════════════════════════════

def check_for_secrets(text: str, field_name: str = "content") -> None:
    """Legacy guard: Raises HTTPException 422 if secrets found.
    
    Used as a hard-block guard in extraction endpoints.
    For mode-aware behavior, use sentinel_scan() instead.
    """
    if not text:
        return
    
    result = _scanner.scan(text, mode=SentinelMode.BLOCK)
    if result.has_secrets:
        pattern_names = list(set(f.pattern_name for f in result.detected))
        raise HTTPException(
            status_code=422,
            detail=(
                f"Sentinel: Secret detected in '{field_name}' — refusing to store. "
                f"Found {len(result.detected)} potential secret(s) ({', '.join(pattern_names)}). "
                f"Please remove the secret and retry. "
                f"To change this behavior, set sentinel_mode to 'warn' or 'redact'."
            ),
        )


def sentinel_scan(
    text: str, 
    tenant: dict, 
    endpoint: str,
    agent_id: str = None,
    field_name: str = "content",
) -> tuple[str, Optional[dict]]:
    """Mode-aware sentinel scan for memory storage endpoints.
    
    Returns:
        (text_to_store, sentinel_response_dict)
        - text_to_store: original text or redacted text depending on mode
        - sentinel_response_dict: sentinel info to include in API response (None if clean)
    
    Raises:
        HTTPException 422 if mode is 'block' and secrets detected
    """
    if not text:
        return text, None
    
    mode = _get_tenant_sentinel_mode(tenant)
    
    if mode == SentinelMode.OFF:
        return text, None
    
    result = _scanner.scan(text, mode=mode)
    
    if not result.has_secrets:
        return text, None
    
    # Log the detection
    audit = _get_audit_logger()
    audit.log_detection(
        tenant_id=tenant.get("id", "unknown"),
        endpoint=endpoint,
        result=result,
        agent_id=agent_id,
    )
    
    # Build response dict
    sentinel_response = result.to_dict()
    
    if mode == SentinelMode.BLOCK:
        pattern_names = list(set(f.pattern_name for f in result.detected))
        raise HTTPException(
            status_code=422,
            detail={
                "error": "sentinel_blocked",
                "message": (
                    f"Sentinel: {len(result.detected)} secret(s) detected in '{field_name}' — "
                    f"storage blocked by policy. Types: {', '.join(pattern_names)}. "
                    f"Remove secrets and retry, or change sentinel_mode to 'warn' or 'redact'."
                ),
                "sentinel": sentinel_response,
            },
        )
    
    if mode == SentinelMode.REDACT:
        # Return redacted text for storage
        return result.redacted_text or text, sentinel_response
    
    # WARN mode: return original text, but include sentinel info in response
    return text, sentinel_response
