# Config Changes — 2026-03-24

Backup saved to `/root/.openclaw/openclaw.json.bak2`

## 1. Telegram queue mode → `steer`
- `messages.queue.mode`: `collect` → `steer`
- `messages.queue.byChannel.telegram`: `collect` → `steer`
- Kept: debounceMs: 3000, cap: 5, drop: summarize

## 2. Default model → Sonnet (with Opus fallback)
Added to `agents.defaults`:
- `models` catalog with both `anthropic/claude-sonnet-4-5` (alias: sonnet) and `anthropic/claude-opus-4-6` (alias: opus)
- `model.primary`: `anthropic/claude-sonnet-4-5`
- `model.fallbacks`: `["anthropic/claude-opus-4-6"]`
- Opus remains available via `/model opus` or as automatic fallback

## 3. Heartbeat suppression during active conversation
- No built-in OpenClaw config option exists for this
- Modified `/root/scripts/heartbeat.sh` to check `sessions.json` mtime
- If sessions file was modified within last 5 minutes (300s), heartbeat exits early
- Logs the skip reason for debugging

## Status
- Config written, **gateway NOT restarted** (Justin will handle)
- All existing config preserved — only added/modified the specified fields
