# D13 — A Global Install Pins Users to 0.1.4 Forever

**Date:** 2026-08-24
**Author:** clean-room measurement, macOS 26.5.2 (Darwin 25.5.0), Node v22.11.0, npm 10.9.0
**Status:** SCOPE — nothing here is implemented. Input to a later repair chain.
**Found by:** the D1 correction in the 2026-08-23 chain (`d39045f`, website repo).

Every public surface tells users to run `npm install -g @0latency/mcp-server`.
Doing so once, at any point since 2026-03-25, pins that user to whatever version
was current then — and **nothing we publish afterwards moves them**. The `-y` in
the config does not help. The `init` command we just made the recommended path
does not run for them at all.

---

## The defect

A user who ran the documented global install while `latest` was `0.1.4` now has
`@0latency/mcp-server@0.1.4` in their npm global prefix. Their
`claude_desktop_config.json` says:

```json
"command": "npx", "args": ["-y", "@0latency/mcp-server"]
```

`npx` sees the package already present in the global prefix and **runs it without
fetching anything**. They get 0.1.4 on every launch, indefinitely, while `latest`
has been 0.2.2 since 2026-05-10.

0.1.4 is materially worse than 0.2.2:

| | 0.1.4 | 0.2.2 |
|---|---|---|
| `--version` | ignored — no argv handling *at all* (`grep argv dist/index.js` returns nothing) | `process.argv.length === 2` + commander |
| `init` subcommand | does not exist | present and working |
| given any argument | ignores it, starts the stdio server, blocks on stdin | handled correctly |

This is the same shadowing that produced the D1 hang. It is **not** an env-var
problem: 0.1.4 already reads `ZERO_LATENCY_API_KEY`, so the D2 fix is correct for
both versions.

### It breaks the path we just recommended

D9 made `npx -y @0latency/mcp-server init` the documented happy path. For a pinned
user that command does not run `init` — 0.1.4 has no such subcommand and no argv
handling, so it ignores the word `init` and starts the stdio server, which then
blocks. Measured: the walk hung until killed, output
`0Latency MCP server running on stdio`.

---

## Mechanism — measured, not assumed

The trigger is the **npm global prefix**, not `PATH`.

```
global 0.1.4 installed in an isolated prefix, latest = 0.2.2

npx -y @0latency/mcp-server --version
  -> starts the 0.1.4 stdio server
  -> _npx entries in the cache afterwards: 0        (it fetched NOTHING)

same run, global bin removed from PATH, prefix still set
  -> still starts the 0.1.4 server
```

So removing the shim from `PATH` does not help; npx consults the configured npm
prefix directly.

npx *does* still contact the registry — with `npm_config_registry` pointed at a
dead port the command fails `ECONNREFUSED` rather than falling back to the global
copy. It contacts the registry and then reuses the installed package anyway. This
matters for the remedy analysis below: a registry lookup happening is **not** the
same as a version check being honoured.

---

## What actually unpins a user

All measured on a sandbox built to look like an affected user (0.1.4 installed
into an isolated npm prefix), one fresh sandbox per row:

| Command | Result |
|---|---|
| `npx -y @0latency/mcp-server` | **PINNED** — 0.1.4 server starts |
| `npx -y @0latency/mcp-server@latest` | **UNPINNED** to 0.2.2 |
| `npx -y @0latency/mcp-server@0.2.2` | **UNPINNED** to 0.2.2 |
| `npm install -g @0latency/mcp-server@latest` | **UNPINNED** to 0.2.2 |
| `npm uninstall -g @0latency/mcp-server` | **UNPINNED** to 0.2.2 |

Two distinct classes:

1. **Fix the machine** — `npm uninstall -g @0latency/mcp-server`, or
   `npm install -g @0latency/mcp-server@latest`. Permanent, but requires the user
   to run a command we have no way to make them run.
2. **Fix the config** — put a version qualifier in the `args` so npx cannot reuse
   the global at all. Works without the user understanding anything.

---

## Can the docs be written so it cannot happen again?

### Option A — qualify the spec in the published config

```json
"args": ["-y", "@0latency/mcp-server@latest"]
```

Measured to unpin. Costs: npx resolves `latest` against the registry on every cold
start, so client startup gains a network dependency and fails closed when the
registry is unreachable (the `ECONNREFUSED` above). It also means a published bad
version reaches every user immediately, with no pinning to fall back on.

### Option B — pin an exact version in the published config

```json
"args": ["-y", "@0latency/mcp-server@0.2.2"]
```

Also measured to unpin, and deterministic. Costs: every release requires editing
the docs, the installer and `init`, and users who never re-run setup stay on the
pinned version — trading a silent stale pin for an explicit one.

### Option C — stop publishing `npm install -g` as a setup step

This is the actual root. All three live surfaces still print it:

