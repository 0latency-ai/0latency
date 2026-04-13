#!/bin/bash
# Loop Comprehensive Intelligence Scan
# Orchestrates Python scan + web search augmentation

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace/loop"
cd "$WORKSPACE"

TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="logs/comprehensive-scan-$TIMESTAMP.log"

{
echo "=== Loop Comprehensive Scan - $(date '+%Y-%m-%d %H:%M UTC') ==="

# Run base Python scan (Reddit, HN, YouTube)
echo "Running base scans (Reddit, HN, YouTube)..."
python3 scan_intelligence_v2.py

# Spawn sub-agent for web search augmentation (Twitter, enterprise)
echo "Spawning web search sub-agent for Twitter + enterprise infrastructure..."
cd /root/.openclaw/workspace

openclaw sessions spawn --runtime subagent --mode run --timeout 300 \
  --label "loop-websearch-$TIMESTAMP" \
  --task "You are Loop's web search augmentation agent.

## Mission: Find Twitter + Enterprise Agent Infrastructure Content

**Part 1: Twitter/X Content**
Search for recent posts (last 24-48 hours) about:
- #aiagents + memory
- #MCP + agent context
- Agent deployment discussions
- \"persistent memory\" OR \"agent memory\" on Twitter/X

**Part 2: Enterprise Agent Infrastructure**
Search for companies/platforms building:
- ZeroClick-style agent platforms (agents serving agents)
- Enterprise agent deployment infrastructure
- Retail/ecommerce preparing agent interfaces
- Multi-agent orchestration platforms
- Conversational commerce agents

**Part 3: Where Enterprise Users Congregate**
Find discussions happening on:
- LinkedIn groups (AI/ML engineering, enterprise AI)
- GitHub Discussions (AI agent projects)
- Dev.to / Hashnode (agent development posts)
- Enterprise AI forums/communities

**Output Format:**
Append to /root/.openclaw/workspace/loop/alerts-pending.txt

Add section:
\`\`\`
--- WEB SEARCH AUGMENTATION ---

TWITTER/X HIGHLIGHTS:
- [Key post/discussion]
- URL
- Why relevant

ENTERPRISE INFRASTRUCTURE:
- [Company/platform]
- What they're building
- Why 0Latency fits
- URL

ENTERPRISE COMMUNITIES:
- [LinkedIn group / forum / discussion]
- Topic/focus
- Engagement opportunity
\`\`\`

Use web_search tool. Focus on RECENT content (last 7 days). Quality over quantity."

echo ""
echo "Comprehensive scan complete - $(date '+%H:%M UTC')"
echo "Results: $WORKSPACE/alerts-pending.txt"
} > "$LOG_FILE" 2>&1

# Archive old pending alerts if they exist
if [ -f "$WORKSPACE/alerts-pending.txt" ] && [ -f "$WORKSPACE/alerts-pending.txt.old" ]; then
    mv "$WORKSPACE/alerts-pending.txt.old" "$WORKSPACE/alerts-archive/pending-$(date -d '2 hours ago' +%Y%m%d-%H%M).txt" 2>/dev/null || true
fi

# Backup current alerts before augmentation
cp "$WORKSPACE/alerts-pending.txt" "$WORKSPACE/alerts-pending.txt.old" 2>/dev/null || true

echo "Scan complete. Check $LOG_FILE"
