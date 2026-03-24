# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

## Email Monitor
- Check `/root/scripts/email_alerts_pending.txt` — if it exists and has content, format a summary and send to Justin via Telegram, then delete the file.
- Run `/root/scripts/email_monitor.py` if alerts file doesn't exist (monitor on heartbeat cycle).

## Email Scan (Every 4 hours during waking hours)
- Scan ALL mailboxes (PFL x2, SS x2, Gmail) for new messages in last 4 hours
- Flag: replies from prospects (Stephanie, Shelly, any CO/KY/TX contacts), RFPs, procurement notices, partnership inquiries
- Flag: anything from state DOEs, school districts, or ed-tech companies
- Log findings to daily memory file
- Alert Justin via Telegram if anything is time-sensitive
- Check SENT items too — know what Justin has been doing so you stay current
