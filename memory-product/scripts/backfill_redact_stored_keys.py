#!/usr/bin/env python3
"""TASK 1b/1c — redact the 42 rows in place and re-embed the affected ones.

Uses production code paths: redact_secrets_for_storage() from
storage_multitenant (same function store_memory() calls), and the same
embedding text (headline + ". " + context) that store_memory() uses.
Key values are never printed.
"""
import os, sys, json, base64, argparse
sys.path.insert(0,"/root/.openclaw/workspace/memory-product/src")
sys.path.insert(0,"/root/.openclaw/workspace/memory-product")
import psycopg2
from psycopg2.extras import RealDictCursor
from storage_multitenant import redact_secrets_for_storage, _embed_text, _embed_text_local

ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true"); A=ap.parse_args()
RX=r'zl_(live|test)_[A-Za-z0-9_-]{16,}'
conn=psycopg2.connect(os.environ["DATABASE_URL"])
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""SELECT id,tenant_id,agent_id,headline,context,full_content,metadata
  FROM memory_service.memories
  WHERE headline ~* %s OR context ~* %s OR full_content ~* %s OR metadata::text ~* %s
  ORDER BY tenant_id, created_at""",(RX,RX,RX,RX))
rows=cur.fetchall()
print("MODE: %s   rows in scope: %d"%("APPLY" if A.apply else "DRY RUN", len(rows)))
print("="*78)

changed=reembedded=0
for i,r in enumerate(rows,1):
    before={k:r[k] for k in ("headline","context","full_content")}
    md=r["metadata"] or {}
    if isinstance(md,str): md=json.loads(md)
    payload={"headline":r["headline"],"context":r["context"],
             "full_content":r["full_content"],"metadata":md}
    out=redact_secrets_for_storage(dict(payload))
    # base64 copy: a secret hides from every regex in there unless decoded (307dde9)
    newmd=out.get("metadata") or {}
    b64=newmd.get("content_raw_b64") or ""
    if b64:
        try:
            raw=base64.b64decode(b64).decode("utf-8","replace")
            clean=redact_secrets_for_storage({"headline":"","context":"","full_content":raw})["full_content"]
            if clean!=raw:
                newmd=dict(newmd); newmd["content_raw_b64"]=base64.b64encode(clean.encode()).decode("ascii")
                out["metadata"]=newmd
        except Exception as e:
            print("   !! b64 undecodable on %s: %s"%(r["id"],type(e).__name__))
    fields=[f for f in ("headline","context","full_content") if out[f]!=before[f]]
    md_changed = json.dumps(newmd,sort_keys=True,default=str)!=json.dumps(md,sort_keys=True,default=str)
    if not fields and not md_changed:
        print("[%2d] %s  NO CHANGE"%(i,r["id"])); continue
    changed+=1
    need_embed = ("headline" in fields) or ("context" in fields)
    print("[%2d] %s  fields=%s%s  reembed=%s"%(i,r["id"],",".join(fields) or "-",
          " +metadata" if md_changed else "", need_embed))
    for f in fields:
        print("      %-12s -> %s"%(f, out[f][:150].replace("\n","\\n")+("..." if len(out[f])>150 else "")))
    if A.apply:
        if need_embed:
            et="%s. %s"%(out["headline"],out["context"])
            emb=_embed_text(et); lemb=_embed_text_local(et); reembedded+=1
            cur.execute("""UPDATE memory_service.memories
                SET headline=%s, context=%s, full_content=%s, metadata=%s::jsonb,
                    embedding=%s::vector, local_embedding=%s::vector, updated_at=now()
                WHERE id=%s::uuid""",
                (out["headline"],out["context"],out["full_content"],json.dumps(newmd,default=str),
                 str(emb),str(lemb),r["id"]))
        else:
            cur.execute("""UPDATE memory_service.memories
                SET headline=%s, context=%s, full_content=%s, metadata=%s::jsonb, updated_at=now()
                WHERE id=%s::uuid""",
                (out["headline"],out["context"],out["full_content"],json.dumps(newmd,default=str),r["id"]))

print("="*78)
print("rows changed: %d   rows re-embedded: %d"%(changed,reembedded))
if A.apply:
    conn.commit(); print("COMMITTED")
else:
    conn.rollback(); print("rolled back (dry run)")
cur.close();conn.close()
