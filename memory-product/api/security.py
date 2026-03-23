"""
Security endpoints and secret scanning middleware for Zero Latency Memory API.
Scans inbound memory content for accidental secret storage and provides
transparency into the patterns we detect.
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from secret_scanner import scan_message, SECRET_PATTERNS

router = APIRouter()


# --- Models ---

class ScanRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)


class ScanFinding(BaseModel):
    pattern: str
    description: str
    redacted: str
    position: int
    length: int


class ScanResponse(BaseModel):
    secrets_found: int
    findings: list[ScanFinding]
    clean: bool


class PatternInfo(BaseModel):
    name: str
    description: str


class PatternsResponse(BaseModel):
    total_patterns: int
    patterns: list[PatternInfo]


# --- Endpoints ---

@router.post("/api/v1/scan", response_model=ScanResponse, tags=["Security"])
async def scan_text(req: ScanRequest):
    """Scan text for potential secrets. Returns detected secrets (redacted).
    
    No authentication required — this is a public utility endpoint.
    Useful for pre-flight checks before storing memory content.
    """
    findings = scan_message(req.text)
    return ScanResponse(
        secrets_found=len(findings),
        findings=[ScanFinding(**f) for f in findings],
        clean=len(findings) == 0,
    )


@router.get("/api/v1/security/patterns", response_model=PatternsResponse, tags=["Security"])
async def list_security_patterns():
    """Returns the list of secret patterns we scan for.
    
    Transparency feature — shows exactly what 0Latency detects
    to prevent accidental secret storage in agent memory.
    """
    patterns = [
        PatternInfo(name=name, description=desc)
        for name, _regex, desc in SECRET_PATTERNS
    ]
    return PatternsResponse(
        total_patterns=len(patterns),
        patterns=patterns,
    )


# --- Middleware helper for extraction endpoints ---

def check_for_secrets(text: str, field_name: str = "content") -> None:
    """Check text for secrets. Raises HTTPException 422 if secrets found.
    
    Used as a guard in extraction endpoints to prevent accidental
    secret storage in agent memory.
    """
    if not text:
        return
    
    findings = scan_message(text)
    if findings:
        pattern_names = list(set(f["pattern"] for f in findings))
        raise HTTPException(
            status_code=422,
            detail=(
                f"Secret detected in memory content — refusing to store. "
                f"Found {len(findings)} potential secret(s) ({', '.join(pattern_names)}). "
                f"Please remove the secret and retry."
            ),
        )
