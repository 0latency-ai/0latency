#!/usr/bin/env python3
"""
0Latency Sentinel — Automatic credential detection and data loss prevention for AI memory.

Enterprise-grade DLP (Data Loss Prevention) that scans all inbound memory content for:
- API keys (AWS, OpenAI, Anthropic, Stripe, GitHub, Google, Slack, etc.)
- OAuth tokens, JWTs, bearer tokens
- Passwords in plaintext
- Social Security Numbers (SSNs)
- Credit card numbers (with Luhn validation)
- Private keys (RSA, SSH, PGP)
- Database connection strings with embedded credentials
- Generic high-entropy secrets

Each detection includes:
- Type classification
- Confidence scoring (high/medium/low)
- Character-level location
- Redacted version (safe for logging)

Usage:
    from sentinel import SentinelScanner
    scanner = SentinelScanner()
    result = scanner.scan("my text with sk-abc123...")
    # result.detected -> list of findings
    # result.has_secrets -> bool
    # result.redacted_text -> text with secrets replaced
"""

import re
import math
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("sentinel")


# ═══════════════════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════════════════

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SentinelMode(str, Enum):
    WARN = "warn"        # Flag + warn, store original
    REDACT = "redact"    # Replace secrets with [REDACTED], store redacted version
    BLOCK = "block"      # Refuse to store
    OFF = "off"          # No scanning


class SentinelAction(str, Enum):
    FLAGGED = "flagged"
    REDACTED = "redacted"
    BLOCKED = "blocked"
    CLEAN = "clean"


@dataclass
class SentinelFinding:
    """A single detected secret/credential."""
    pattern_name: str
    pattern_category: str  # e.g. "api_key", "token", "credential", "pii"
    description: str
    confidence: Confidence
    position: int
    length: int
    redacted: str          # Safe-to-log redacted version
    
    def to_dict(self) -> dict:
        return {
            "pattern_name": self.pattern_name,
            "pattern_category": self.pattern_category,
            "description": self.description,
            "confidence": self.confidence.value,
            "position": self.position,
            "length": self.length,
            "redacted": self.redacted,
        }


