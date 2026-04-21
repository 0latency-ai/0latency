# Contributing to 0Latency

Thanks for helping make 0Latency better. We value every contribution — and we put our money where our mouth is.

## Contributor Rewards

| Contribution | Reward |
|---|---|
| **Report a confirmed bug** | Lifetime Pro access ($29/mo value) |
| **Submit a PR that gets merged** | Lifetime Scale access ($89/mo value) |
| **Build something with 0Latency and share it publicly** (blog post, tutorial, open source project) | Lifetime Scale access ($89/mo value) |

These are real rewards for real contributions. No hoops, no fine print.

**To claim your reward:** Email [hello@0latency.ai](mailto:hello@0latency.ai) with a link to your contribution (issue, PR, or published project). We'll set up your lifetime access within 24 hours.

---

## Reporting Bugs

Good bug reports are incredibly valuable. To file one:

1. **Search existing issues** first — it may already be reported.
2. **Open a new issue** using the [bug report template](https://github.com/jghiglia2380/0Latency/issues/new?template=bug_report.md).
3. Include:
   - What you expected to happen
   - What actually happened
   - Steps to reproduce
   - Your environment (Python version, OS, SDK version)
   - Any relevant error messages or logs

A confirmed bug = a bug we can reproduce. If your report leads to a fix, that's a lifetime Pro account.

## Submitting Pull Requests

1. **Open an issue first** for significant changes so we can discuss the approach.
2. **Fork the repo** and create your branch from `master`.
3. **Write clear commit messages** — one logical change per commit.
4. **Add tests** for new functionality. We use `pytest` for the API and SDK.
5. **Run the test suite** before submitting:
   ```bash
   cd memory-product/api
   pip install -r requirements.txt
   pytest tests/ -v
   ```
6. **Open a PR** with a clear description of what changed and why.

### Code Style

- **Python:** Follow PEP 8. We use 4-space indentation.
- **Type hints:** Use them for function signatures.
- **Docstrings:** Required for public functions and classes.
- **Line length:** 120 characters max.
- **Imports:** Standard library → third-party → local, separated by blank lines.

### What Makes a Good PR

- Solves a real problem (linked to an issue)
- Focused — one concern per PR
- Includes tests
- Doesn't break existing tests
- Has a clear description

## Development Setup

```bash
git clone https://github.com/jghiglia2380/0Latency.git
cd 0Latency/memory-product
pip install -r api/requirements.txt

# Set required env vars
export DATABASE_URL="your_postgres_url"
export GEMINI_API_KEY="your_key"

# Run the API locally
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest tests/ -v
```

## Project Structure

```
memory-product/
├── api/              # FastAPI application
│   ├── main.py       # App entry point
│   ├── routes/       # API endpoints
│   ├── models/       # Pydantic models
│   ├── services/     # Business logic
│   └── tests/        # Test suite
├── sdk/              # Python SDK (zerolatency package)
├── chrome-extension/ # Browser extension
├── site/             # Landing page
└── mcp-server/       # MCP integration
```

## Questions?

- Open a [GitHub Discussion](https://github.com/jghiglia2380/0Latency/discussions)
- Email [hello@0latency.ai](mailto:hello@0latency.ai)

---

Thanks for contributing. Every bug report, PR, and project built with 0Latency makes the platform better for everyone.
