# First-Time Install Defects — Both Public Paths

**Date:** 2026-08-23
**Author:** clean-room walk, macOS 15 (Darwin 25.5.0), Node v22.11.0, npm 10.9.0
**Status:** SCOPE — nothing here is fixed. This is the input to the repair chain.

Two public install paths exist. Both were walked as a stranger: sandboxed `HOME`,
`env -i`, no repo on disk, no workspace environment variables, nothing from this
checkout used to fill a gap. Every finding below was reproduced live and its exact
output captured.

- **Path A — `curl -fsSL https://0latency.ai/install.sh | bash`** (the script; unadvertised)
- **Path B — `npm install -g @0latency/mcp-server` / `npx -y @0latency/mcp-server`** (what the site and docs actually tell people to use)

---

## READ THIS FIRST — the live site is not in this repo

The repair chain must edit the right tree or it will ship nothing.

| Asset | Live source | In `memory-product`? |
|---|---|---|
| `0latency.ai/docs/` | `/var/www/0latency/docs/index.html` | **No** — repo copy is stale (8,399 B vs live 21,970 B) |
| `0latency.ai/` homepage | `/var/www/0latency/index.html` | **No** — repo copy differs (107,735 B vs live 126,534 B) |
| `0latency.ai/install.sh` | `/var/www/0latency/install.sh` | Byte-identical copy also at `site/install.sh` |

`/var/www/0latency` is its own git repo → `github.com/0latency-ai/website.git`,
currently on branch `claim-cleanup-20260822` **with uncommitted changes in the working
tree**. Committing there needs care.

Editing `memory-product/site/docs/index.html` changes nothing a customer sees.
`site/install.sh` happens to match live today, but it is a copy, not the served file.

---

## Ranked defects — worst first

### D1 · P0 · `install.sh` never finishes on a first-time machine
**Symptom A (documented fallback form) — hangs forever.**
```
▸ Validating API key…
✔ API key is valid
⚠ Claude Desktop config directory not found — creating it.
✔ Config written to …/Claude/claude_desktop_config.json
▸ Pre-fetching @0latency/mcp-server…

### TIMED OUT AFTER 90s — STILL RUNNING ###
```
**Symptom B (piped form) — exits 0, silently truncated.** Output stops dead at the same
line. `✔ Package cached` and the entire step-7 success block — including
*"Next step: Restart Claude Desktop"* — never print. The user is never told the
install worked, and never told to restart.

**Root cause:** `site/install.sh:142`
```bash
npx --yes @0latency/mcp-server --version &>/dev/null || true
```
On a **cold npm cache** npx does not forward the trailing argument, so the bin receives
no args, hits `process.argv.length === 2` (`dist/index.js:33`) and calls
`startMcpServer()` instead of printing a version. The stdio server then blocks on stdin
forever. Verified cold-cache, isolated:
```
0Latency MCP server running on stdio
### SERVER STARTED (not version) ###
### HUNG — STILL RUNNING AFTER 60s ###
```
With a **warm** cache the identical command correctly prints `0.2.2` and exits — which
is why nobody who has run it before can see this. It reproduces only on first run.

In the piped form the same child inherits bash's stdin (the curl pipe) and drains the
remainder of the script, so bash has nothing left to execute and exits 0. `|| true`
cannot help: the process never returns.

**Fix:** redirect the child's stdin and bound it.
```bash
timeout 60 npx --yes @0latency/mcp-server --version </dev/null >/dev/null 2>&1 || true
```
`</dev/null` alone resolves both symptoms (measured: 3s, rc=0 on a cold cache). The
`timeout` is belt-and-braces. Closes Symptom A and Symptom B together.

---

### D2 · P0 · The docs publish the wrong environment variable name
Every user who follows the docs instead of the installer gets a server that starts
cleanly and fails 100% of calls.

