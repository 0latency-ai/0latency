# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

## Email Monitor
- Check `/root/scripts/email_alerts_pending.txt` — if it exists and has content, format a summary and send to Justin via Telegram, then delete the file.
- Run `/root/scripts/email_monitor.py` if alerts file doesn't exist (monitor on heartbeat cycle).