@dataclass
class SentinelResult:
    """Complete scan result."""
    detected: list[SentinelFinding] = field(default_factory=list)
    action: SentinelAction = SentinelAction.CLEAN
    mode: SentinelMode = SentinelMode.WARN
    redacted_text: Optional[str] = None
    scan_time_ms: int = 0
    
    @property
    def has_secrets(self) -> bool:
        return len(self.detected) > 0
    
    @property
    def high_confidence_count(self) -> int:
        return sum(1 for d in self.detected if d.confidence == Confidence.HIGH)
    
    def to_dict(self) -> dict:
        return {
            "detected": [d.to_dict() for d in self.detected],
            "action": self.action.value,
            "mode": self.mode.value,
            "secrets_found": len(self.detected),
            "high_confidence": self.high_confidence_count,
            "has_secrets": self.has_secrets,
            "scan_time_ms": self.scan_time_ms,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Pattern Definitions
# ═══════════════════════════════════════════════════════════════════════════════

# (name, category, regex, description, confidence)
SENTINEL_PATTERNS: list[tuple[str, str, str, str, Confidence]] = [
    # ── API Keys (HIGH confidence — distinctive prefixes) ─────────────────
    ("AWS Access Key", "api_key", r'\bAKIA[A-Z0-9]{16}\b', "AWS IAM access key ID", Confidence.HIGH),
    ("AWS Secret Key", "api_key", r'(?i)(?:aws_secret_access_key|aws_secret)\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})["\']?', "AWS secret access key", Confidence.HIGH),
    ("OpenAI Key", "api_key", r'\bsk-[A-Za-z0-9]{20,}\b', "OpenAI API key", Confidence.HIGH),
    ("Anthropic Key", "api_key", r'\bsk-ant-[A-Za-z0-9_-]{20,}\b', "Anthropic API key", Confidence.HIGH),
    ("Stripe Secret", "api_key", r'\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b', "Stripe secret key", Confidence.HIGH),
    ("Stripe Publishable", "api_key", r'\bpk_(?:live|test)_[A-Za-z0-9]{24,}\b', "Stripe publishable key", Confidence.MEDIUM),
    ("Stripe Restricted", "api_key", r'\brk_(?:live|test)_[A-Za-z0-9]{24,}\b', "Stripe restricted key", Confidence.HIGH),
    ("GitHub PAT", "api_key", r'\bghp_[A-Za-z0-9]{36,}\b', "GitHub personal access token", Confidence.HIGH),
    ("GitHub OAuth", "api_key", r'\bgho_[A-Za-z0-9]{36,}\b', "GitHub OAuth access token", Confidence.HIGH),
    ("GitHub User-to-Server", "api_key", r'\bghu_[A-Za-z0-9]{36,}\b', "GitHub user-to-server token", Confidence.HIGH),
    ("GitHub Server-to-Server", "api_key", r'\bghs_[A-Za-z0-9]{36,}\b', "GitHub server-to-server token", Confidence.HIGH),
    ("GitHub Refresh", "api_key", r'\bghr_[A-Za-z0-9]{36,}\b', "GitHub refresh token", Confidence.HIGH),
    ("GitHub Fine-Grained PAT", "api_key", r'\bgithub_pat_[A-Za-z0-9_]{50,}\b', "GitHub fine-grained personal access token", Confidence.HIGH),
    ("Google API Key", "api_key", r'\bAIza[A-Za-z0-9_-]{35}\b', "Google API key", Confidence.HIGH),
    ("Slack Bot Token", "api_key", r'\bxoxb-[0-9]{10,}-[A-Za-z0-9-]+\b', "Slack bot token", Confidence.HIGH),
    ("Slack User Token", "api_key", r'\bxoxp-[0-9]{10,}-[A-Za-z0-9-]+\b', "Slack user token", Confidence.HIGH),
    ("Slack App Token", "api_key", r'\bxoxa-[0-9]{10,}-[A-Za-z0-9-]+\b', "Slack app token", Confidence.HIGH),
    ("Twilio Account SID", "api_key", r'\bAC[a-f0-9]{32}\b', "Twilio account SID", Confidence.HIGH),
    ("Twilio API Key", "api_key", r'\bSK[a-f0-9]{32}\b', "Twilio API key", Confidence.HIGH),
    ("SendGrid Key", "api_key", r'\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b', "SendGrid API key", Confidence.HIGH),
    ("Supabase Key", "api_key", r'\bsbp_[A-Za-z0-9]{40,}\b', "Supabase project key", Confidence.HIGH),
    ("Supabase Secret", "api_key", r'\bsb_secret_[A-Za-z0-9_-]{20,}\b', "Supabase service role secret", Confidence.HIGH),
    ("PyPI Token", "api_key", r'\bpypi-[A-Za-z0-9_-]{50,}\b', "PyPI API token", Confidence.HIGH),
    ("npm Token", "api_key", r'\bnpm_[A-Za-z0-9]{36,}\b', "npm access token", Confidence.HIGH),
    ("Heroku API Key", "api_key", r'(?i)heroku[_\s]*api[_\s]*key\s*[=:]\s*["\']?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})["\']?', "Heroku API key", Confidence.HIGH),
    ("Mailgun Key", "api_key", r'\bkey-[a-f0-9]{32}\b', "Mailgun API key", Confidence.HIGH),
    ("Supadata Key", "api_key", r'\bsd_[a-f0-9]{32,}\b', "Supadata API key", Confidence.HIGH),
    ("ZeroBounce Key", "api_key", r'\bzb_[A-Za-z0-9]{20,}\b', "ZeroBounce API key", Confidence.HIGH),
    
    # ── Tokens (HIGH confidence) ──────────────────────────────────────────
    ("JWT", "token", r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b', "JSON Web Token", Confidence.HIGH),
    ("Bearer Token", "token", r'[Bb]earer\s+[A-Za-z0-9_\-.]{20,}', "Bearer authorization token", Confidence.HIGH),
    ("Basic Auth", "token", r'[Bb]asic\s+[A-Za-z0-9+/=]{20,}', "Basic authentication header (base64 encoded credentials)", Confidence.HIGH),
    ("OAuth Token", "token", r'(?i)(?:access_token|oauth_token)\s*[=:]\s*["\']?([A-Za-z0-9_\-.]{20,})["\']?', "OAuth access token", Confidence.MEDIUM),
    
    # ── Private Keys (HIGH confidence) ────────────────────────────────────
    ("RSA Private Key", "private_key", r'-----BEGIN RSA PRIVATE KEY-----', "RSA private key header", Confidence.HIGH),
    ("EC Private Key", "private_key", r'-----BEGIN EC PRIVATE KEY-----', "EC private key header", Confidence.HIGH),
    ("DSA Private Key", "private_key", r'-----BEGIN DSA PRIVATE KEY-----', "DSA private key header", Confidence.HIGH),
    ("Generic Private Key", "private_key", r'-----BEGIN PRIVATE KEY-----', "PKCS#8 private key header", Confidence.HIGH),
    ("PGP Private Key", "private_key", r'-----BEGIN PGP PRIVATE KEY BLOCK-----', "PGP private key block", Confidence.HIGH),
    ("SSH Private Key", "private_key", r'-----BEGIN OPENSSH PRIVATE KEY-----', "OpenSSH private key", Confidence.HIGH),
    
    # ── Database Connection Strings (HIGH confidence) ─────────────────────
    ("Postgres Connection String", "connection_string", r'(?i)postgres(?:ql)?://[^\s:]+:[^\s@]+@[^\s/]+', "PostgreSQL connection string with credentials", Confidence.HIGH),
    ("MySQL Connection String", "connection_string", r'(?i)mysql://[^\s:]+:[^\s@]+@[^\s/]+', "MySQL connection string with credentials", Confidence.HIGH),
    ("MongoDB Connection String", "connection_string", r'(?i)mongodb(?:\+srv)?://[^\s:]+:[^\s@]+@[^\s/]+', "MongoDB connection string with credentials", Confidence.HIGH),
    ("Redis Connection String", "connection_string", r'(?i)redis://:[^\s@]+@[^\s/]+', "Redis connection string with password", Confidence.HIGH),
    ("Generic DB URL", "connection_string", r'(?i)(?:mysql|postgres|mongodb|redis|mssql|oracle)://[^\s]+:[^\s]+@', "Database URL with embedded credentials", Confidence.HIGH),
    
    # ── Passwords (MEDIUM confidence — can have false positives) ──────────
    ("Password Assignment", "credential", r'(?i)(?:password|passwd|pwd)\s*[=:]\s*["\']([^"\'\s]{8,})["\']', "Plaintext password assignment", Confidence.MEDIUM),
    ("Password Assignment Unquoted", "credential", r'(?i)(?:password|passwd|pwd)\s*[=:]\s*([^\s"\']{8,50})\b', "Plaintext password (unquoted)", Confidence.MEDIUM),
    
    # ── PII (MEDIUM-HIGH confidence) ──────────────────────────────────────
    ("SSN", "pii", r'\b\d{3}-\d{2}-\d{4}\b', "Social Security Number", Confidence.MEDIUM),
    ("Credit Card (Visa)", "pii", r'\b4[0-9]{12}(?:[0-9]{3})?\b', "Visa credit card number", Confidence.MEDIUM),
    ("Credit Card (Mastercard)", "pii", r'\b5[1-5][0-9]{14}\b', "Mastercard credit card number", Confidence.MEDIUM),
    ("Credit Card (Amex)", "pii", r'\b3[47][0-9]{13}\b', "American Express card number", Confidence.MEDIUM),
    ("Credit Card (Discover)", "pii", r'\b6(?:011|5[0-9]{2})[0-9]{12}\b', "Discover credit card number", Confidence.MEDIUM),
    
    # ── Generic Secrets (LOW-MEDIUM confidence) ───────────────────────────
    ("Generic Secret Assignment", "credential", r'(?i)(?:api[_-]?key|secret[_-]?key|auth[_-]?token|api[_-]?secret|client[_-]?secret)\s*[=:]\s*["\']?([A-Za-z0-9_\-./+=]{20,})["\']?', "Generic secret/key assignment", Confidence.MEDIUM),
    ("Environment Variable Secret", "credential", r'(?i)(?:export\s+)?(?:[A-Z_]*(?:SECRET|TOKEN|KEY|PASSWORD|CREDENTIAL|AUTH)[A-Z_]*)\s*=\s*["\']?([A-Za-z0-9_\-./+=]{16,})["\']?', "Secret in environment variable", Confidence.LOW),
]

# Compiled patterns for performance
_COMPILED_PATTERNS: list[tuple[str, str, re.Pattern, str, Confidence]] = [
    (name, cat, re.compile(pattern), desc, conf)
    for name, cat, pattern, desc, conf in SENTINEL_PATTERNS
]


# ═══════════════════════════════════════════════════════════════════════════════
# Luhn Check for Credit Cards
# ═══════════════════════════════════════════════════════════════════════════════

def _luhn_check(number: str) -> bool:
    """Validate a credit card number using the Luhn algorithm."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _shannon_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not text:
        return 0.0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


# ═══════════════════════════════════════════════════════════════════════════════
# Core Scanner
# ═══════════════════════════════════════════════════════════════════════════════

class SentinelScanner:
    """Enterprise-grade credential and secret detection scanner."""
    
    def __init__(self):
        self.patterns = _COMPILED_PATTERNS
    
    def _redact(self, secret: str) -> str:
        """Create a safe-to-log redacted version of a secret."""
        if len(secret) <= 8:
            return secret[:2] + "***"
        elif len(secret) <= 14:
            return secret[:4] + "..." + secret[-2:]
        else:
            return secret[:6] + "..." + secret[-4:]
    
    def _validate_credit_card(self, match: re.Match, text: str) -> bool:
        """Extra validation for credit card matches using Luhn + context."""
        number = match.group(0)
        # Must pass Luhn check
        if not _luhn_check(number):
            return False
        # Check it's not part of a longer number (phone, ID, etc.)
        start = match.start()
        end = match.end()
        if start > 0 and text[start - 1].isdigit():
            return False
        if end < len(text) and text[end].isdigit():
            return False
        return True
    
    def _validate_ssn(self, match: re.Match, text: str) -> bool:
        """Extra validation for SSN matches."""
        ssn = match.group(0)
        parts = ssn.split("-")
        area = int(parts[0])
        group = int(parts[1])
        serial = int(parts[2])
        # Invalid SSN ranges
        if area == 0 or area == 666 or area >= 900:
            return False
        if group == 0 or serial == 0:
            return False
        # Check for date-like context (YYYY-MM-DD pattern)
        start = match.start()
        if start >= 5 and re.match(r'\d{4}-', text[start-5:start]):
            return False
        return True
    
    def scan(self, text: str, mode: SentinelMode = SentinelMode.WARN) -> SentinelResult:
        """Scan text for secrets and credentials.
        
        Args:
            text: Content to scan
            mode: How to handle detections (warn/redact/block/off)
        
        Returns:
            SentinelResult with findings and action taken
        """
        import time
        start = time.time()
        
        if mode == SentinelMode.OFF:
            return SentinelResult(mode=mode, scan_time_ms=0)
        
        if not text or len(text) < 8:
            return SentinelResult(mode=mode, scan_time_ms=0)
        
        findings: list[SentinelFinding] = []
        seen_spans: set[tuple[int, int]] = set()  # Deduplicate overlapping matches
        
        for name, category, compiled, desc, confidence in self.patterns:
            for match in compiled.finditer(text):
                span = (match.start(), match.end())
                
                # Skip if this span overlaps with an already-found higher-priority match
                if any(s[0] <= span[0] and s[1] >= span[1] for s in seen_spans):
                    continue
                
                secret = match.group(0)
                
                # Extra validation for PII patterns
                if category == "pii":
                    if "Credit Card" in name:
                        if not self._validate_credit_card(match, text):
                            continue
                        # Upgrade to HIGH if Luhn passes
                        confidence = Confidence.HIGH
                    elif name == "SSN":
                        if not self._validate_ssn(match, text):
                            continue
                
                # For low-confidence patterns, check entropy
                if confidence == Confidence.LOW:
                    # Extract the actual secret value (might be in a capture group)
                    val = match.group(1) if match.lastindex else match.group(0)
                    if _shannon_entropy(val) < 3.0:
                        continue  # Too low entropy, probably not a real secret
                
                seen_spans.add(span)
                findings.append(SentinelFinding(
                    pattern_name=name,
                    pattern_category=category,
                    description=desc,
                    confidence=confidence,
                    position=match.start(),
                    length=len(secret),
                    redacted=self._redact(secret),
                ))
        
        # Sort by position
        findings.sort(key=lambda f: f.position)
        
        # Determine action
        if not findings:
            action = SentinelAction.CLEAN
        elif mode == SentinelMode.BLOCK:
            action = SentinelAction.BLOCKED
        elif mode == SentinelMode.REDACT:
            action = SentinelAction.REDACTED
        else:
            action = SentinelAction.FLAGGED
        
        # Build redacted text if needed
        redacted_text = None
        if findings and mode == SentinelMode.REDACT:
            redacted_text = self._build_redacted_text(text, findings)
        
        scan_time = int((time.time() - start) * 1000)
        
        return SentinelResult(
            detected=findings,
            action=action,
            mode=mode,
            redacted_text=redacted_text,
            scan_time_ms=scan_time,
        )
    
    def _build_redacted_text(self, text: str, findings: list[SentinelFinding]) -> str:
        """Replace detected secrets with [REDACTED:<type>] placeholders."""
        result = list(text)
        # Process in reverse order to maintain positions
        for finding in sorted(findings, key=lambda f: f.position, reverse=True):
            start = finding.position
            end = start + finding.length
            placeholder = f"[REDACTED:{finding.pattern_name}]"
            result[start:end] = list(placeholder)
        return "".join(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Logger
# ═══════════════════════════════════════════════════════════════════════════════

class SentinelAuditLogger:
    """Audit logger for Sentinel detections. Never logs the actual secret."""
    
    def __init__(self, db_execute_fn=None):
        """
        Args:
            db_execute_fn: Optional DB execution function for persistent logging.
                          Falls back to file-based logging if not provided.
        """
        self._db_execute = db_execute_fn
        self._log_path = "/root/logs/sentinel_audit.log"
    
    def log_detection(
        self,
        tenant_id: str,
        endpoint: str,
        result: SentinelResult,
        agent_id: str = None,
    ) -> None:
        """Log a sentinel detection event."""
        if not result.has_secrets:
            return
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        for finding in result.detected:
            entry = {
                "timestamp": timestamp,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "endpoint": endpoint,
                "pattern_name": finding.pattern_name,
                "pattern_category": finding.pattern_category,
                "confidence": finding.confidence.value,
                "action": result.action.value,
                "mode": result.mode.value,
                # NEVER log the actual secret — only the redacted version
                "redacted_preview": finding.redacted,
            }
            
            # Try DB logging first
            if self._db_execute:
                try:
                    self._db_execute("""
                        INSERT INTO memory_service.sentinel_audit_log 
                        (tenant_id, agent_id, endpoint, pattern_name, pattern_category, 
                         confidence, action_taken, mode, redacted_preview)
                        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tenant_id, agent_id, endpoint, finding.pattern_name,
                        finding.pattern_category, finding.confidence.value,
                        result.action.value, result.mode.value, finding.redacted,
                    ), tenant_id=tenant_id, fetch_results=False)
                except Exception as e:
                    logger.warning(f"Sentinel DB audit log failed: {e}")
                    self._file_log(entry)
            else:
                self._file_log(entry)
    
    def _file_log(self, entry: dict) -> None:
        """Fallback: log to file."""
        try:
            import os
            os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
            with open(self._log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Sentinel file audit log failed: {e}")
    
    def get_metrics(self, tenant_id: str = None, days: int = 7) -> dict:
        """Get detection metrics for dashboard display."""
        if not self._db_execute:
            return {"error": "DB not configured", "detections": []}
        
        try:
            if tenant_id:
                rows = self._db_execute("""
                    SELECT 
                        date_trunc('day', created_at) as day,
                        pattern_category,
                        action_taken,
                        COUNT(*) as count
                    FROM memory_service.sentinel_audit_log
                    WHERE tenant_id = %s::UUID 
                      AND created_at > now() - make_interval(days => %s)
                    GROUP BY day, pattern_category, action_taken
                    ORDER BY day DESC
                """, (tenant_id, days), tenant_id=tenant_id)
            else:
                rows = self._db_execute("""
                    SELECT 
                        date_trunc('day', created_at) as day,
                        pattern_category,
                        action_taken,
                        COUNT(*) as count
                    FROM memory_service.sentinel_audit_log
                    WHERE created_at > now() - make_interval(days => %s)
                    GROUP BY day, pattern_category, action_taken
                    ORDER BY day DESC
                """, (days,), tenant_id="00000000-0000-0000-0000-000000000000")
            
            detections = []
            for row in (rows or []):
                detections.append({
                    "day": str(row[0]),
                    "category": str(row[1]),
                    "action": str(row[2]),
                    "count": int(row[3]),
                })
            
            # Summary
            total = sum(d["count"] for d in detections)
            by_category = {}
            by_action = {}
            for d in detections:
                by_category[d["category"]] = by_category.get(d["category"], 0) + d["count"]
                by_action[d["action"]] = by_action.get(d["action"], 0) + d["count"]
            
            return {
                "period_days": days,
                "total_detections": total,
                "by_category": by_category,
                "by_action": by_action,
                "daily_breakdown": detections,
            }
        except Exception as e:
            logger.error(f"Sentinel metrics query failed: {e}")
            return {"error": str(e), "detections": []}


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton + Backward Compatibility
# ═══════════════════════════════════════════════════════════════════════════════

# Default scanner instance
_default_scanner = SentinelScanner()


def scan_message(text: str) -> list[dict]:
    """Backward-compatible wrapper: scan text, return list of finding dicts.
    
    This maintains compatibility with the existing secret_scanner.py interface.
    """
    result = _default_scanner.scan(text)
    return [
        {
            "pattern": f.pattern_name,
            "description": f.description,
            "redacted": f.redacted,
            "position": f.position,
            "length": f.length,
            "confidence": f.confidence.value,
            "category": f.pattern_category,
        }
        for f in result.detected
    ]


# Re-export for backward compat with secret_scanner.py consumers
SECRET_PATTERNS = [
    (name, pattern, desc) 
    for name, _cat, pattern, desc, _conf in SENTINEL_PATTERNS
]


def log_detection(findings: list[dict], source: str = "telegram"):
    """Backward-compatible log function."""
    log_path = "/root/logs/sentinel_audit.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    import os
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    for finding in findings:
        entry = {
            "timestamp": timestamp,
            "source": source,
            "pattern": finding.get("pattern", "unknown"),
            "description": finding.get("description", ""),
            "redacted": finding.get("redacted", ""),
            "confidence": finding.get("confidence", "medium"),
            "action": "detected_and_warned",
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


def format_warning(findings: list[dict]) -> str:
    """Format a user-friendly warning message."""
    types = list(set(f.get("pattern", "Unknown") for f in findings))
    warning = "⚠️ **Sentinel: Secret detected in memory content!**\n\n"
    warning += f"Found {len(findings)} potential secret(s): {', '.join(types)}\n\n"
    warning += "**Secrets should not be stored in AI memory.** Consider:\n"
    warning += "• Using environment variables or a secrets manager\n"
    warning += "• Removing credentials before storing the memory\n"
    warning += "• Using the redact mode to auto-strip secrets\n\n"
    warning += "If this was a real secret, **rotate it immediately**."
    return warning


# CLI
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read()
    
    scanner = SentinelScanner()
    result = scanner.scan(text)
    
    if result.has_secrets:
        print(f"🚨 Sentinel found {len(result.detected)} potential secret(s):")
        for f in result.detected:
            print(f"  [{f.confidence.value.upper()}] {f.pattern_name}: {f.redacted} ({f.description})")
        print()
        print(format_warning([d.to_dict() for d in result.detected]))
    else:
        print("✅ Sentinel: No secrets detected.")