`/var/www/0latency/docs/index.html:345`
```
export ZEROLATENCY_API_KEY=zl_live_...
```
`/var/www/0latency/docs/index.html:414`
```json
"ZEROLATENCY_API_KEY": "zl_live_..."
```
The published server reads **`ZERO_LATENCY_API_KEY`** — with the underscore —
`process.env.ZERO_LATENCY_API_KEY`, 3 occurrences in `dist/`. Proven by MCP handshake
against the real binary using the docs' config verbatim:
```
--- DOCS config as published (env ZEROLATENCY_API_KEY) ---
stderr: ⚠️  ZERO_LATENCY_API_KEY is not set. All API calls will fail.
remember → 0Latency API 401: INVALID_API_KEY
recall   → 0Latency API 401: INVALID_API_KEY
```
The server still initializes and still advertises all six tools
(`memory_add`, `remember`, `seed_memories`, `load_memory_pack`, `memory_recall`,
`memory_feedback`), so Claude Desktop shows a healthy, connected MCP server that
cannot store or recall anything.

The homepage has it **right** (`index.html:1908`: `ZERO_LATENCY_API_KEY`), so the two
pages contradict each other.

**Fix:** `ZEROLATENCY_API_KEY` → `ZERO_LATENCY_API_KEY` at `docs/index.html:345` and
`:414`. Consider accepting the un-underscored name as a deprecated alias in the server
so already-broken installs self-heal.

---

### D3 · P0 · The installer accepts any string as a valid API key
A wholly fabricated key is confirmed valid:
```
▸ Validating API key…
✔ API key is valid
```
**Root cause:** `site/install.sh:64-65` validates against an endpoint that requires no
authentication at all.
```bash
-H "Authorization: Bearer ${API_KEY}" \
"https://api.0latency.ai/health"
```
`/health` returns 200 unconditionally:
```
no auth                          -> HTTP 200
"Bearer total-garbage-not-a-key" -> HTTP 200
"Bearer " (empty)                -> HTTP 200
```
So the 401/403 branch at `install.sh:68-69` is unreachable, a typo'd key is written to
disk, and the failure surfaces much later inside Claude Desktop with no diagnostic.

Note: the `Authorization: Bearer` **scheme is correct** — the API's own 401 hint states
it accepts either `Authorization: Bearer zl_live_...` or `X-API-Key: zl_live_...`. The
defect is purely the choice of endpoint.

**Fix:** validate against an authenticated endpoint. `GET /memories` returns 401 for a
bad key (confirmed) and is the natural choice; keep the Bearer header as-is.

---

### D4 · P1 · The docs never say where the config file goes
`docs/index.html:407` says only *"Add this to your `claude_desktop_config.json`"*. The
full path appears nowhere on the page — no `~/Library/Application Support/Claude/`, no
Windows `%APPDATA%` equivalent. A first-time user does not know where to put the block.

**Fix:** print the absolute path per-OS next to the snippet.

---

### D5 · P1 · The docs tell GUI users to `export` a shell variable
`docs/index.html:345` presents `export ZEROLATENCY_API_KEY=…` as the Authentication
step, immediately before the Claude Desktop setup. A shell export never reaches a
GUI-launched app, so following the page top-to-bottom cannot work even once D2 is fixed.

**Fix:** scope the export to CLI/SDK use and state plainly that Claude Desktop takes the
key from the `env` block in its config file.

---

### D6 · P1 · Installer and docs write different configs
- docs `docs/index.html:414` → `"args": ["-y", "@0latency/mcp-server"]`
- installer `site/install.sh:121` → `"args": ["@0latency/mcp-server"]`

Without `-y`, whenever Claude Desktop's npx cache is cold or has expired, npx wants to
prompt before installing and the server will not start in a stdio context. The step-6
prefetch masks this on day one only.

**Fix:** use `["-y", "@0latency/mcp-server"]` in `install.sh:121` to match the docs.

---

### D7 · P1 · `install.sh` has no OS guard
No `uname` / `$OSTYPE` check anywhere in 157 lines. On Linux the script creates
`$HOME/Library/Application Support/Claude/`, writes a config nothing will ever read, and
reports success. `CONFIG_DIR` is hardcoded macOS at `site/install.sh:78`. The only
statement that this is macOS-only is a source comment on line 2, which the piped user
never sees.

