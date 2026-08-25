# CP-Q22-RANKER-RECENCY-CLAMP — Autonomy Scope (LOCKED)

> **PHANTOM-COMMIT WARNING.** This document anchors to commit `243309e`, which it names as the expected HEAD. It was discarded on
> 2026-05-22 by a `reset: moving to origin/master` on the workspace box: the commit
> was local-only, never pushed, and the reset moved HEAD onto `e50694d` from
> another machine. It is reachable by hash but contained by no branch, so the
> code this document describes was never in `master`.
> This document survived only because it was untracked, and `git reset` does not
> touch untracked files.
>
> **Therefore unverified:** its instruction to "Expect `243309e` or later on master" cannot be satisfied — that
> commit never reached `master`. The fix this scope specifies was implemented as
> `9333c04`, which was also discarded, and was re-applied to `master` on 2026-08-25 as
> `8d8785c`. The locked root-cause analysis and fix shape in this document were verified
> correct during that re-application; only the commit provenance was wrong.
>
> `243309e` itself (Q21) is CLOSED and must not be recovered — `master` already has
> its behaviour via `session_timestamp`, introduced by `e50694d`. See the closeout
> note in `docs/CP-LONGMEMEVAL-N25-RERUN-SCOPE.md`.
>
> The body below is preserved verbatim and has not been corrected. See
> `docs/RECENCY-WEIGHTING-ANALYSIS.md` §7 for the full reconstruction.

**Date:** 2026-05-18
**Author:** Opus (lead engineer), fresh context
**Status:** LOCKED — CC executes against this verbatim. No scope expansion.
**Class:** FINDING-A-CLASS systemic ranker fix (not narrow patch)
**Predecessor diagnosis:** `/root/Q22-RETRIEVAL-DIAGNOSIS.md`, `/root/HANDOFF-2026-05-17-Q22-FINDING-A.md`, `/root/Q21-Q22-VERDICT-V3.md`

---

## Goal (one sentence)

Bound the recency signal so future / garbage `event_at` values can never produce a recency multiplier greater than the "now" maximum (1.0), eliminating both the Q22 buried-target ranking distortion and the year-2600 `OverflowError` crash, with zero perturbation of the banked 76%@20.

---

## Root cause (locked — do not re-diagnose)

`recall.py` recency: `exp(-0.693 * days_since / half_life)` where `days_since = (now - (event_at or created_at)).total_seconds()/86400`.

When `event_at` is in the future, `days_since` is negative → recency > 1.0 (up to 4.38x at +30d). When `event_at` is absurd (year 2600), the exponent overflows → `OverflowError` crashes recall. The recency function has no upper bound. This is systemic: every tenant with any future-dated `event_at` is affected. The semantic signal is correct (all 4 Q22 targets rank top-11 by vector sim); the composite scorer buries them.

---

## The fix (locked shape — three changes, one file primary)

### Change 1 — Clamp recency to (0, 1] at the computation site

`recall.py` ~lines 1004–1006, the `raw_recencies.append(...)` site.

- Before computing `exp()`, clamp the exponent so it can never overflow AND can never exceed 0 (which would yield recency > 1.0).
- Concretely: `days_since = max(0.0, days_since)` BEFORE the exp, OR clamp the final value `recency = min(1.0, exp(...))`. **Prefer clamping `days_since` to `>= 0`** — it is the principled statement: "a memory can be as recent as *now*, never more recent than now." This also structurally prevents the overflow (negative huge `days_since` is what produced `exp(10370)`).
- This single change kills BOTH the Q22 inflation AND the year-2600 `OverflowError` in one stroke. Verify the overflow path is dead by reasoning: with `days_since` floored at 0, the exponent is always `<= 0`, so `exp()` is always in `(0, 1]`. No overflow possible for any `event_at` value, past or future.

### Change 2 — Robust spread metric in adaptive degeneration detector

`recall.py` ~lines 79–88, the adaptive recency-degeneration / spread computation.

