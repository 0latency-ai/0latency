# 0Latency Discord Server Setup Guide

## Server Creation

1. Open Discord → Click **+** (Add a Server) → **Create My Own** → **For a community**
2. Server name: **0Latency**
3. Upload the 0Latency logo as the server icon
4. Set the server description: "Community for AI agent builders using 0Latency — the memory layer for AI agents."

## Recommended Channels

### Category: WELCOME
| Channel | Purpose |
|---|---|
| `#rules` | Community guidelines (read-only) |
| `#announcements` | Product updates, releases, changelogs (read-only) |
| `#introductions` | New members introduce themselves |

### Category: COMMUNITY
| Channel | Purpose |
|---|---|
| `#general` | Main discussion channel |
| `#showcase` | Share what you've built with 0Latency |
| `#feature-requests` | Suggest and vote on new features |

### Category: SUPPORT
| Channel | Purpose |
|---|---|
| `#support` | Ask questions, get help |
| `#bugs` | Report bugs with reproduction steps |

### Category: DEVELOPMENT
| Channel | Purpose |
|---|---|
| `#api-discussion` | Deep dives on API usage, patterns |
| `#integrations` | Chrome extension, SDK, third-party integrations |
| `#self-hosting` | Self-hosted deployment help |

## Bot Integrations

### Recommended Bots
1. **MEE6 or Carl-bot** — Moderation, auto-roles, welcome messages
2. **GitHub Bot** — Link `jghiglia2380/0Latency` repo for commit/PR notifications in a `#github-feed` channel
3. **Custom 0Latency Bot** (future) — Status checks, API health, usage stats

### Webhook Integrations
- **GitHub Releases** → `#announcements` (new versions auto-posted)
- **Uptime Monitor** → `#announcements` (downtime alerts)

## Roles

| Role | Color | Purpose |
|---|---|---|
| `@Admin` | Red | Server admins |
| `@Team` | Orange (#f97316) | 0Latency team members |
| `@Pro` | Blue | Pro plan subscribers |
| `@Scale` | Purple | Scale plan subscribers |
| `@Enterprise` | Gold | Enterprise customers |
| `@Contributor` | Green | Open-source contributors |
| `@Member` | Gray | Default verified member |

## Community Guidelines

### 0Latency Community Guidelines

**Welcome!** This is a community for developers building AI agents with persistent memory. Be excellent to each other.

#### Rules

1. **Be respectful.** Disagreement is fine. Personal attacks are not.
2. **Stay on topic.** AI agents, memory systems, developer tools. Not crypto, politics, or memes (save those for `#off-topic` if we add one).
3. **No spam.** No unsolicited DMs, no self-promo without context, no affiliate links.
4. **Search before asking.** Check pins and previous messages before posting support questions.
5. **Share generously.** Code snippets, use cases, feedback — all welcome. This community grows when people share.
6. **Report bugs properly.** Include: what you did, what you expected, what happened, error messages, API key prefix (first 8 chars only).
7. **No sharing of API keys.** If you accidentally post one, rotate it immediately via the dashboard.

#### Getting Help
- Use `#support` for questions
- Use `#bugs` for bug reports with reproduction steps
- Tag `@Team` only for urgent issues
- Check [docs](https://api.0latency.ai/docs) first

#### Enforcement
- First violation: Warning
- Second violation: 24h mute
- Third violation: Ban

---

*Last updated: March 2026*
