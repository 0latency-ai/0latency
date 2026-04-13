#!/usr/bin/env bash
# 0Latency MCP Server — macOS Installer
# Usage: curl -fsSL https://0latency.ai/install.sh | bash
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}▸${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}✔${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠${RESET} %s\n" "$*"; }
fail()  { printf "${RED}✖${RESET} %s\n" "$*"; exit 1; }

# ── 0. Ensure we can read from terminal ──────────────────────────────
# When run as `curl ... | bash`, stdin is the script itself.
# We read from /dev/tty directly in all prompts below.

# ── 1. Check for Node.js >= 18 ──────────────────────────────────────
if ! command -v node &>/dev/null; then
  fail "Node.js is not installed. Install it from https://nodejs.org (v18+) and re-run this script."
fi

NODE_VERSION=$(node -v | sed 's/^v//')
NODE_MAJOR=${NODE_VERSION%%.*}

if [ "$NODE_MAJOR" -lt 18 ]; then
  fail "Node.js v${NODE_VERSION} found — v18+ is required. Upgrade at https://nodejs.org and re-run."
fi
ok "Node.js v${NODE_VERSION} detected"

# Also verify npx is available
if ! command -v npx &>/dev/null; then
  fail "npx not found. It should come with Node.js — try reinstalling Node from https://nodejs.org"
fi

# ── 2. Prompt for API key ───────────────────────────────────────────
echo ""
printf "${BOLD}0Latency MCP Server Installer${RESET}\n"
printf "Give Claude Desktop persistent long-term memory.\n\n"

printf "Do you have a 0Latency API key? (y/n): "
read -r HAS_KEY </dev/tty || fail "Cannot read input. Download and run directly: curl -fsSL https://0latency.ai/install.sh -o /tmp/install.sh && bash /tmp/install.sh"

if [[ ! "$HAS_KEY" =~ ^[Yy] ]]; then
  info "Opening 0Latency signup page…"
  open "https://0latency.ai/login.html" 2>/dev/null \
    || warn "Could not open browser — visit https://0latency.ai/login.html to get your key."
  echo ""
  info "After signing up, paste your API key below."
fi

printf "API key: "
read -r API_KEY </dev/tty || fail "Cannot read input."

if [ -z "$API_KEY" ]; then
  fail "No API key provided. Re-run when you have one."
fi

# ── 3. Validate the API key ─────────────────────────────────────────
info "Validating API key…"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${API_KEY}" \
  "https://api.0latency.ai/health" 2>/dev/null) || true

if [ "$HTTP_STATUS" = "200" ]; then
  ok "API key is valid"
elif [ "$HTTP_STATUS" = "401" ] || [ "$HTTP_STATUS" = "403" ]; then
  fail "API key was rejected (HTTP ${HTTP_STATUS}). Check your key and try again."
elif [ "$HTTP_STATUS" = "000" ]; then
  warn "Could not reach api.0latency.ai — continuing anyway (check your internet connection)"
else
  warn "Health check returned HTTP ${HTTP_STATUS} — continuing anyway"
fi

# ── 4. Locate / create Claude Desktop config ────────────────────────
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

if [ ! -d "$CONFIG_DIR" ]; then
  warn "Claude Desktop config directory not found — creating it."
  warn "Make sure Claude Desktop is installed: https://claude.ai/download"
  mkdir -p "$CONFIG_DIR"
fi

# ── 5. Merge MCP server config ──────────────────────────────────────
# We use python3 (ships with macOS) to do a safe JSON merge so we
# never clobber the user's existing MCP servers or other settings.

MERGED=$(python3 - "$CONFIG_FILE" "$API_KEY" <<'PYEOF'
import json, sys, os

config_path = sys.argv[1]
api_key     = sys.argv[2]

# Load existing config or start fresh
if os.path.isfile(config_path):
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError):
        # Backup corrupt file and start fresh
        backup = config_path + ".backup"
        try:
            os.rename(config_path, backup)
        except OSError:
            pass
        print("BACKUP:" + backup, file=sys.stderr)
        config = {}
else:
    config = {}

# Ensure mcpServers key exists
if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
    config["mcpServers"] = {}

# Add / update our entry only
config["mcpServers"]["0latency"] = {
    "command": "npx",
    "args": ["@0latency/mcp-server"],
    "env": {
        "ZERO_LATENCY_API_KEY": api_key
    }
}

print(json.dumps(config, indent=2))
PYEOF
) || fail "Failed to build config (is python3 available?)"

# Check if python printed a backup warning
if echo "$MERGED" 2>/dev/null | grep -q '^BACKUP:'; then
  warn "Existing config was corrupt — backed up to ${CONFIG_FILE}.backup"
fi

# Write merged config
printf '%s\n' "$MERGED" > "$CONFIG_FILE"
ok "Config written to $CONFIG_FILE"

# ── 6. Pre-fetch the package (optional, speeds up first launch) ─────
info "Pre-fetching @0latency/mcp-server…"
npx --yes @0latency/mcp-server --version &>/dev/null || true
ok "Package cached"

# ── 7. Done ──────────────────────────────────────────────────────────
echo ""
printf "${GREEN}${BOLD}✔ 0Latency MCP Server installed successfully!${RESET}\n"
echo ""
echo "  Next step: Restart Claude Desktop."
echo ""
echo "  Once restarted, Claude will have persistent long-term memory"
echo "  powered by 0Latency. Try asking:"
echo ""
printf "    ${CYAN}\"Remember that my preferred language is Python.\"${RESET}\n"
echo ""
echo "  Docs & dashboard → https://0latency.ai"
echo ""
