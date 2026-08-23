#!/usr/bin/env python3
"""TASK 1d — three independent proofs. Key values never printed."""
import os, sys, re, json, hashlib, time
sys.path.insert(0,"/root/.openclaw/workspace/memory-product/src")
import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(os.environ["DATABASE_URL"]); conn.set_session(readonly=True)
cur=conn.cursor(cursor_factory=RealDictCursor)

OLD_RX = r'zl_(live|test)_[A-Za-z0-9]{16,}'          # 307dde9's original
NEW_RX = r'zl_(live|test)_[A-Za-z0-9_-]{16,}'        # widened, case-insensitive below

print("="*74)
print("PROOF 1 — ORIGINAL 307dde9 regex, case-sensitive, tenant-wide")
print("="*74)
for label,tid in [("thomas","44c3080d-c196-407d-a606-4ea9f62ba0fc"),
                  ("Default Tenant","00000000-0000-0000-0000-000000000000"),
                  ("ALL TENANTS",None)]:
    if tid:
        cur.execute("""SELECT count(*) n FROM memory_service.memories WHERE tenant_id=%s::uuid
          AND (headline ~ %s OR context ~ %s OR full_content ~ %s OR metadata::text ~ %s)""",
          (tid,OLD_RX,OLD_RX,OLD_RX,OLD_RX))
    else:
        cur.execute("""SELECT count(*) n FROM memory_service.memories
          WHERE headline ~ %s OR context ~ %s OR full_content ~ %s OR metadata::text ~ %s""",
          (OLD_RX,OLD_RX,OLD_RX,OLD_RX))
    print("  %-16s %d rows"%(label,cur.fetchone()["n"]))

print()
print("="*74)
print("PROOF 2 — WIDENED regex (urlsafe charset, any case), tenant-wide")
print("="*74)
for label,tid in [("thomas","44c3080d-c196-407d-a606-4ea9f62ba0fc"),
                  ("Default Tenant","00000000-0000-0000-0000-000000000000"),
                  ("ALL TENANTS",None)]:
    if tid:
        cur.execute("""SELECT count(*) n FROM memory_service.memories WHERE tenant_id=%s::uuid
          AND (headline ~* %s OR context ~* %s OR full_content ~* %s OR metadata::text ~* %s)""",
          (tid,NEW_RX,NEW_RX,NEW_RX,NEW_RX))
    else:
        cur.execute("""SELECT count(*) n FROM memory_service.memories
          WHERE headline ~* %s OR context ~* %s OR full_content ~* %s OR metadata::text ~* %s""",
          (NEW_RX,NEW_RX,NEW_RX,NEW_RX))
    print("  %-16s %d rows"%(label,cur.fetchone()["n"]))

print()
print("="*74)
print("PROOF 3 — NO REGEX. Hash every token in the store against api_keys.")
print("="*74)
cur.execute("SELECT key_hash,status FROM memory_service.api_keys")
KH={r["key_hash"]:r["status"] for r in cur.fetchall()}
ACTIVE={h for h,s in KH.items() if s in ("active","rotating")}
print("  api_keys rows: %d   (active/rotating: %d)"%(len(KH),len(ACTIVE)))
# tokenise on anything that cannot occur inside a key. No key-shape assumption.
KEEP=set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
TBL={c:(chr(c) if chr(c) in KEEP else " ") for c in range(256)}
TBL=str.maketrans("".join(chr(c) for c in range(256)),
                  "".join(chr(c) if chr(c) in KEEP else " " for c in range(256)))
cur2=conn.cursor(name="scanall")   # server-side cursor, streams
cur2.itersize=2000
cur2.execute("SELECT headline, context, full_content, metadata::text FROM memory_service.memories")
tok=hits_active=hits_any=rows=0
t0=time.time()
for rec in cur2:
    rows+=1
    for field in rec:
        if not field: continue
        for t in field.translate(TBL).split():
            tok+=1
            h=hashlib.sha256(t.encode("utf-8","ignore")).hexdigest()
            if h in KH:
                hits_any+=1
                if h in ACTIVE: hits_active+=1
cur2.close()
print("  rows scanned : %d"%rows)
print("  tokens hashed: %d  (%.1fs)"%(tok,time.time()-t0))
print("  tokens matching ANY issued key hash    : %d"%hits_any)
print("  tokens matching an ACTIVE credential   : %d   <-- MUST BE 0"%hits_active)
print()
print("  RESULT:", "PASS — no live credential anywhere in the store" if hits_active==0
      else "FAIL — %d active-credential token(s) still present"%hits_active)
cur.close();conn.close()
