# Verbatim Guarantee

## What we promise

When 0Latency stores a memory atom, the original text is preserved verbatim and is retrievable byte-identical via the verification slice.

## How it's enforced

1. Atom write path: original `full_content` is hashed at write time; hash stored alongside.
2. Verification slice: `GET /memories/{id}/source` returns the verbatim atom and its stored hash.
3. CLI verification: `cli/verify.py` re-hashes the returned content and compares.
4. Contract test: `scripts/contract_test.py` runs nightly at 03:15 UTC, exercises the entire chain end-to-end against production.
5. Hollow-pass guard (T11): contract test exits non-zero if zero atoms were exercised — catches the case where the test "passed" only because there was nothing to test.

## What's covered

- All four atom write paths (CP8 Phase 2 T11 verification): MCP `memory_add`, REST `POST /memories`, the synthesis writer's source-atom store, and the bulk import path.

## What's NOT covered (negative scope)

- **Synthesis rows** — these are derived content, not source atoms. They have their own provenance (`source_memory_ids`) and lineage (`superseded_by`), but they are not byte-identical to any input. The verbatim guarantee applies only to atoms.
- **Embeddings** — these are vector representations, derived from atoms. Not part of the verbatim contract.
- **Redacted atoms** — once redacted (`redaction_state='redacted'`), the original content is removed. The audit trail proves the redaction happened, but the original text is by design unrecoverable.
- **Atoms older than the verification slice's existence** — atoms written before T9 (`GET /memories/{id}/source`) shipped were stored without the hash column populated. They are still byte-identical to what was written, but the contract test cannot verify them. (If this matters, a backfill is straightforward: re-hash existing `full_content` and write to `verbatim_hash`.)

## Public claim

0Latency claims: "every atom you store can be retrieved byte-identical, and we run a contract test against production every night to prove it." This claim is supported by the four-path coverage, the verification slice endpoint, and the nightly contract test with hollow-pass guard. We do NOT claim verbatim preservation for synthesis rows, embeddings, or redacted content.

## Verification

```bash
# As an operator, prove the guarantee right now:
ATOM_ID=$(curl -sf -H "X-API-Key: $KEY" "https://api.0latency.ai/recall?query=test&limit=1" | jq -r '.results[0].id')
curl -sf -H "X-API-Key: $KEY" "https://api.0latency.ai/memories/$ATOM_ID/source" | python3 cli/verify.py
# Output: VERIFIED if hashes match
```

## Cron

```
15 3 * * * /root/.openclaw/workspace/memory-product/scripts/contract_test.sh
```

Last successful run: see `/var/log/0latency/contract_test.log`.
