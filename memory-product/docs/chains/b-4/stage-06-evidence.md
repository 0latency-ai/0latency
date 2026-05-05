# Stage 06 Evidence - Update memory_recall MCP tool description

**Commit SHA:** f4f55b5 (MCP)

**Outcome:** SHIPPED

## Files Touched
- /root/0latency-mcp-unified/src/server-stdio.ts - Updated memory_recall tool description

## Changes
Updated memory_recall tool description to document:
1. Hierarchical expansion via expand parameter (evidence, cluster options)
2. Synthesis memory promotion behavior (1.15x rank boost)
3. Role-based filtering of results

## Previous Description
```
"Recall relevant memories given a conversation context. Returns a formatted context block ready to inject into a prompt."
```

## New Description
```
"Recall relevant memories given a conversation context. Returns a formatted context block ready to inject into a prompt. Supports hierarchical expansion via expand parameter (evidence, cluster). Synthesis memories are promoted 1.15x above constituent atoms. Results are role-filtered based on caller permissions."
```

## Verification Commands

### 1. TypeScript build
```bash
cd /root/0latency-mcp-unified
npm run build
```

### 2. Verify description
```bash
grep -A2 "memory_recall" src/server-stdio.ts
```

## Verification Output

```
> @0latency/mcp-server@0.2.1 build
> tsc

(successful build)
```

## Notes
- Description now documents all Phase 4 features
- LLM callers will see updated documentation when making tool selection decisions
- No behavioral changes, documentation-only update