```
homepage      npm install -g @0latency/mcp-server   x1
/docs/        npm install -g @0latency/mcp-server   x1
/quickstart   npm install -g @0latency/mcp-server   x1
```

The global install buys nothing — the config invokes `npx`, not the global bin.
It exists only as a "verification" step, which is also D12. Removing it stops new
pins at the source but does nothing for users already pinned.

### Option D — have the server detect and report it

0.2.2 could compare its own version against `latest` at startup and log to stderr.
Useless here: the pinned user is running 0.1.4, which will never contain the check.
Any self-healing code ships in a version they cannot reach. **Discard.**

None of A–D reaches an already-pinned user by itself. A and B do, but only once
that user's config is rewritten — which means `init`, and `init` is exactly what
they cannot run. The only paths that reach them are a one-line command they run by
hand, or a rewritten config delivered some other way.

---

## Deprecate or unpublish 0.1.4?

Registry state as of 2026-08-24:

```
versions      0.1.0, 0.1.1, 0.1.4, 0.2.0, 0.2.1, 0.2.2
dist-tags     latest -> 0.2.2   (published 2026-05-10)
0.1.4         published 2026-03-25   (deprecated: no)
downloads     24 in the last week (2026-08-17 .. 2026-08-23)
maintainers   jghiglia <jghiglia@gmail.com>   (sole)
dependents    none listed
```

### Deprecate

Verified against a control package that is already deprecated (`istanbul@0.4.5`),
installed globally into a sandbox:

```
at INSTALL time     : npm warn deprecated istanbul@0.4.5: This module is no longer maintained...
at RUN time via npx : no warning at all — it simply runs
```

So deprecation is **install-time metadata only**. It does not alter an installed
copy, does not change resolution, and does not surface when npx reuses a global
install. It would warn *new* people running `npm install -g`, and would not reach
a single already-pinned user.

Low risk, low reach. Worth doing as a signal; not a fix.

### Unpublish

0.1.4 is 5 months old, so the 72-hour self-service window is long closed. The
standing npm policy for older versions requires no dependents, under 300 downloads
a week, and a sole maintainer. On the numbers above the package appears to qualify
(24/wk, sole owner, no dependents) — **this needs confirming with npm, not
assuming from a downloads endpoint.**

Even if permitted, unpublishing does not do what we want:

- It does not remove the copy already on a pinned user's machine. Their npx keeps
  reusing local bytes.
- It hard-breaks anyone who pinned `@0.1.4` deliberately.
- npm forbids republishing that exact version afterwards.

**Recommendation: deprecate, do not unpublish.** Unpublish carries real downside and
buys nothing that deprecation does not, because neither reaches the installed copy.

---

## Suggested shape of the fix (not implemented)

1. Deprecate `<0.2.0` with a message naming the remedy verbatim:
   `npm install -g @0latency/mcp-server@latest`.
2. Remove `npm install -g` from the homepage, `/docs/` and `/quickstart` as a
   setup step. It is not needed and it is the only thing creating pins.
3. Pick A or B for the published config and apply it consistently across
   `docs/index.html`, `quickstart.html`, `install.sh` and what `init` writes —
   four surfaces that must not disagree again.
4. Publish a short "already installed and stuck?" note with the one-line fix,
   and link it from the MCP Setup section — the only route that reaches the
   existing pinned population.
5. Re-walk D9 with a stale global present. The current `init` guidance is
   untrue for that population until step 2 or 3 lands.

---

## What is NOT the problem

- Not the env var. 0.1.4 reads `ZERO_LATENCY_API_KEY`, same as 0.2.2.
- Not `PATH`. Removing the shim from `PATH` changes nothing; it is the npm prefix.
- Not `-y`. Measured separately in the D6 commit: `-y` is not load-bearing here.
- Not a cold cache. A genuinely cold machine fetches 0.2.2 and works correctly.

## Reproduction

```bash
# Build an affected user in an isolated prefix — does not touch your real global install
P=$(mktemp -d); C=$(mktemp -d); H=$(mktemp -d)
env -i HOME=$H PATH=/usr/local/bin:/usr/bin:/bin npm_config_prefix=$P npm_config_cache=$C \
  npm install -g @0latency/mcp-server@0.1.4

# Pinned: starts the stdio server instead of printing 0.2.2
env -i HOME=$H PATH=$P/bin:/usr/local/bin:/usr/bin:/bin npm_config_prefix=$P npm_config_cache=$C \
  npx -y @0latency/mcp-server --version </dev/null

# Unpinned
env -i HOME=$H PATH=$P/bin:/usr/local/bin:/usr/bin:/bin npm_config_prefix=$P npm_config_cache=$C \
  npx -y @0latency/mcp-server@latest --version </dev/null    # -> 0.2.2

rm -rf $P $C $H
```
