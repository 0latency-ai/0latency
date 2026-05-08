# _db_execute + split() Migration Tracking

## Background

The pattern `rows = _db_execute(query); parts = row.split('|||')` is vulnerable to silent column-alignment failures when:
1. Query SELECT list changes (columns added/removed/reordered)
2. Split indexing assumes fixed column positions
3. Mismatch goes undetected until runtime data corruption

**Reference:** Similar bug fixed in recall.py (12.5% data quality regression, 2026-04-26) - commit referenced in operator memories.

**Solution:** Migrate to `_db_execute_rows(query)` which returns tuples for native unpacking, eliminating stringify+split.

## Migration Sites

| File:Line | Function | Columns | Priority | Status |
|-----------|----------|---------|----------|--------|
| src/storage_multitenant.py:558 | `_handle_correction` | 3 (id, headline, agent_id) | HIGH | ✅ P5.7 |
| src/storage_multitenant.py:631 | `check_duplicate_detection` | 1 (id) | MED | ☐ |
| src/storage_multitenant.py:659 | `check_for_obsolete_facts` | 2+ | MED | ☐ |
| src/storage_multitenant.py:715 | `get_related_memories` | 1 (id) | LOW | ☐ |
| src/storage_multitenant.py:843 | `rewrite_memory` | 2+ | MED | ☐ |
| src/extract_turn.py:105 | `extract_turn` | 1 (content) | LOW | ☐ |
| src/historical_import.py:306 | `import_historical_data` | 1 (content) | LOW | ☐ |
| src/session_processor.py:182 | `process_session` | 1 (content) | LOW | ☐ |
| api/resume_helpers.py:31 | `parse_resume_data` | varies | LOW | ☐ |
| api/resume_helpers.py:84 | `format_resume_output` | varies | LOW | ☐ |

**Total:** 10 sites (1 migrated, 9 remaining)

## Priority Rubric

- **HIGH**: Core recall/correction paths, multi-column split (>2), high traffic
- **MED**: Secondary paths, 2 columns, moderate traffic
- **LOW**: Import/export utilities, single column, low traffic

## Migration Pattern

**Before:**
```python
rows = _db_execute(query, params, tenant_id=tenant_id)
for row in rows:
    parts = row.split("|||")
    col1 = parts[0].strip()
    col2 = parts[1].strip() if len(parts) > 1 else ""
```

**After:**
```python
rows = _db_execute_rows(query, params, tenant_id=tenant_id)
for (col1, col2) in rows:
    # Native tuple unpacking, no stringify+split
```

## Next Steps

1. Migrate storage_multitenant.py:631,659,715,843 (4 sites in same file)
2. Add regression tests for each migrated function
3. Migrate extract_turn.py, historical_import.py, session_processor.py (lower priority, single-column)
4. Evaluate api/resume_helpers.py sites (may require different approach if parsing external format)

---

*Tracking document created: CP8 P5.7 T4 (2026-05-08)*
*Work sequenced post-CP8*
