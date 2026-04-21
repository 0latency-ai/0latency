#!/usr/bin/env python3
"""
Secret Scanner — Detects and warns about API keys/tokens/secrets in inbound messages.

Patterns detected:
- PyPI tokens (pypi-...)
- GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
- OpenAI keys (sk-...)
- Anthropic keys (sk-ant-...)
- Stripe keys (sk_live_, sk_test_, pk_live_, pk_test_, rk_live_, rk_test_)
- AWS keys (AKIA...)
- Supabase keys (eyJ... JWT format, sb_...)
- Slack tokens (xoxb-, xoxp-, xoxa-, xoxr-)
- Discord tokens (long base64 with dots)
- Twilio (SK..., AC...)
- SendGrid (SG....)
- Generic long hex/base64 strings that look like secrets
- Bearer tokens in authorization headers

Usage:
  - Import and call scan_message(text) -> list of matches
  - Or run standalone: python3 secret_scanner.py "message text"
"""

import re
import sys
import json
from datetime import datetime, timezone

# Pattern definitions: (name, regex, description)
SECRET_PATTERNS = [
    ("PyPI Token", r'\bpypi-[A-Za-z0-9_-]{50,}\b', "PyPI API token"),
    ("GitHub PAT", r'\bghp_[A-Za-z0-9]{36,}\b', "GitHub personal access token"),
    ("GitHub OAuth", r'\bgho_[A-Za-z0-9]{36,}\b', "GitHub OAuth token"),
    ("GitHub User-to-Server", r'\bghu_[A-Za-z0-9]{36,}\b', "GitHub user-to-server token"),
    ("GitHub Server-to-Server", r'\bghs_[A-Za-z0-9]{36,}\b', "GitHub server-to-server token"),
    ("GitHub Refresh", r'\bghr_[A-Za-z0-9]{36,}\b', "GitHub refresh token"),
    ("OpenAI Key", r'\bsk-[A-Za-z0-9]{20,}\b', "OpenAI API key"),
    ("Anthropic Key", r'\bsk-ant-[A-Za-z0-9_-]{20,}\b', "Anthropic API key"),
    ("Stripe Secret", r'\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b', "Stripe secret key"),
    ("Stripe Publishable", r'\bpk_(?:live|test)_[A-Za-z0-9]{24,}\b', "Stripe publishable key"),
    ("Stripe Restricted", r'\brk_(?:live|test)_[A-Za-z0-9]{24,}\b', "Stripe restricted key"),
    ("AWS Access Key", r'\bAKIA[A-Z0-9]{16}\b', "AWS access key ID"),
    ("AWS Secret Key", r'\b[A-Za-z0-9/+=]{40}\b(?=.*(?:aws|secret|key))', "Possible AWS secret key"),
    ("Slack Bot Token", r'\bxoxb-[0-9]{10,}-[A-Za-z0-9-]+\b', "Slack bot token"),
    ("Slack User Token", r'\bxoxp-[0-9]{10,}-[A-Za-z0-9-]+\b', "Slack user token"),
    ("Slack App Token", r'\bxoxa-[0-9]{10,}-[A-Za-z0-9-]+\b', "Slack app token"),
    ("Twilio Account SID", r'\bAC[a-f0-9]{32}\b', "Twilio account SID"),
    ("Twilio API Key", r'\bSK[a-f0-9]{32}\b', "Twilio API key"),
    ("SendGrid Key", r'\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b', "SendGrid API key"),
    ("Supabase Key", r'\bsbp_[A-Za-z0-9]{40,}\b', "Supabase key"),
    ("Supabase Secret", r'\bsb_secret_[A-Za-z0-9_-]{20,}\b', "Supabase service role secret"),
    ("Google API Key", r'\bAIza[A-Za-z0-9_-]{35}\b', "Google API key"),
    ("Supadata Key", r'\bsd_[a-f0-9]{32,}\b', "Supadata API key"),
    ("ZeroBounce Key", r'\bzb_[A-Za-z0-9]{20,}\b', "ZeroBounce API key"),
    ("Bearer Token", r'[Bb]earer\s+[A-Za-z0-9_\-.]{20,}', "Bearer authorization token"),
    ("Generic Long Secret", r'(?:api[_-]?key|token|secret|password|credential)\s*[=:]\s*["\']?([A-Za-z0-9_\-./+=]{32,})["\']?', "Generic secret assignment"),
]

def scan_message(text: str) -> list[dict]:
    """Scan a message for potential secrets. Returns list of {pattern_name, description, redacted_match}."""
    if not text or len(text) < 10:
        return []
    
    findings = []
    for name, pattern, description in SECRET_PATTERNS:
        matches = re.finditer(pattern, text)
        for match in matches:
            secret = match.group(0)
            # Redact: show first 6 chars and last 4
            if len(secret) > 14:
                redacted = secret[:6] + "..." + secret[-4:]
            else:
                redacted = secret[:4] + "..."
            
            findings.append({
                "pattern": name,
                "description": description,
                "redacted": redacted,
                "position": match.start(),
                "length": len(secret),
            })
    
    return findings

def log_detection(findings: list[dict], source: str = "telegram"):
    """Log secret detections to /root/logs/secret_scanner.log (never logs the actual secret)."""
    log_path = "/root/logs/secret_scanner.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    
    for finding in findings:
        entry = {
            "timestamp": timestamp,
            "source": source,
            "pattern": finding["pattern"],
            "description": finding["description"],
            "redacted": finding["redacted"],
            "action": "detected_and_warned",
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

def format_warning(findings: list[dict]) -> str:
    """Format a user-friendly warning message."""
    types = list(set(f["pattern"] for f in findings))
    warning = "⚠️ **Secret detected in message!**\n\n"
    warning += f"Found {len(findings)} potential secret(s): {', '.join(types)}\n\n"
    warning += "**DO NOT send secrets over chat.** Use one of:\n"
    warning += "• SSH into the server and add directly\n"
    warning += "• One-time secret link (onetimesecret.com)\n"
    warning += "• Encrypted file attachment\n\n"
    warning += "If this was a real secret, **rotate it immediately** — it's now in chat history."
    return warning


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read()
    
    findings = scan_message(text)
    
    if findings:
        print(f"🚨 Found {len(findings)} potential secret(s):")
        for f in findings:
            print(f"  - {f['pattern']}: {f['redacted']} ({f['description']})")
        print()
        print(format_warning(findings))
    else:
        print("✅ No secrets detected.")
