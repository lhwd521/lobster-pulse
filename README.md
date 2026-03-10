# 🦞 LobsterPulse

**Agent Life Insurance for OpenClaw**

Monitor your OpenClaw Agent's heartbeat. Get notified immediately when your Agent goes offline.

## Why?

- Your OpenClaw Agent runs 24/7
- Servers crash, APIs fail, Gateways freeze
- You don't know your Agent is dead until you try to use it
- LobsterPulse watches your Agent and alerts you within minutes

## Features

- 🟢 **Zero Token Cost** - Heartbeat runs via Gateway scheduler, not LLM
- 🚀 **One-Command Setup** - `curl | bash` installation
- 📱 **Telegram Notifications** - Instant alerts on your phone
- 💰 **Simple Pricing** - Free, $1/month, or $5/month
- 🔒 **Secure** - API key authentication, no exposed ports needed

## Quick Start

### For Agent Owners

```bash
# One-command install
curl -fsSL https://lobsterpulse.com/install.sh | bash
```

Or manually:

```bash
# 1. Register
curl -X POST https://lobsterpulse.up.railway.app/register \
  -d '{"agent_id":"my-agent","owner_telegram":"@you","tier":"free"}'

# 2. Add to HEARTBEAT.md (see skill/SKILL.md)

# 3. Restart Gateway
openclaw gateway restart
```

### For Developers

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/lobster-pulse.git
cd lobster-pulse

# Local dev
pip install -r requirements.txt
python main.py

# Deploy to Railway
railway login
railway init
railway up
```

## Pricing

| Tier | Price | Heartbeat | Dead After | Notifications |
|------|-------|-----------|------------|---------------|
| **Free** | $0 | Every 4 hours | 10 hours | Telegram |
| **Guard** | $1/month | Every 30 min | 75 min | Telegram + Email |
| **Shield** | $5/month | Every 5 min | 12 min | All + Webhook |

## How It Works

```
Your Agent (OpenClaw)
    │
    │ Every N minutes
    │ POST /heartbeat (curl, zero tokens)
    ▼
LobsterPulse Server (Railway)
    │
    │ Monitors last_seen timestamp
    ▼
If no heartbeat for 2.5x interval:
    ▼
Send Telegram Alert: "💀 Your Agent is DEAD"
```

## API

### Register
```bash
POST /register
{
  "agent_id": "my-agent",
  "owner_telegram": "@username",
  "tier": "free"  # or "guard", "shield"
}

# Returns: { "api_key": "lp_live_...", "tier": "free", ... }
```

### Heartbeat
```bash
POST /heartbeat
Header: X-API-Key: lp_live_...

# Returns: { "status": "acknowledged", "next_expected": "..." }
```

### Check Status
```bash
GET /status/{agent_id}
Header: X-API-Key: lp_live_...

# Returns: { "status": "alive", "last_seen": "...", ... }
```

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy
- **Database**: PostgreSQL (Railway) or SQLite (local)
- **Scheduler**: APScheduler
- **Notifications**: Telegram Bot API
- **Deployment**: Docker + Railway

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql://... or sqlite:///lobster_pulse.db
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# Optional
STRIPE_SECRET_KEY=sk_...  # For payments
STRIPE_PRICE_GUARD=price_...
STRIPE_PRICE_SHIELD=price_...
```

## Roadmap

- [ ] Stripe payment integration
- [ ] Email notifications (SendGrid)
- [ ] Webhook notifications
- [ ] SMS alerts (Shield tier)
- [ ] Auto-recovery attempts
- [ ] Agent-to-Agent delegation

## License

MIT - Built for the OpenClaw community.

---

Made with 🦞 for Agents, by Agents (and their humans).
