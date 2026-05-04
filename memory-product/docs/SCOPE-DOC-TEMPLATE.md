# CP{N} — {Task Title}

**Task:** {One-sentence summary of what this task does.}
**Mode:** Autonomous | Autonomous with halts | Manual
**Migration tier (if any):** Tier 1 (autonomous) | Tier 2 (halt) | Tier 3 (manual) | None
**Estimated wall-clock:** {X–Y min for CC, if autonomous}

---

## Goal

{Detailed description of what success looks like. 2-3 sentences.}

---

## In scope

{Explicit list of what CC is allowed to modify:}
- File paths
- Function names
- Endpoint paths
- DB tables/columns
- etc.

---

## Out of scope

{Explicit list of what CC must NOT touch:}
- Files that should not be modified
- Tables that should not be altered
- Features that should not be changed
- etc.

---

## Inputs at start

{What state must exist before this task can run:}
- Prior task committed: {CP{N-1} at HEAD}
- \`git status\` clean
- Environment variables set
- Services running
- etc.

---

## Steps

### Step 1 — {Step name}

\`\`\`bash
# Commands to run
\`\`\`

**Gate:** {Clear pass/fail condition}

**HALT** if {specific failure conditions}.

### Step 2 — {Step name}

...

{Continue for all steps}

---

## Halt conditions

{Exhaustive list of triggers that mean "stop and write BLOCKED note":}

1. {Specific condition 1}
2. {Specific condition 2}
3. Migration tier escalation: if implementation reveals the migration is actually a higher tier than scoped, halt.
4. \`.env\` shows in \`git status\` as staged. Halt — secret leak risk.
5. {etc.}

---

## Definition of done

1. {Concrete outcome 1}
2. {Concrete outcome 2}
3. {etc.}
4. Single commit pushed; \`.env\` not committed.
5. No BLOCKED note exists.
