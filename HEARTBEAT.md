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

## Intelligence Agent Alerts
- Check `/root/.openclaw/workspace/loop/alerts-pending.txt` — HIGH priority 0Latency engagement opportunities
- Check `/root/.openclaw/workspace/scout/alerts-pending.txt` — PFL Academy leads/RFPs/opportunities
- Check `/root/.openclaw/workspace/sheila/alerts-pending.txt` — Startup Smartup reconnect opportunities
- If any file has HIGH PRIORITY items: alert Justin via Telegram with summary
- If MEDIUM priority: log to daily memory file
- After processing: archive to alerts-archive/ with timestamp

## Execution Agent Pending Approvals
- Run `/root/scripts/check_pending_approvals.py` to query Lance/Shea/Nellie namespaces
- Read `/tmp/pending_approvals_summary.txt` for review
- For each pending item, decide: approve / reject / modify
- Use approval workflow commands:
  - `approve_draft.sh <agent> <memory_id>` — approves for sending
  - `reject_draft.sh <agent> <memory_id> "<reason>"` — stores rejection reason for learning
  - `modify_draft.sh <agent> <memory_id> "<new_content>"` — stores modified version + approval
- After approval, execution agent will send on next run and update with outcome
- Rejection reasons are stored in agent namespace for self-improvement (agents recall them when drafting similar content)