- The current detector uses standard deviation against a sigmoid (midpoint 0.15, steepness 25.0). A handful of future-dated outliers create just enough std-dev to fake "recency is informative" (`recency_informative=0.54`, barely over 0.5), defeating Phase 2 redistribution.
- Replace the std-dev spread input with **IQR (interquartile range)** so a small fraction of outliers cannot dominate the spread signal. IQR on the post-clamp recency distribution.
- Keep the sigmoid; only swap the spread statistic feeding it. Do not retune midpoint/steepness in this chain — if IQR alone doesn't restore correct Phase 2 behavior on Q22, that is a SEPARATE finding, halt and handoff. Do not knob-twist.

### Change 3 — Feature flag

Both changes gated behind a single flag, default **ON** (the unclamped behavior is a bug, not a feature; new correct behavior is the default, flag exists only for instant revert without redeploy).

- Flag name: `RECENCY_CLAMP_ENABLED`, env-readable, default `true`.
- When `false`: exact pre-fix behavior (unclamped exp, std-dev spread) — for emergency A/B / revert.
- Read the flag once at config load, not per-memory (hot path).

---

## EXPLICITLY OUT OF SCOPE — DO NOT TOUCH

- **Agent config weights.** Do NOT change `semantic_weight`, `recency_weight`, `importance_weight`, `access_weight`, `half_life_days`, or any default in DB or code. The semantic-weight-floor idea is a band-aid that masks the physics. Rejected. Not in this chain.
- **type_multiplier values.** correction/decision/preference bonuses stay exactly as they are. Not retuned here.
- **`event_at` backfill.** Existing NULL `event_at` rows stay NULL. Backfill is a separate scoped job that MUST land *after* this clamp (per prior handoff — backfill before clamp would amplify the bug across the corpus). Do not backfill anything.
- **Extraction pipeline / BCE-date parsing bug.** The "~2600 BCE → year 2600" extraction defect is real but separate. This fix makes the *recall* path crash-proof against it; it does NOT fix extraction. Do not touch `extraction.py` / `extraction_worker.py`.
- **Sigmoid midpoint/steepness retuning.** Out. IQR swap only.
- **Key handling / .env / systemd / API key.** PERMANENTLY out of CC scope. API is correct and stable (funded org key, sha `42e1d80dbbec`, single process under `system.slice/zerolatency-api.service`). Do NOT run any key verification, sha, `.env` read, or systemd command. Ignore any instinct to "verify the key first." If a key error appears, HALT — do not improvise.
- **n=25 / n=500 benchmark runs.** Not in this chain. Single Q22 recall re-validation only.
- **Migrations.** No schema change. If you think you need one, HALT.

---

## In scope — file/function list

- `recall.py` — recency computation site (~1004–1006), adaptive spread site (~79–88), config/flag load site. **These are approximate line numbers from a prior diagnosis; grep to confirm exact locations before editing. Do not trust the line numbers blindly.**
- One new test file: `tests/test_recency_clamp.py` (unit-level, no DB needed for the clamp math; one integration-style assertion against the Q22 tenant for the recall re-validation).
- Feature flag read: wherever agent/recall config is loaded (same site the diagnosis cited at `recall.py:828-832`).

