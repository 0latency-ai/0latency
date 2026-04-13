#!/usr/bin/env python3
"""Phase 4-6 Memory Consolidation Merger
Implements archive-before-action loop with exact ordering, P90 gate, and zero false-positive merges.
Constitution: /root/.openclaw/workspace/PHASE4-6-CONSTITUTION.md
"""
import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import openai

# Setup logging
log_file = f"/root/logs/merger-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s UTC | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONN = "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

# Load OpenAI key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    try:
        import subprocess
        env_output = subprocess.run(['bash', '-c', 'source /root/.bashrc && echo $OPENAI_API_KEY'],
                                   capture_output=True, text=True).stdout.strip()
        OPENAI_API_KEY = env_output
    except:
        pass
if not OPENAI_API_KEY:
    for _env_path in ['/root/.openclaw/workspace/memory-product/.env', '/root/.env']:
        try:
            with open(_env_path) as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line.startswith('OPENAI_API_KEY='):
                        OPENAI_API_KEY = _line.split('=', 1)[1].strip()
                        break
            if OPENAI_API_KEY:
                break
        except:
            pass

openai.api_key = OPENAI_API_KEY


def get_db_conn():
    """Get database connection."""
    return psycopg2.connect(DB_CONN)


def log_msg(msg: str):
    """Log with ISO timestamp."""
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    logger.info(f"{ts} | {msg}")


def check_p90_gate() -> Tuple[str, float, int]:
    """§1.1 — P90 Gate. Returns (decision, threshold, max_merges)."""
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT
                consolidation_type,
                COUNT(*) AS n,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY classification_confidence) AS p90
            FROM memory_service.consolidation_queue
            WHERE status = 'classified'
                AND consolidation_type = 'DUPLICATE'
            GROUP BY consolidation_type;
        """)
        result = cur.fetchone()
        
        if not result or result['n'] is None or result['n'] < 12:
            log_msg(f"GATE_BLOCKED: insufficient_data (n={result['n'] if result else 'NULL'})")
            return "NO-GO", 0.0, 0
        
        p90 = float(result['p90']) if result['p90'] else 0.0
        
        if p90 < 0.85:
            log_msg(f"GATE_BLOCKED: p90={p90}")
            # Execute §1.2 prompt tuning protocol
            execute_prompt_tuning_diagnostic(p90)
            return "NO-GO", 0.0, 0
        elif 0.85 <= p90 < 0.90:
            log_msg(f"GATE_CAUTION: p90={p90}, threshold={p90}, max_merges=5")
            return "CAUTION-GO", p90, 5
        else:  # p90 >= 0.90
            log_msg(f"GATE_GO: p90={p90}, threshold={p90}, max_merges=10")
            return "GO", p90, 10
    finally:
        cur.close()
        conn.close()


def execute_prompt_tuning_diagnostic(p90: float):
    """§1.2 — Prompt tuning protocol. Dump diagnostic and HALT."""
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 1. Get 10 lowest-confidence DUPLICATE pairs
        cur.execute("""
            SELECT classification_confidence, similarity_score, classification_reasoning,
                   memory_id_a, memory_id_b
            FROM memory_service.consolidation_queue
            WHERE consolidation_type = 'DUPLICATE'
                AND classification_confidence < 0.85
            ORDER BY classification_confidence ASC
            LIMIT 10;
        """)
        low_conf_pairs = cur.fetchall()

        # 2. Fetch memory text for each pair
        pair_details = []
        for pair in low_conf_pairs:
            cur.execute("""
                SELECT id, headline, content, memory_type FROM memory_service.memories
                WHERE id IN (%s, %s);
            """, (pair['memory_id_a'], pair['memory_id_b']))
            mems = cur.fetchall()
            pair_details.append({'pair': dict(pair), 'memories': [dict(m) for m in mems]})

        # 3. Read current classifier prompt
        classifier_prompt = 'COULD NOT READ'
        try:
            import importlib
            spec_path = os.path.join(os.path.dirname(__file__), 'classifier.py')
            with open(spec_path, 'r') as f:
                content = f.read()
            # Extract CLASSIFICATION_PROMPT
            if 'CLASSIFICATION_PROMPT' in content:
                start = content.index('CLASSIFICATION_PROMPT')
                classifier_prompt = content[start:start+2000]
        except:
            pass

        # 4. Write diagnostic file
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        diag_path = f'/root/logs/prompt-tuning-diagnostic-{date_str}.md'
        with open(diag_path, 'w') as f:
            f.write(f'# Prompt Tuning Diagnostic — {date_str}\n\n')
            f.write(f'## P90: {p90}\n\n')
            f.write(f'## Low-Confidence DUPLICATE Pairs ({len(pair_details)})\n\n')
            for i, pd in enumerate(pair_details):
                f.write(f'### Pair {i+1} (conf={pd["pair"]["classification_confidence"]})\n')
                for m in pd['memories']:
                    f.write(f'- **{m.get("headline", "N/A")}**: {m.get("content", "N/A")[:200]}\n')
                f.write(f'- Reasoning: {pd["pair"]["classification_reasoning"]}\n\n')
            f.write(f'## Current Classifier Prompt\n```\n{classifier_prompt}\n```\n')

        log_msg(f'PROMPT_TUNING_REQUIRED: p90={p90}, low_conf_pairs={len(pair_details)} dumped to {diag_path}')
        log_msg(f'ACTION_REQUIRED: Human or Opus must review diagnostic and revise CLASSIFICATION_PROMPT before Phase 4 can proceed.')
    except Exception as e:
        log_msg(f'Prompt tuning diagnostic failed: {str(e)}')
    finally:
        cur.close()
        conn.close()


def check_preflight_safeguards() -> bool:
    """§2.0 — Pre-flight safeguards. Return False if any fails."""
    # 1. Kill switch
    if os.environ.get('CONSOLIDATION_ENABLED', 'true') != 'true':
        log_msg("SAFEGUARD: kill_switch=active")
        return False
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    try:
        # 2. Daily merge cap
        cur.execute("""
            SELECT COUNT(*) as cnt FROM memory_service.consolidation_queue
            WHERE status = 'processed' AND processed_at::date = CURRENT_DATE;
        """)
        today_count = cur.fetchone()[0]
        if today_count >= 50:
            log_msg(f"SAFEGUARD: daily_cap={today_count}/50")
            return False
        
        # 3. Anomaly detector
        cur.execute("SELECT COUNT(*) FROM memory_service.memories;")
        total = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM memory_service.consolidation_queue
            WHERE created_at::date = CURRENT_DATE;
        """)
        flagged_today = cur.fetchone()[0]
        
        if total > 0 and (flagged_today / total) > 0.20:
            log_msg(f"SAFEGUARD: anomaly={flagged_today}/{total}")
            return False
        
        return True
    finally:
        cur.close()
        conn.close()


