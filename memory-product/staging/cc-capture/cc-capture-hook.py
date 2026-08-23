#!/usr/bin/env python3
"""cc-capture-hook — Claude Code `Stop` hook. STAGED, NOT INSTALLED.

Per docs/CC-CAPTURE-HOOK-DESIGN.md §3 and §6:
  * does NO network I/O — it appends one spool file and returns,
  * exits 0 unconditionally, never 2 (exit 2 on Stop tells the model it may
    not stop and feeds stderr back to it; capture has no such opinion),
  * spool filename IS the turn key, so a double-fire overwrites rather
    than appends (§4).

Reads the hook payload as JSON on stdin. Resolves the turn from
`transcript_path`: the tail assistant text record, plus the nearest preceding
real human prompt (skipping tool_result records, which masquerade as `user`
— §5).
"""
import sys, os, json, hashlib, time

SPOOL = os.environ.get("CC_CAPTURE_SPOOL", os.path.expanduser("~/.claude/cc-capture/spool"))
LOG   = os.environ.get("CC_CAPTURE_LOG",   os.path.expanduser("~/.claude/cc-capture/hook.log"))
MAX_FILES = int(os.environ.get("CC_CAPTURE_MAX_FILES", "5000"))
MAX_BYTES = int(os.environ.get("CC_CAPTURE_MAX_BYTES", str(500 * 1024 * 1024)))


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg))
    except Exception:
        pass


def is_tool_result(rec):
    """A `user` record whose content is a tool_result block is harness
    plumbing, not a human prompt (§5: 1,372 of 1,441 `user` records)."""
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, list):
        for blk in c:
            if isinstance(blk, dict) and blk.get("type") == "tool_result":
                return True
    return False


def text_of(rec):
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = [b.get("text", "") for b in c
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def resolve_turn(path):
    """Return (assistant_uuid, human_text, assistant_text) or None."""
    recs = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("isSidechain"):        # subagent turns fire SubagentStop (§2)
                continue
            recs.append(r)

    ai = None
    for i in range(len(recs) - 1, -1, -1):
        if recs[i].get("type") == "assistant" and text_of(recs[i]).strip():
            ai = i
            break
    if ai is None:
        return None

    human = ""
    for j in range(ai - 1, -1, -1):
        if recs[j].get("type") == "user" and not is_tool_result(recs[j]):
            human = text_of(recs[j])
            break

    return recs[ai].get("uuid") or "", human, text_of(recs[ai])


def spool_full():
    """Bounded spool (§5). Returns True if we must shed."""
    try:
        names = os.listdir(SPOOL)
    except FileNotFoundError:
        return False
    if len(names) >= MAX_FILES:
        return True
    total = 0
    for n in names:
        try:
            total += os.path.getsize(os.path.join(SPOOL, n))
        except OSError:
            pass
    return total >= MAX_BYTES


def shed_oldest():
    """Drop oldest-first with a logged counter, so a drain outage degrades
    visibly instead of filling the disk (§5)."""
    try:
        names = sorted(os.listdir(SPOOL),
                       key=lambda n: os.path.getmtime(os.path.join(SPOOL, n)))
    except Exception:
        return
    for n in names[:max(1, len(names) // 100)]:
        try:
            os.remove(os.path.join(SPOOL, n))
            log("SHED dropped oldest spool file %s (cap reached)" % n)
        except OSError:
            pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        log("BAD stdin: %s" % e)
        return

    tpath = payload.get("transcript_path")
    sid = payload.get("session_id") or ""
    if not tpath or not os.path.exists(tpath):
        log("no transcript_path (%r) — nothing to spool" % tpath)
        return

    try:
        turn = resolve_turn(tpath)
    except Exception as e:
        log("resolve failed: %s" % e)
        return
    if not turn:
        log("no assistant text record in %s" % tpath)
        return

    auuid, human, assistant = turn
    if not assistant.strip():
        log("empty assistant text — skipping")
        return

    # §4: stable, unique-per-turn, idempotent under retry, computable offline.
    turn_key = hashlib.sha256(("%s\x00%s" % (sid, auuid)).encode("utf-8")).hexdigest()

    rec = {
        "turn_key": turn_key,
        "session_id": sid,
        "assistant_uuid": auuid,
        "cwd": payload.get("cwd"),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "human": human,
        "assistant": assistant,
    }

    try:
        os.makedirs(SPOOL, exist_ok=True)
        if spool_full():
            shed_oldest()
        # filename IS the turn key: a double-fire overwrites, never appends
        dest = os.path.join(SPOOL, turn_key + ".json")
        tmp = dest + ".tmp"
        with open(tmp, "w") as f:
            json.dump(rec, f)
        os.replace(tmp, dest)          # atomic
        log("spooled %s (%d B)" % (turn_key[:12], os.path.getsize(dest)))
    except Exception as e:
        log("spool write failed: %s" % e)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:      # nothing reaches the session
        log("unhandled: %s" % e)
    sys.exit(0)                 # ALWAYS 0 — never 2
