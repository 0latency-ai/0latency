# Changelog

## [0.2.2] - 2026-05-10

### Added
- **`init` subcommand** for one-command MCP setup
  - Interactive CLI wizard to configure Claude Desktop, Cursor, Windsurf, or Claude Code
  - Auto-detects OS and generates correct config file paths
  - Merges into existing configs (preserves other MCP servers)
  - API key discovery from env var or ~/.0latency/credentials
  - Memory write+recall verification to confirm working setup
  - Target: <60s end-to-end with existing API key
  - Usage: `npx @0latency/mcp-server init`

### Changed
- Refactored codebase: extracted server logic to `server.ts`, added CLI routing in `index.ts`
- Added Commander.js for CLI argument parsing
- Added Inquirer.js for interactive prompts

### Technical
- Dependencies added: `commander`, `inquirer`
- New modules: `config.ts` (config file I/O), `init.ts` (init command), `verify.ts` (API verification)
- Default behavior unchanged: running `npx @0latency/mcp-server` starts MCP server as before

## [0.1.4] - Previous

- (Prior version history not tracked here)