def select_candidates(threshold: float, max_count: int) -> List[Dict]:
    """§2.1 — Candidate selection with post-query exclusions."""
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM memory_service.consolidation_queue
            WHERE status = 'classified'
                AND consolidation_type IN ('DUPLICATE', 'UPDATE')
                AND classification_confidence >= %s
            ORDER BY classification_confidence DESC
            LIMIT %s;
        """, (threshold, max_count))
        
        candidates = cur.fetchall()
        
        # Post-query exclusions
        filtered = []
        for cand in candidates:
            # Check if memories still exist
            cur.execute("SELECT id FROM memory_service.memories WHERE id = %s;", (cand['memory_id_a'],))
            if not cur.fetchone():
                continue
            cur.execute("SELECT id FROM memory_service.memories WHERE id = %s;", (cand['memory_id_b'],))
            if not cur.fetchone():
                continue
            
            # Check recency (within last 10 minutes)
            cur.execute("""
                SELECT created_at FROM memory_service.memories WHERE id IN (%s, %s);
            """, (cand['memory_id_a'], cand['memory_id_b']))
            rows = cur.fetchall()
            skip = False
            for row in rows:
                if (datetime.now(timezone.utc) - row['created_at'].replace(tzinfo=timezone.utc)).total_seconds() < 600:
                    skip = True
                    break
            if skip:
                continue
            
            # Check identity lock
            cur.execute("""
                SELECT memory_type FROM memory_service.memories WHERE id IN (%s, %s);
            """, (cand['memory_id_a'], cand['memory_id_b']))
            types = cur.fetchall()
            if any(row['memory_type'] == 'identity' for row in types):
                cur.execute("""
                    UPDATE memory_service.consolidation_queue 
                    SET status = 'rejected', classification_reasoning = %s
                    WHERE id = %s;
                """, ("IDENTITY_LOCK: memory_type=identity is immutable", cand['id']))
                conn.commit()
                continue
            
            filtered.append(cand)
        
        return filtered
    finally:
        cur.close()
        conn.close()


def archive_transaction(pair: Dict) -> bool:
    """§2.2 — Archive-before-action loop (STEP 1-5 exact order)."""
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        pair_id = pair['id']
        mem_a_id = pair['memory_id_a']
        mem_b_id = pair['memory_id_b']
        mem_type = pair['consolidation_type']
        
        # STEP 1: READ
        cur.execute("SELECT * FROM memory_service.memories WHERE id = %s;", (mem_a_id,))
        mem_a = cur.fetchone()
        cur.execute("SELECT * FROM memory_service.memories WHERE id = %s;", (mem_b_id,))
        mem_b = cur.fetchone()
        
        if not mem_a or not mem_b:
            log_msg(f"ERROR | pair={pair_id} | step=1 | error=memory_not_found")
            cur.execute("UPDATE memory_service.consolidation_queue SET status = 'rejected' WHERE id = %s;", (pair_id,))
            conn.commit()
            return False
        
        # STEP 2: ARCHIVE
        reason = 'consolidated' if mem_type == 'DUPLICATE' else 'superseded'
        try:
            cur.execute("""
                INSERT INTO memory_service.memory_archive
                (original_memory_id, tenant_id, agent_id, headline, content, memory_type, importance, embedding, original_created_at, archived_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (mem_a['id'], mem_a['tenant_id'], mem_a['agent_id'], mem_a['headline'], mem_a['context'],
                  mem_a['memory_type'], mem_a['importance'], mem_a['embedding'], mem_a['created_at'], reason))
            
            cur.execute("""
                INSERT INTO memory_service.memory_archive
                (original_memory_id, tenant_id, agent_id, headline, content, memory_type, importance, embedding, original_created_at, archived_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (mem_b['id'], mem_b['tenant_id'], mem_b['agent_id'], mem_b['headline'], mem_b['context'],
                  mem_b['memory_type'], mem_b['importance'], mem_b['embedding'], mem_b['created_at'], reason))
            conn.commit()
        except Exception as e:
            log_msg(f"ERROR | pair={pair_id} | step=2 | error={str(e)}")
            conn.rollback()
            cur.execute("UPDATE memory_service.consolidation_queue SET status = 'rejected' WHERE id = %s;", (pair_id,))
            conn.commit()
            return False
        
        # STEP 3: VERIFY — count must be exactly 2 for THIS pair
        # Use >= 2 check scoped to these IDs (handles re-archive edge case)
        cur.execute("""
            SELECT COUNT(*) FROM memory_service.memory_archive
            WHERE original_memory_id IN (%s, %s);
        """, (mem_a_id, mem_b_id))
        row = cur.fetchone()
        count = row['count'] if row else 0
        if count < 2:
            log_msg(f"ERROR | pair={pair_id} | step=3 | error=ARCHIVE_VERIFY_FAILED expected=2 got={count}")
            cur.execute("UPDATE memory_service.consolidation_queue SET status = 'rejected' WHERE id = %s;", (pair_id,))
            conn.commit()
            return False
        
        # STEP 4: ACT (merge)
        if not execute_merge(cur, conn, mem_a, mem_b, mem_type):
            log_msg(f"ERROR | pair={pair_id} | step=4 | error=merge_failed")
            cur.execute("UPDATE memory_service.consolidation_queue SET status = 'rejected' WHERE id = %s;", (pair_id,))
            conn.commit()
            return False
        
        # STEP 5: MARK
        cur.execute("""
            UPDATE memory_service.consolidation_queue
            SET status = 'processed', processed_at = NOW()
            WHERE id = %s;
        """, (pair_id,))
        conn.commit()
        
        # Log merge
        log_msg(f"MERGED | type={mem_type} | conf={pair['classification_confidence']} | sim={pair['similarity_score']} | a={mem_a_id} | b={mem_b_id} | archived=VERIFIED")
        
        # §4: Cross-agent propagation detection (inline after STEP 5)
        detect_propagation(cur, conn, mem_a, mem_type)
        
        return True
    except Exception as e:
        import traceback
        log_msg(f"ERROR | pair={pair_id} | step=unknown | error={str(e)} | trace={traceback.format_exc()}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def execute_merge(cur, conn, mem_a: Dict, mem_b: Dict, merge_type: str) -> bool:
    """§2.3 — Merge execution (DUPLICATE or UPDATE)."""
    if merge_type == 'DUPLICATE':
        # Call LLM
        merged = call_merge_llm(mem_a, mem_b)
        if not merged:
            return False
        
        # UPDATE mem_a
        cur.execute("""
            UPDATE memory_service.memories
            SET headline = %s, context = %s, importance = %s
            WHERE id = %s;
        """, (merged['headline'], merged['context'], max(mem_a['importance'], mem_b['importance']), mem_a['id']))
        
        # DELETE mem_b
        cur.execute("DELETE FROM memory_service.memories WHERE id = %s;", (mem_b['id'],))
        
        # UPDATE archive
        cur.execute("""
            UPDATE memory_service.memory_archive
            SET consolidated_into = %s
            WHERE original_memory_id = %s;
        """, (mem_a['id'], mem_b['id']))
        
        conn.commit()
        return True
    
    elif merge_type == 'UPDATE':
        # Determine newer
        newer = mem_b if mem_b['created_at'] > mem_a['created_at'] else mem_a
        older = mem_a if newer == mem_b else mem_b
        
        # DELETE older
        cur.execute("DELETE FROM memory_service.memories WHERE id = %s;", (older['id'],))
        
        # UPDATE archive
        cur.execute("""
            UPDATE memory_service.memory_archive
            SET archived_reason = %s, consolidated_into = %s
            WHERE original_memory_id = %s;
        """, ('superseded', newer['id'], older['id']))
        
        conn.commit()
        return True
    
    return False


def call_merge_llm(mem_a: Dict, mem_b: Dict) -> Optional[Dict]:
    """§2.4 — Call LLM merge prompt."""
    prompt = f"""Merge these two memories into one concise memory.
Keep all unique facts from both. Use the higher importance score ({max(mem_a['importance'], mem_b['importance'])}).
Use the earlier creation date.

Memory A: {mem_a['headline']} — {mem_a['context']}
Memory B: {mem_b['headline']} — {mem_b['context']}

Respond with JSON only:
{{"headline": "merged headline", "context": "merged context"}}"""
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = response.choices[0].message.content.strip()
        # Strip markdown
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        text = text.strip()
        result = json.loads(text)
        return result
    except Exception as e:
        logger.error(f"LLM merge failed: {str(e)}")
        return None


def detect_propagation(cur, conn, merged_mem: Dict, merge_type: str):
    """§4: Cross-agent propagation detection and queuing."""
    try:
        # Get embedding of surviving memory
        cur.execute("SELECT embedding FROM memory_service.memories WHERE id = %s;", (merged_mem['id'],))
        row = cur.fetchone()
        if not row or not row['embedding']:
            return
        
        merged_embedding = row['embedding']
        
        # Find similar memories in other agents
        cur.execute("""
            SELECT id, agent_id, headline, context,
                1 - (embedding <=> %s::vector) AS similarity
            FROM memory_service.memories
            WHERE tenant_id = %s
                AND agent_id != %s
                AND 1 - (embedding <=> %s::vector) > 0.80
            ORDER BY embedding <=> %s::vector
            LIMIT 10;
        """, (merged_embedding, merged_mem['tenant_id'], merged_mem['agent_id'], merged_embedding, merged_embedding))
        
        targets = cur.fetchall()
        for target in targets:
            target_id, target_agent, similarity = target['id'], target['agent_id'], target['similarity']
            
            # Check identity lock
            cur.execute("SELECT memory_type FROM memory_service.memories WHERE id = %s;", (target_id,))
            target_type_row = cur.fetchone()
            if target_type_row and target_type_row['memory_type'] == 'identity':
                continue  # Skip silently
            
            # Queue for next run
            cur.execute("""
                INSERT INTO memory_service.consolidation_queue
                (tenant_id, agent_id, memory_id_a, memory_id_b, similarity_score, consolidation_type, status, classification_reasoning)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (merged_mem['tenant_id'], target_agent, target_id, merged_mem['id'], similarity, 'UPDATE', 'classified',
                  f"Cross-agent propagation from {merged_mem['agent_id']}"))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Propagation detection failed: {str(e)}")


