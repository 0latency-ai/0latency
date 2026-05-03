#!/usr/bin/env python3
"""
zerolatency verify <memory_id> — Verify verbatim source preservation
Wraps GET /memories/{memory_id}/source in a developer-readable format.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def load_env():
    """Load .env by walking up from cwd to root. Returns dict of key=value pairs."""
    env_vars = {}
    current = Path.cwd()
    
    while True:
        env_path = current / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
            break
        
        parent = current.parent
        if parent == current:  # reached root
            break
        current = parent
    
    return env_vars


def build_url(base_url, memory_id):
    """Construct the GET /memories/{id}/source endpoint URL."""
    return f"{base_url}/memories/{memory_id}/source"


def call_api(url, api_key):
    """Call the API and return (status_code, body_dict). Raises on network errors."""
    req = urllib.request.Request(url, headers={"X-API-Key": api_key})
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return (resp.status, body)
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except (json.JSONDecodeError, AttributeError):
            body = {"detail": e.msg}
        return (e.code, body)


def format_output(response_dict):
    """Format the API response per the CLI contract."""
    memory_id = response_dict.get("memory_id", "unknown")
    memory_type = response_dict.get("memory_type", "unknown")
    source_type = response_dict.get("source_type", "unknown")
    
    lines = []
    lines.append(f"✓ Memory {memory_id} verified")
    lines.append(f"Type:        {memory_type}")
    lines.append(f"Source type: {source_type}")
    
    if source_type == "verbatim":
        depth = response_dict.get("trace", {}).get("depth", 0)
        lines.append(f"Depth:       {depth}")
        lines.append("")
        lines.append("Source text:")
        lines.append("─" * 41)
        lines.append(response_dict.get("source_text", ""))
        lines.append("─" * 41)
    
    elif source_type == "derived":
        chain = response_dict.get("source_chain", [])
        depth = response_dict.get("trace", {}).get("depth", "unknown")
        lines.append(f"Chain depth: {depth}")
        lines.append("")
        lines.append("Source chain:")
        
        for idx, item in enumerate(chain, 1):
            item_id = item.get("memory_id", "unknown")
            item_type = item.get("memory_type", "unknown")
            item_text = item.get("source_text", "")
            lines.append(f"[{idx}] {item_id} ({item_type})")
            lines.append("─" * 41)
            lines.append(item_text)
            lines.append("─" * 41)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Verify verbatim source preservation for a memory"
    )
    parser.add_argument("memory_id", help="UUID of the memory to verify")
    parser.add_argument("--api-key", help="0Latency API key (default: from .env or env)")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ZEROLATENCY_BASE_URL", "http://localhost:8420"),
        help="Base URL for 0Latency API (default: http://localhost:8420)",
    )
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key
    if not api_key:
        env_vars = load_env()
        api_key = env_vars.get("ZEROLATENCY_API_KEY") or os.environ.get("ZEROLATENCY_API_KEY")
    
    if not api_key:
        print("✗ Error: ZEROLATENCY_API_KEY not found in .env or environment", file=sys.stderr)
        sys.exit(4)
    
    # Build URL and call API
    url = build_url(args.base_url, args.memory_id)
    
    try:
        status_code, body = call_api(url, api_key)
    except urllib.error.URLError as e:
        print(f"✗ Network error: {e.reason}", file=sys.stderr)
        sys.exit(4)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(4)
    
    # Handle status codes
    if status_code == 200:
        print(format_output(body))
        sys.exit(0)
    elif status_code == 404:
        print("✗ Memory not found (404)", file=sys.stderr)
        sys.exit(1)
    elif status_code == 401:
        print("✗ Auth error — check ZEROLATENCY_API_KEY (401)", file=sys.stderr)
        sys.exit(2)
    elif status_code in (422, 400):
        detail = body.get("detail", "Invalid UUID format")
        print(f"✗ Invalid UUID format ({status_code})", file=sys.stderr)
        print(f"   {detail}", file=sys.stderr)
        sys.exit(3)
    else:
        detail = body.get("detail", "Unknown error")
        print(f"✗ Error: {detail} ({status_code})", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
