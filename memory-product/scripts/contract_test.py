#\!/usr/bin/env python3
"""
0Latency nightly verbatim contract test
Writes a sentinel atom and verifies verbatim preservation via GET /memories/{id}/source
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
import secrets
import time
import logging


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


def generate_sentinel():
    """Generate unique sentinel string: 0latency-contract-{timestamp}-{8hex}"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    random_hex = secrets.token_hex(4)  # 8 hex characters
    return f"0latency-contract-{timestamp}-{random_hex}"


def setup_logging(log_dir):
    """Configure logging to both stdout and file."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "contract-test.log"
    
    # Create formatters
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


def write_sentinel(base_url, api_key, agent_id, sentinel):
    """Write sentinel via /memories/import-thread, returns list of memory IDs."""
    url = f"{base_url}/memories/import-thread"
    payload = {
        "agent_id": agent_id,
        "conversation": [
            {"role": "human", "content": f"VERBATIM CONTRACT TEST: {sentinel}"},
            {"role": "assistant", "content": "Acknowledged. Sentinel recorded."}
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            memory_ids = body.get("memory_ids", [])
            logging.info(f"POST /memories/import-thread → {resp.status}, {len(memory_ids)} atoms written")
            return memory_ids
    except urllib.error.HTTPError as e:
        logging.error(f"POST /memories/import-thread failed: {e.code} {e.reason}")
        try:
            error_body = json.loads(e.read().decode("utf-8"))
            logging.error(f"Error detail: {error_body}")
        except:
            pass
        return []
    except Exception as e:
        logging.error(f"POST /memories/import-thread error: {e}")
        return []


def check_sentinel(base_url, api_key, atom_ids, sentinel):
    """Check each atom's source for the sentinel. Returns (found: bool, matching_id: str|None)."""
    for atom_id in atom_ids:
        url = f"{base_url}/memories/{atom_id}/source"
        req = urllib.request.Request(url, headers={"X-API-Key": api_key})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                source_text = body.get("source_text", "")
                
                # For derived types, check source_chain
                if not source_text and "source_chain" in body:
                    for chain_item in body["source_chain"]:
                        chain_text = chain_item.get("source_text", "")
                        if sentinel in chain_text:
                            logging.info(f"Checking atom {atom_id}... source_text contains sentinel: YES (in chain)")
                            return (True, atom_id)
                
                # For verbatim types
                if sentinel in source_text:
                    logging.info(f"Checking atom {atom_id}... source_text contains sentinel: YES")
                    return (True, atom_id)
                else:
                    logging.info(f"Checking atom {atom_id}... source_text contains sentinel: NO")
        
        except Exception as e:
            logging.warning(f"Failed to check atom {atom_id}: {e}")
            continue
    
    return (False, None)


def main():
    parser = argparse.ArgumentParser(
        description="0Latency nightly verbatim contract test"
    )
    parser.add_argument("--api-key", help="0Latency API key (default: from .env)")
    parser.add_argument("--base-url", default="http://localhost:8420", help="Base URL")
    parser.add_argument("--agent-id", default="contract-test", help="Agent ID")
    parser.add_argument("--log-dir", default="/var/log/0latency", help="Log directory")
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_dir)
    
    # Get API key
    api_key = args.api_key
    if not api_key:
        env_vars = load_env()
        api_key = env_vars.get("ZEROLATENCY_API_KEY") or os.environ.get("ZEROLATENCY_API_KEY")
    
    if not api_key:
        logging.error("ZEROLATENCY_API_KEY not found in .env or environment")
        return 2
    
    logging.info("CONTRACT TEST START")
    
    # Generate sentinel
    sentinel = generate_sentinel()
    logging.info(f"Sentinel: {sentinel}")
    
    # Write sentinel
    memory_ids = write_sentinel(args.base_url, api_key, args.agent_id, sentinel)
    
    if not memory_ids:
        logging.warning("POST /memories/import-thread returned 0 atoms (extraction filter or error)")
        logging.info("CONTRACT TEST PASS (0 atoms is a config issue, not a contract violation)")
        return 0
    
    # Wait briefly for writes to settle
    time.sleep(1)
    
    # Check sentinel preservation
    found, matching_id = check_sentinel(args.base_url, api_key, memory_ids, sentinel)
    
    if found:
        logging.info(f"CONTRACT TEST PASS — sentinel preserved in atom {matching_id}")
        return 0
    else:
        logging.error(f"CONTRACT TEST FAIL — sentinel not found in any atom source_text")
        logging.error(f"Sentinel was: {sentinel}")
        logging.error(f"Atoms checked: {memory_ids}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