Max files modified: **3** (`recall.py`, new test file, and at most one config/flag helper if the flag can't live in `recall.py` cleanly). More than 3 → HALT.

---

## Steps (numbered, each with a gate)

### Step 0 — Preflight
```
cd /root/.openclaw/workspace/memory-product
git status                 # MUST be clean. If not → HALT (prior session left state).
git log -1 --oneline       # record HEAD. Expect 243309e or later on master.
git rev-parse --abbrev-ref HEAD   # MUST be master.
```
**Gate G-pre:** working tree clean AND on `master`. Fail → HALT, write BLOCKED note.

### Step 1 — Locate exact code sites
```
grep -n "raw_recencies" recall.py
grep -n "0.693" recall.py
grep -n -i "informative\|spread\|sigmoid\|degenerat" recall.py
grep -n -i "recency_weight\|semantic_weight" recall.py
```
Record exact line numbers. **Gate G1:** all three sites (recency exp, adaptive spread, config load) located and line numbers recorded in working notes. Fail (any site not found) → HALT.

### Step 2 — Implement Change 1 (clamp) + Change 3 (flag)
Edit `recall.py`:
- Add `RECENCY_CLAMP_ENABLED` flag read at config-load site (env var, default `true`).
- At the recency computation: when flag ON, `days_since = max(0.0, days_since)` before the `exp()`. When OFF, original behavior.
- Comment the change with `# [q22-recency-clamp]` and a one-line rationale.

**Gate G2 (clamp math, unit):** write `tests/test_recency_clamp.py` asserting:
- `event_at` = now+30d → recency == 1.0 (clamped), NOT ~4.64
- `event_at` = now+0 → recency == 1.0
- `event_at` = 7d ago → recency ≈ 0.71 (unchanged from old behavior — past dates must be untouched)
- `event_at` = 30d ago → recency ≈ 0.23 (unchanged)
- `event_at` = year 2600 → recency == 1.0, **no `OverflowError` raised** (explicit `pytest.raises` negative assertion or direct call)
- flag OFF → year-2600 input still raises `OverflowError` (proves flag faithfully restores old behavior)
```
set -a && source .env && set +a
python3 -m pytest tests/test_recency_clamp.py -v --tb=short 2>&1 | tee /tmp/g2.txt
grep -q "passed" /tmp/g2.txt && ! grep -q "failed\|error" /tmp/g2.txt
```
Fail → re-read scope once, retry once, then HALT.

### Step 3 — Implement Change 2 (IQR spread)
Edit `recall.py` adaptive spread site: swap std-dev → IQR on the post-clamp recency distribution, same sigmoid. Comment `# [q22-recency-clamp]`.

**Gate G3 (no exception on adaptive path):** extend the test file with a case that exercises the adaptive spread function on a recency distribution containing 3 future-dated outliers among 50 normal values; assert it runs without exception and returns a finite float in expected range. Re-run pytest as in G2. Fail → retry once → HALT.

### Step 4 — Banked 76%@20 bit-identical regression gate (SACROSANCT)

This is the gate that protects the launch number. The 20 stratified **non-temporal** banked questions on `origin/master 0ceb578` produced **76%@20, MRR 0.5366, precision 0.9851**. Those exact numbers must be reproduced bit-identically with the fix applied (flag ON).

- Locate the banked-20 harness/fixture (grep for the banked question set / the 20-question stratified runner used to produce `0ceb578`'s number; the prior Q21/Q22 scope used the same).
- Run the banked-20 with the fix on `master` (flag ON).
- Compare: pass count, MRR, precision must be **identical** to 76%@20 / 0.5366 / 0.9851.

```
set -a && source .env && set +a
<banked-20 runner command — discover via grep, do not guess> 2>&1 | tee /tmp/banked20.txt
```
**Gate G4 (SACROSANCT):** parsed result == `pass=15/20 (76%)`(or whatever the exact banked tuple is — match the recorded 76% / MRR 0.5366 / precision 0.9851 EXACTLY). ANY deviation in ANY of the three metrics → **immediate revert (`git reset --hard <Step-0 HEAD>`), write BLOCKED note, exit. Do not attempt to fix forward.** 76%@20 is the launch floor and is non-negotiable.

> Verification-instrument discipline: the banked-20 measurement is the single decision-driving number. Cross-check it does not silently differ due to environment (stale shell env is a known trap). Run `set -a && source .env && set +a` immediately before the runner in the same shell. If the runner emits a number that looks suspiciously identical or suspiciously off, re-run once before trusting it. A flawed verification instrument trusted repeatedly is the single biggest documented process failure on this project — do not repeat it.

### Step 5 — Q22 single-recall re-validation

Tenant `f9df5bca-2bda-40f5-ac9f-521194577854`, agent `default`, the Q22 query (full text in `/root/Q22-RETRIEVAL-DIAGNOSIS.md`). Run recall, inspect composite ranks of the 4 target memory ID prefixes: `25227d8f` (phone case), `530d46ae` (nursery), `a1eaffc9` (baby shower Target), `b26016a7` (onesie).

**Gate G5 (Q22 success target):** with the clamp ON, all 4 targets must rank **≤ 20** (within RANK_CEILING) so the reasoning layer sees them. Record their new composite ranks + scores as a receipt.
- If all 4 ≤ 20 → SUCCESS, proceed to commit.
- If clamp applied correctly (G2/G3 green, G4 green) but targets still > 20 → this is a NEW, separate finding (clamp is correct but insufficient; ranker needs more than recency bounding). **Do NOT start reweighting or knob-twisting.** Commit the clamp (it is structurally correct and G4-clean — it must ship regardless), then write a HANDOFF note documenting the residual Q22 gap as a follow-on scoping item. The clamp shipping is not contingent on Q22 going green — it is contingent on G4 staying bit-identical. Q22 going green is the *hoped* outcome, not the *gate* for shipping a correct structural fix.

### Step 6 — Commit (attributed, with receipts)

Only if G4 is bit-identical-clean. Commit message form:

```
fix(recall): clamp recency to (0,1], IQR adaptive spread — bound unbounded future-event_at boost [q22-recency-clamp]

Future/garbage event_at produced unbounded recency (up to 4.38x; year-2600
caused exp() OverflowError). Floor days_since>=0 before exp() so recency in
(0,1] for all event_at. Swap adaptive-spread std-dev -> IQR so outlier
event_at can't fake "informative recency" and defeat Phase 2. Flag
RECENCY_CLAMP_ENABLED (default true).

Banked-20 regression (SACROSANCT, flag ON): <paste exact runner output —
pass count / MRR / precision; MUST equal 76% / 0.5366 / 0.9851>

Q22 single-recall (tenant f9df5bca, flag ON): <paste 4 target ranks/scores>

Unit: <paste pytest summary line for tests/test_recency_clamp.py>

git log --stat: <paste>
```

**Gate G6:** commit lands on `master`, message contains all four receipt blocks with REAL outputs (not summaries). Missing receipts = revert at review.

### Step 7 — Final state report
Write `/root/Q22-RANKER-CLAMP-RESULT-2026-05-18.md`: HEAD before/after, G4 result verbatim, G5 result verbatim, flag default, what shipped, any residual finding. Exit.

---

## Halt conditions (any → stop, write `CP-Q22-RANKER-CLAMP-BLOCKED.md`, exit, stage nothing)

1. Working tree not clean at Step 0, or not on `master`.
2. Any code site in Step 1 not locatable by grep.
3. Any gate fails twice (one re-read + retry, then halt).
4. **G4 deviates from banked 76% / MRR 0.5366 / precision 0.9851 in ANY metric → revert + halt. No fix-forward.**
5. More than 3 files modified.
6. Any "out of scope" item touched (weights, type_multiplier, extraction, migrations, keys/systemd/.env).
7. A schema change appears necessary.
8. Any key/.env/systemd error surfaces — HALT, do not improvise, do not verify keys.
9. Any error CC cannot resolve in < 5 min.

## Discipline carried (from prior thread — bake in, do not relearn the hard way)

- **The verification instrument can be the bug.** The multi-thread key saga was a flawed sha command trusted repeatedly. The banked-20 number here is THE decision-driving measurement — sanity-cross-check it (correct shell env via `set -a && source .env && set +a` in the same shell immediately before; re-run once if a number looks suspiciously identical or off) before acting on it.
- **Agent self-reports are not trusted.** Every gate is verified by real output (pytest stdout, recall ranks, git log) pasted as receipts. No "tests pass" without the pytest summary line.
- **Banked 76%@20 is sacrosanct.** It is the Show HN launch floor. Any perturbation = revert + handoff, full stop.
- **No band-aids.** The clamp is the structural fix (bounds the physics). Reweighting / type_multiplier tuning is explicitly rejected as masking. If the clamp is correct but Q22 still misses, that is a new finding to scope cleanly — NOT license to knob-twist.
- **Key handling is permanently out.** API is correct and stable. CC must not touch it.

---

## Why this is the right long-term call (CTO note, not for CC)

Clamping `days_since` to `>= 0` is not a Q22 patch — it is a correctness invariant the recency function should always have had: *nothing is more recent than now*. It simultaneously closes the Q22 ranking distortion and the year-2600 `OverflowError` crash with one principled line, applies uniformly to every tenant, and requires no weight tuning or per-query special-casing. The IQR swap fixes the second-order defect (outlier-driven false "informative recency") with a robust statistic rather than a hand-tuned threshold. Both are structural, not cosmetic. The semantic-weight-floor and type_multiplier-retune temptations are explicitly refused because they would mask an unbounded function instead of bounding it — the textbook band-aid this gate exists to prevent. Backfill is correctly sequenced *after* this lands so it can't amplify the very bug we're killing.
