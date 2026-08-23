#!/usr/bin/env python3
"""cc-capture-drain — ships spooled turns to /memories/extract. STAGED.

Separate from the hook by design (§3): the hook does a local file write and
nothing else; this process owns all network I/O, retries and backoff. Run it
from a systemd timer / cron, never from the session's critical path.

Posts to /memories/extract — the 202 async path, never the synchronous
/extract (p50 6.1s, p95 22.8s, max 131s per §3).

Idempotence (§4): a local ledger of shipped turn_keys means a re-post of the
same spool file is a no-op. Server-side dedup is a backstop, not the only
line of defense — reinforcement silently inflates recall_count.
"""
import os, sys, json, time, urllib.request, urllib.error, argparse

SPOOL   = os.environ.get("CC_CAPTURE_SPOOL",  os.path.expanduser("~/.claude/cc-capture/spool"))
LEDGER  = os.environ.get("CC_CAPTURE_LEDGER", os.path.expanduser("~/.claude/cc-capture/shipped.ledger"))
LOG     = os.environ.get("CC_CAPTURE_LOG",    os.path.expanduser("~/.claude/cc-capture/drain.log"))
API     = os.environ.get("ZERO_LATENCY_API_URL", "https://api.0latency.ai").rstrip("/")
APIKEY  = os.environ.get("ZERO_LATENCY_API_KEY", "")
AGENT   = os.environ.get("CC_CAPTURE_AGENT_ID", "claude-code")
SURFACE = os.environ.get("CC_CAPTURE_SURFACE", "claude_code_mcp")
STALE_ALERT_SEC = int(os.environ.get("CC_CAPTURE_STALE_SEC", "3600"))


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_ledger():
    try:
        with open(LEDGER) as f:
            return {l.strip() for l in f if l.strip()}
    except FileNotFoundError:
        return set()


def record(turn_key):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(turn_key + "\n")


def post(rec, timeout=30):
    """POST one turn. Returns (ok, status, body)."""
    body = {
        "agent_id": AGENT,
        "content": "Human: %s\n\nAssistant: %s" % (rec.get("human", ""), rec.get("assistant", "")),
        "session_key": rec.get("session_id") or None,
        "session_timestamp": rec.get("captured_at"),
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(API + "/memories/extract", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "cc-capture-drain/1.0")
    req.add_header("X-API-Key", APIKEY)
    # Surface tag, same contract the MCP server uses. NOTE: /memories/extract
    # does not currently consume X-Client — see the PRE-FLIGHT FINDING at the
    # top of docs/CC-CAPTURE-HOOK-DESIGN.md.
    req.add_header("X-Client", SURFACE)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        return False, e.code, e.read().decode()[:400]
    except Exception as e:
        return False, 0, "%s: %s" % (type(e).__name__, e)


def drain_once(keep=False):
    shipped = load_ledger()
    try:
        names = sorted(os.listdir(SPOOL))
    except FileNotFoundError:
        log("spool %s does not exist — nothing to drain" % SPOOL)
        return 0, 0, 0

    files = [n for n in names if n.endswith(".json")]
    ok = skipped = failed = 0
    oldest = None

    for n in files:
        p = os.path.join(SPOOL, n)
        try:
            with open(p) as f:
                rec = json.load(f)
        except Exception as e:
            log("SKIP unreadable %s: %s" % (n, e))
            continue

        tk = rec.get("turn_key") or n[:-5]
        if tk in shipped:
            log("DEDUP %s already shipped — dropping spool file, not re-posting" % tk[:12])
            skipped += 1
            if not keep:
                os.remove(p)
            continue

        backoff, sent = 2, False
        for attempt in range(1, 4):
            good, status, bodytxt = post(rec)
            if good:
                log("SENT %s -> %s %s" % (tk[:12], status, bodytxt[:120]))
                record(tk)
                shipped.add(tk)
                ok += 1
                sent = True
                if not keep:
                    os.remove(p)
                break
            log("FAIL %s attempt %d -> %s %s" % (tk[:12], attempt, status, bodytxt[:160]))
            if status and 400 <= status < 500 and status != 429:
                log("PERMANENT %s (%s) — leaving spooled for review" % (tk[:12], status))
                break
            time.sleep(backoff)
            backoff *= 2
        if not sent:
            failed += 1
            age = time.time() - os.path.getmtime(p)
            oldest = max(oldest or 0, age)

    # drain-lag alerting is part of the deliverable (§6 cost 2)
    try:
        rem = [os.path.join(SPOOL, x) for x in os.listdir(SPOOL) if x.endswith(".json")]
        if rem:
            lag = time.time() - min(os.path.getmtime(x) for x in rem)
            if lag > STALE_ALERT_SEC:
                log("ALERT drain lag %.0fs over threshold %ds; %d file(s) stuck"
                    % (lag, STALE_ALERT_SEC, len(rem)))
    except Exception:
        pass

    log("drain complete: sent=%d dedup_skipped=%d failed=%d" % (ok, skipped, failed))
    return ok, skipped, failed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="do not delete spool files (test mode)")
    a = ap.parse_args()
    if not APIKEY:
        log("ZERO_LATENCY_API_KEY unset — refusing to run")
        sys.exit(1)
    drain_once(keep=a.keep)