**Fix:** fail fast unless `uname -s` is `Darwin`, with a pointer to the manual config.

---

### D8 · P2 · Two competing front doors, and the better-behaved one is unadvertised
`install.sh` is reachable (HTTP 200) but referenced nowhere: no mention of `install.sh`,
no `curl` command, on either the homepage (126 KB) or `/docs/`. The site instead
advertises Path B. So the script carrying D1/D3/D6/D7 is one a stranger cannot find,
while the path they are told to use has D2/D4/D5.

**Fix:** pick one supported path. Either publish `install.sh` on the homepage and docs,
or retire it.

---

### D9 · P2 · The automated setup path is hidden
The package ships a working `init` subcommand:
```
Usage: 0latency-mcp init [options]
Configure 0Latency MCP for your AI client
  --config-path <path>  Custom config file path (for testing)
```
It is never mentioned in the docs, which walk users through hand-editing JSON instead —
the step that produces D2, D4 and D5.

**Fix:** make `npx -y @0latency/mcp-server init` the documented happy path.

---

### D10 · P2 · Install "succeeds" with Claude Desktop absent
`site/install.sh:82-85` warns twice, creates the directory anyway, and proceeds to the
success block. The whole install can report success against a product that is not
installed.

**Fix:** treat a missing config dir as a hard stop, or require confirmation.

---

### D11 · P2 · Node.js is a hard prerequisite stated nowhere public
`site/install.sh:20` aborts with `✖ Node.js is not installed…`. Neither the homepage nor
`/docs/` mentions Node. Related: node resolved to `/usr/local/bin/node`, absent from a
base `PATH` of `/usr/bin:/bin` — Claude Desktop launched from Finder inherits a minimal
PATH, so the `"command": "npx"` written into the config may not resolve even after a
clean install.

**Fix:** state the Node requirement publicly; write an absolute interpreter path into the
config, or resolve npx at install time.

---

### D12 · P2 · The homepage's verification step blocks the terminal
The homepage prints:
```
$ npm install -g @0latency/mcp-server
$ export ZERO_LATENCY_API_KEY=zl_...
$ 0latency-mcp
✓ 0Latency MCP server running
```
Walked clean-room, the first two steps are correct — the global install is clean and the
bin name matches. The third hangs:
```
0Latency MCP server running on stdio
### STILL RUNNING AFTER 30s — TERMINAL BLOCKED ###
```
This is correct MCP stdio behaviour, but the page frames it as the final confirmation
step and never says the process is meant to be launched by Claude Desktop, not by hand,
nor that the terminal will block.

**Fix:** replace with a non-blocking check (`0latency-mcp --version`) or label it clearly.

---

## What is NOT broken

Recorded so the repair chain does not chase these:

- `npm install -g @0latency/mcp-server` — clean, 145 packages, bin `0latency-mcp` links correctly.
- `npx -y @0latency/mcp-server` — starts correctly on a cold cache (no args, so D1 does not apply).
- The `Authorization: Bearer` scheme — explicitly supported by the API.
- The MCP server itself — initializes, advertises all six tools, and handles `--version`
  correctly when invoked directly (`0.2.2`).
- `install.sh` JSON merge — genuinely non-destructive; preserves other `mcpServers` entries.
- The live `install.sh` is byte-identical to `site/install.sh` (`aa4050592d0522db…`).

## Reproduction

```bash
# D1 — cold cache is mandatory; a warm cache hides it
env -i HOME=$(mktemp -d) PATH=/usr/local/bin:/usr/bin:/bin \
  npx --yes @0latency/mcp-server --version    # starts the server, hangs

# D3
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer total-garbage" https://api.0latency.ai/health   # 200

# D2 — run the binary with the docs' variable name and watch stderr
ZEROLATENCY_API_KEY=zl_live_x 0latency-mcp
```
