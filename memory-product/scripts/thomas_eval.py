#!/usr/bin/env python3
"""Recall eval for the 0Latency memory product — LLM-judged against a versioned rubric.

For each question in the rubric:
  1. POST /recall on the live API and capture the returned context_block.
  2. Hand the judge the question, the rubric's expected_facts / must_not_assert,
     and the recalled context. The judge answers PASS or FAIL with a reason.
  3. Print per-question detail and an overall pass rate.

The rubric is a versioned JSON file (evals/thomas_eval_v<N>.json) so questions can
be added without touching this runner. Questions flagged answer_changed_over_time
are the load-bearing ones: for those the store still contains the OLD answer, so a
pass requires recall to surface the current state rather than the stale row.

Read-only. Calls /recall and the judge model. Writes nothing to the database.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_RUBRIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                              "evals", "thomas_eval_v1.json")
API_BASE = os.environ.get("ZEROLATENCY_API_BASE", "http://localhost:8420")

JUDGE_PROMPT = """You are grading a MEMORY RETRIEVAL system, not a chatbot.

A question was asked. The system returned the context below from its memory store.
Decide whether that context would let an assistant answer the question CORRECTLY.

QUESTION
{question}

REQUIRED FACTS — the context must support all of these (paraphrase is fine; exact
wording is not required):
{expected}

MUST NOT ASSERT — the context fails if it presents any of these as the current
truth. An outdated statement appearing ALONGSIDE the correct current one is
acceptable only if the current one is also present and is not contradicted:
{forbidden}

RECALLED CONTEXT
---
{context}
---

Grade strictly on whether the required facts are actually present in the recalled
context. Do not use your own knowledge to fill gaps — if a required fact is not in
the context, it is missing, even if you personally know it is true.

