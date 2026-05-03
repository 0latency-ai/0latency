#!/usr/bin/env python3
"""
0Latency nightly verbatim contract test

Tests the verbatim guarantee via /extract endpoint (creates raw_turn).
Seed-API path is excluded due to known limitation (raw_turn exposure only).

Exit codes:
  0 = PASS (contract upheld)
  1 = FAIL (contract violated - sentinel not preserved)
  2 = ERROR (test infra issue)
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
    """Load .env by walking up from cwd to root."""
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
                        env_vars[key.strip()] = value.strip().strip('"')
            break

        parent = current.parent
        if parent == current:
            break
        current = parent

    return env_vars


def setup_logging(log_dir):
    """Configure logging to stdout and file."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "contract-test.log"

    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger


def http_request(method, url, api_key, payload=None):
    """Make HTTP request with error handling."""
    headers = {"X-API-Key": api_key}
    data = None

    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        logging.error(f"{method} {url} failed: {e.code} {e.reason}")
        try:
            error_body = json.loads(e.read().decode("utf-8"))
            logging.error(f"Error detail: {error_body}")
        except:
            pass
        raise
    except Exception as e:
        logging.error(f"{method} {url} error: {e}")
        raise


def test_extract_path(base_url, api_key, agent_id):
    """Test verbatim contract via /extract (sync extraction with raw_turn creation)."""
    # Generate sentinel
    sentinel = f"VERBATIM-CONTRACT-TEST-{datetime.now(timezone.utc).isoformat()}-{secrets.token_hex(8)}"
    logging.info(f"Testing extract path with sentinel: {sentinel}")

    # POST /extract with conversational wrapper containing sentinel
    payload = {
        "agent_id": agent_id,
        "human_message": f"Please remember this exact phrase: '{sentinel}'",
        "agent_message": f"I have recorded the phrase: {sentinel}"
    }

    response, status = http_request("POST", f"{base_url}/extract", api_key, payload)
    raw_turn_id = response.get("raw_turn_id")

    if not raw_turn_id:
        logging.error(f"POST /extract did not return raw_turn_id: {response}")
        return False

    logging.info(f"POST /extract → {status}, raw_turn_id={raw_turn_id}")

    # Wait for write to settle
    time.sleep(0.5)

    # GET /memories/{raw_turn_id}/source
    source_response, status = http_request("GET", f"{base_url}/memories/{raw_turn_id}/source", api_key)
    source_text = source_response.get("source_text", "")

    logging.info(f"GET /memories/{raw_turn_id}/source → {status}")

    # Assert sentinel is present in source_text (it's embedded in conversation)
    if sentinel in source_text:
        logging.info(f"✓ Extract path: sentinel preserved in raw_turn source_text")
        logging.info(f"  Source length: {len(source_text)} chars")
        return True
    else:
        logging.error(f"✗ Extract path: CONTRACT VIOLATION - sentinel not found")
        logging.error(f"  Sentinel: {repr(sentinel)}")
        logging.error(f"  Source preview: {repr(source_text[:500])}...")
        logging.error(f"  Source length: {len(source_text)} chars")
        return False


def cleanup_all_test_memories(base_url, api_key, agent_id):
    """Delete all memories from the test agent (both raw_turn and extracted atoms)."""
    try:
        # Get all memories for this agent created in last hour
        memories, status = http_request("GET", f"{base_url}/memories?agent_id={agent_id}&limit=100", api_key)

        # Filter to recent ones (last hour)
        cutoff = datetime.now(timezone.utc).timestamp() - 3600
        recent_memories = []
        for memory in memories:
            created_at = memory.get("created_at", "")
            try:
                # Parse ISO timestamp
                mem_time = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
                if mem_time > cutoff:
                    recent_memories.append(memory)
            except:
                # Include if we can't parse timestamp (safer to clean up)
                recent_memories.append(memory)

        deleted_count = 0
        for memory in recent_memories:
            try:
                memory_id = memory.get("id")
                http_request("DELETE", f"{base_url}/memories/{memory_id}", api_key)
                deleted_count += 1
            except Exception as e:
                logging.warning(f"Failed to delete memory {memory_id}: {e}")

        if deleted_count > 0:
            logging.info(f"Cleaned up {deleted_count} test memories for agent {agent_id}")
    except Exception as e:
        logging.warning(f"Failed to cleanup test memories: {e}")


def main():
    parser = argparse.ArgumentParser(description="0Latency nightly verbatim contract test")
    parser.add_argument("--api-key", help="API key (default: from .env)")
    parser.add_argument("--base-url", default="http://localhost:8420", help="Base URL")
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
        logging.error("ZEROLATENCY_API_KEY not found")
        return 2

    logging.info("=== VERBATIM CONTRACT TEST START ===")
    logging.info("NOTE: Seed-API path excluded (known limitation - see VERBATIM-GUARANTEE.md)")

    agent_id = "verbatim-contract-test"

    try:
        # Test extraction path (creates raw_turn)
        extract_pass = test_extract_path(args.base_url, api_key, agent_id)

        # Cleanup ALL test memories (raw_turn + extracted atoms)
        cleanup_all_test_memories(args.base_url, api_key, agent_id)

        # Determine overall result
        if extract_pass:
            logging.info("=== CONTRACT TEST PASS — verbatim guarantee upheld ===")
            return 0
        else:
            logging.error("=== CONTRACT TEST FAIL — verbatim guarantee violated ===")
            return 1

    except Exception as e:
        logging.error(f"=== CONTRACT TEST ERROR: {e} ===")
        import traceback
        logging.error(traceback.format_exc())

        # Attempt cleanup even on error
        try:
            cleanup_all_test_memories(args.base_url, api_key, agent_id)
        except:
            pass

        return 2


if __name__ == "__main__":
    sys.exit(main())
