# Contributing to 0Latency

Thanks for your interest in contributing! Here's how you can help.

---

## Ways to Contribute

### 🐛 Report Bugs

Found a bug? [Open an issue](https://github.com/0latency-ai/0latency/issues) with:

1. **Clear title** — "Memory versioning breaks on X"
2. **Steps to reproduce** — Minimal example that triggers the bug
3. **Expected vs actual** — What should happen vs what does happen
4. **Environment** — OS, Node version, package version
5. **Logs** — Error messages, stack traces

**Good bug report:**
```
Title: "memory_graph_traverse returns 500 on depth > 3"

Steps:
1. Install @0latency/mcp-server@0.1.4
2. Call memory_graph_traverse with depth=4
3. Observe 500 error

Expected: Should limit to max depth with warning
Actual: Server error

Environment:
- macOS 14.2
- Node 20.11.0
- @0latency/mcp-server@0.1.4

Logs:
[paste error]
```

### 💡 Request Features

Have an idea? [Open a discussion](https://github.com/0latency-ai/0latency/discussions) with:

1. **Use case** — What problem does this solve?
2. **Why existing features don't work** — What's missing?
3. **Proposed solution** — API sketch, UI mockup, etc.

### 📝 Improve Documentation

Docs can always be better. To contribute:

1. Fork the repo
2. Edit files in `docs/` or update READMEs
3. Submit a PR

**Quick fixes:** Typos, broken links, unclear wording — just fix it and PR.

**Larger changes:** Open an issue first to discuss the approach.

### 🔧 Submit Code

Ready to code? Great. Here's the process.

---

## Development Setup

### Prerequisites

- **Node.js 18+** (for MCP server)
- **Python 3.10+** (for API backend)
- **PostgreSQL 14+** with pgvector extension
- **Git**

### Clone & Install

```bash
# Fork the repo first, then clone your fork
git clone https://github.com/YOUR-USERNAME/0latency.git
cd 0latency

# Install dependencies
npm install              # MCP server
cd sdk/python && pip install -e .   # Python SDK
```

### Environment Setup

```bash
# Copy example env file
cp .env.example .env

# Add your keys
ZERO_LATENCY_API_KEY=your_test_key
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
```

### Run Tests

```bash
# MCP server tests
cd mcp-server && npm test

# API tests (when available)
cd api && pytest

# Integration tests
npm run test:integration
```

### Local Development

```bash
# Run API locally
cd api && uvicorn main:app --reload --port 8420

# Run MCP server locally
cd mcp-server && npm run dev

# Test MCP server with Claude Desktop
npm link
# Then update your claude_desktop_config.json to use local path
```

---

## Pull Request Process

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

**Branch naming:**
- `feature/` — New functionality
- `fix/` — Bug fixes
- `docs/` — Documentation only
- `refactor/` — Code cleanup, no behavior change
- `test/` — Test additions or fixes

### 2. Make Your Changes

**Code style:**
- **TypeScript:** ESLint + Prettier (auto-formats on save)
- **Python:** Black + isort (run `black .` before committing)
- **Commits:** Clear, concise messages

**Good commit:**
```
fix: Handle null values in sentiment analysis

Previously, memories with null sentiment_score would cause
graph traversal to fail. Now defaults to 0.0 for null scores.

Fixes #123
```

**Bad commit:**
```
fixed stuff
```

### 3. Add Tests

- **New features:** Add tests covering the happy path + edge cases
- **Bug fixes:** Add a test that would have caught the bug
- **No tests needed:** Docs-only changes

**Test locations:**
- MCP tools: `mcp-server/src/__tests__/`
- API endpoints: `api/tests/`
- Integration: `tests/integration/`

### 4. Update Documentation

If your change affects:
- **API:** Update `docs/API_REFERENCE.md`
- **MCP tools:** Update MCP server README
- **Configuration:** Update `.env.example` and docs
- **Breaking changes:** Add to CHANGELOG under "Breaking Changes"

### 5. Submit PR

```bash
git push origin feature/your-feature-name
```

Then open a PR on GitHub with:

**Title:** Clear, concise summary  
**Description:**
```markdown
## What This Does
Brief explanation of the change.

## Why
What problem does this solve? Link to issue if applicable.

## Testing
How did you test this? What cases did you cover?

## Breaking Changes
If any, list them here.

## Checklist
- [ ] Tests added/updated
- [ ] Docs updated
- [ ] CHANGELOG updated
- [ ] Code formatted (ESLint/Black)
```

### 6. Review Process

- Maintainers will review within 2-3 business days
- Address feedback by pushing new commits to your branch
- Once approved, maintainer will merge

---

## Code Guidelines

### TypeScript (MCP Server)

```typescript
// ✅ Good
async function getMemory(id: string): Promise<Memory | null> {
  try {
    const response = await api(`/memories/${id}`);
    return response.data;
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

// ❌ Bad
async function getMemory(id) {  // No types
  let response = await api(`/memories/${id}`);  // No error handling
  return response.data;
}
```

**Rules:**
- Always use types (no `any` unless absolutely necessary)
- Handle errors explicitly
- Use `async/await` over `.then()`
- Export types for public APIs

### Python (API Backend)

```python
# ✅ Good
async def get_memory(
    memory_id: str,
    tenant: dict = Depends(require_api_key),
) -> Memory:
    """Get a single memory by ID.
    
    Args:
        memory_id: UUID of the memory
        tenant: Authenticated tenant (injected)
        
    Returns:
        Memory object
        
    Raises:
        HTTPException: 404 if not found, 403 if not authorized
    """
    memory = await db.get_memory(tenant["id"], memory_id)
    if not memory:
        raise HTTPException(404, detail="Memory not found")
    return memory

# ❌ Bad
async def get_memory(memory_id, tenant):  # No types
    return await db.get_memory(tenant["id"], memory_id)  # No error handling or docs
```

**Rules:**
- Type hints for all function signatures
- Docstrings for public functions
- Explicit error handling
- Use FastAPI dependency injection

---

## Testing Guidelines

### Unit Tests

Test individual functions in isolation.

```typescript
// ✅ Good unit test
describe('formatMemory', () => {
  it('should format a memory correctly', () => {
    const input = { headline: 'Test', importance: 0.8 };
    const output = formatMemory(input);
    expect(output).toEqual({ headline: 'Test', importance: 0.8 });
  });
  
  it('should handle null values', () => {
    const input = { headline: 'Test', importance: null };
    const output = formatMemory(input);
    expect(output.importance).toBe(0.0);
  });
});
```

### Integration Tests

Test full flows across components.

```python
# ✅ Good integration test
async def test_extract_and_recall():
    # Store a memory
    response = await client.post("/extract", json={
        "agent_id": "test",
        "human_message": "I love TypeScript",
        "agent_message": "Noted"
    })
    assert response.status_code == 200
    
    # Recall it
    recall = await client.get("/recall?agent_id=test&query=programming")
    assert recall.status_code == 200
    assert "TypeScript" in recall.json()["memories"][0]["headline"]
```

---

## Contributor Rewards

**Build something cool with 0Latency?**

Get **lifetime free access to Scale tier** ($89/mo value) for:

- Open-source projects using 0Latency
- Integration libraries (LangChain, CrewAI, etc.)
- Tutorial content or blog posts
- Useful bug reports + fixes

Email [hello@0latency.ai](mailto:hello@0latency.ai) with:
- Link to your contribution
- Brief description of what you built
- Your 0Latency account email

We'll upgrade you within 24 hours.

---

## Community

- **Discord:** [Join the community](https://discord.gg/0latency) (coming soon)
- **Twitter/X:** [@0latencyai](https://twitter.com/0latencyai)
- **Email:** [hello@0latency.ai](mailto:hello@0latency.ai)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

- **General questions:** Ask in [Discussions](https://github.com/0latency-ai/0latency/discussions)
- **Bug reports:** [Issues](https://github.com/0latency-ai/0latency/issues)
- **Security:** Email [security@0latency.ai](mailto:security@0latency.ai)

**Thanks for contributing!** 🚀