Reply with JSON only, no prose, no code fence:
{{"verdict": "PASS" or "FAIL", "missing": ["required facts not found"], "violated": ["must-not-assert items the context asserts"], "reason": "one sentence"}}"""


def http_json(url, payload, headers, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def do_recall(q, api_key, agent_id, limit):
    payload = {
        "query": q["question"],
        "conversation_context": q.get("conversation_context") or q["question"],
        "agent_id": q.get("agent_id") or agent_id,
        "limit": limit,
    }
    try:
        out = http_json(API_BASE + "/recall", payload,
                        {"X-API-Key": api_key, "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        return None, "HTTP %s: %s" % (e.code, e.read().decode("utf-8")[:300])
    except Exception as e:
        return None, "recall failed: %s" % e
    return out, None


def judge(client, model, q, context):
    prompt = JUDGE_PROMPT.format(
        question=q["question"],
        expected="\n".join("- " + f for f in q["expected_facts"]),
        forbidden=("\n".join("- " + f for f in q.get("must_not_assert") or [])
                   or "- (none)"),
        context=context if context.strip() else "(empty — recall returned nothing)",
    )
    msg = client.messages.create(
        model=model, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except Exception:
        pass

    # The judge emits `verdict` first, so a response truncated by max_tokens
    # still carries the decision even when the JSON never closes. Recover it
    # rather than discarding the whole judgement.
    #
    # This previously returned FAIL on any parse error, which silently converted
    # "the judge could not be read" into "the memory system got it wrong" and
    # depressed the reported pass rate with no signal that anything had gone
    # wrong. Q10 was scored FAIL on 2026-08-26 while the judge had written
    # "verdict": "PASS".
    m = re.search(r'"verdict"\s*:\s*"(PASS|FAIL)"', raw)
    if m:
        missing = re.findall(r'"([^"]{8,})"', raw.split('"missing"', 1)[1]) \
            if '"missing"' in raw else []
        return {"verdict": m.group(1), "missing": missing[:6], "violated": [],
                "reason": "recovered from truncated judge output (max_tokens); "
                          "verdict field was intact",
                "truncated": True}

    return {"verdict": "ERROR", "missing": [], "violated": [],
            "reason": "judge output unparseable and no verdict field found: %s"
                      % raw[:180]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", default=DEFAULT_RUBRIC)
    ap.add_argument("--limit", type=int, default=20, help="recall limit per question")
    ap.add_argument("--only", default=None, help="comma-separated question ids")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="emit machine-readable results")
    args = ap.parse_args()

    api_key = os.environ.get("ZEROLATENCY_API_KEY")
    if not api_key:
        print("ERROR: ZEROLATENCY_API_KEY not set", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set (needed for the judge)", file=sys.stderr)
        return 2

    with open(args.rubric) as f:
        rubric = json.load(f)

    questions = rubric["questions"]
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        questions = [q for q in questions if q["id"] in want]

    import anthropic
    client = anthropic.Anthropic()
    model = rubric.get("judge_model", "claude-sonnet-5")
    default_agent = rubric.get("default_agent_id", "user-justin")

    print("=" * 78)
    print("RECALL EVAL — rubric v%s (%s)" % (rubric["version"], os.path.basename(args.rubric)))
    print("api=%s  judge=%s  agent=%s  limit=%d  questions=%d"
          % (API_BASE, model, default_agent, args.limit, len(questions)))
    print("=" * 78)

    results = []
    for q in questions:
        out, err = do_recall(q, api_key, default_agent, args.limit)
        if err:
            verdict = {"verdict": "FAIL", "missing": [], "violated": [],
                       "reason": err}
            used, ctx = 0, ""
        else:
            ctx = out.get("context_block") or ""
            used = out.get("memories_used") or 0
            verdict = judge(client, model, q, ctx)

        passed = verdict.get("verdict") == "PASS"
        results.append({"id": q["id"], "passed": passed,
                        "changed": bool(q.get("answer_changed_over_time")),
                        "memories_used": used, "verdict": verdict})

        tag = "PASS" if passed else (
            "ERROR" if verdict.get("verdict") == "ERROR" else "FAIL")
        flag = "  [answer changed over time]" if q.get("answer_changed_over_time") else ""
        print("\n[%s] %s%s" % (tag, q["id"], flag))
        print("  Q: %s" % q["question"])
        print("  recalled: %d memories, %d chars of context" % (used, len(ctx)))
        print("  judge: %s" % verdict.get("reason", ""))
        if verdict.get("missing"):
            for m in verdict["missing"]:
                print("    - MISSING: %s" % m)
        if verdict.get("violated"):
            for v in verdict["violated"]:
                print("    - ASSERTED STALE: %s" % v)

    total = len(results)
    npass = sum(1 for r in results if r["passed"])
    nerror = sum(1 for r in results if r["verdict"].get("verdict") == "ERROR")
    ntrunc = sum(1 for r in results if r["verdict"].get("truncated"))
    changed = [r for r in results if r["changed"]]
    cpass = sum(1 for r in changed if r["passed"])

    print("\n" + "=" * 78)
    print("PASS RATE: %d/%d (%.0f%%)" % (npass, total, 100.0 * npass / total if total else 0))
    if changed:
        print("  of which answer-changed-over-time: %d/%d (%.0f%%)"
              % (cpass, len(changed), 100.0 * cpass / len(changed)))
    print("  failures: %s" % (", ".join(r["id"] for r in results if not r["passed"]) or "none"))
    if nerror:
        print("  JUDGE ERRORS (not counted as memory failures): %s"
              % ", ".join(r["id"] for r in results
                          if r["verdict"].get("verdict") == "ERROR"))
    if ntrunc:
        print("  recovered from truncated judge output: %s"
              % ", ".join(r["id"] for r in results if r["verdict"].get("truncated")))
    print("=" * 78)

    if args.as_json:
        print(json.dumps({"rubric_version": rubric["version"], "total": total,
                          "passed": npass, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