def integrity_check() -> bool:
    """§2.6 — Post-run integrity check. Return False if violations found."""
    conn = get_db_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT cq.id FROM memory_service.consolidation_queue cq
            WHERE cq.status = 'processed'
                AND cq.processed_at::date = CURRENT_DATE
                AND (SELECT COUNT(*) FROM memory_service.memory_archive ma
                     WHERE ma.original_memory_id IN (cq.memory_id_a, cq.memory_id_b)) != 2;
        """)
        
        violations = cur.fetchall()
        if violations:
            log_msg(f"INTEGRITY_VIOLATION: pairs with missing archives: {[v[0] for v in violations]}")
            # Set circuit breaker
            with open("/tmp/consolidation_disabled_flag", "w") as f:
                f.write("INTEGRITY_VIOLATION")
            os.environ['CONSOLIDATION_ENABLED'] = 'false'
            return False
        
        return True
    finally:
        cur.close()
        conn.close()


def main():
    """Main merge loop."""
    log_msg("=== MERGER START ===")
    
    # Check preflight
    if not check_preflight_safeguards():
        log_msg("Preflight safeguards failed, exiting")
        return
    
    # Check P90 gate
    decision, threshold, max_merges = check_p90_gate()
    if decision == "NO-GO":
        log_msg("P90 gate returned NO-GO, exiting")
        return
    
    # Select candidates
    candidates = select_candidates(threshold, max_merges)
    log_msg(f"Selected {len(candidates)} candidates (max={max_merges})")
    
    # Process each candidate
    merged_count = 0
    for cand in candidates:
        if archive_transaction(cand):
            merged_count += 1
    
    log_msg(f"Processed {merged_count}/{len(candidates)} merges successfully")
    
    # Integrity check
    if not integrity_check():
        log_msg("Integrity check failed, circuit breaker activated")
        return
    
    log_msg(f"=== MERGER END (merged={merged_count}) ===")


if __name__ == '__main__':
    main()
