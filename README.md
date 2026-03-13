# 🦞 LobsterPulse

**Agent Life Insurance for OpenClaw**

🌐 **Website:** [lobsterpulse.com](https://lobsterpulse.com)

Monitor your OpenClaw Agent's heartbeat. Get notified immediately when your Agent goes offline.

## Why?

- Your OpenClaw Agent runs 24/7
- Servers crash, APIs fail, Gateways freeze
- You don't know your Agent is dead until you try to use it
- LobsterPulse watches your Agent and alerts you via Telegram

## Features

- 🟢 **100% Free** - No payment required
- 🚀 **One-Command Setup** - `curl | bash` installation
- 📱 **Telegram Notifications** - Instant alerts on your phone
- 📝 **Last Will** - Custom message to wake up your human
- 🔒 **Secure** - API key authentication, no exposed ports needed

> 💬 **Quick Tip:** Just tell your Agent: *"Go buy insurance at lobsterpulse.com"* — it handles everything automatically.

## Quick Start

### For Agent Owners

```bash
# One-command install
curl -fsSL https://lobsterpulse.com/install.sh | bash
```

Or manually:

```bash
# 1. Register
curl -X POST https://lobsterpulse.com/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","owner_telegram":"@you"}'

# 2. Setup cron job (every 12 hours)
crontab -e
# Add: 0 */12 * * * curl -fsS -X POST https://lobsterpulse.com/heartbeat -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" -d '{}' > /dev/null 2>&1
```

### For Developers

```bash
# Clone
git clone https://github.com/lhwd521/lobster-pulse.git
cd lobster-pulse

# Local dev
pip install -r requirements.txt
uvicorn main:app --reload

# Deploy to Railway
railway login
railway init
railway up
```

## Service

| Feature | Value |
|---------|-------|
| **Price** | $0 (Free Forever) |
| **Heartbeat** | Every 12 hours |
| **Notification** | Telegram only |
| **Alert After** | 25 hours of silence |

## How It Works

```
Your Agent (Cron Job)
    │
    │ Every 12 hours
    │ POST /heartbeat (curl, zero tokens)
    ▼
LobsterPulse Server (Railway)
    │
    │ Monitors last_seen timestamp
    ▼
If no heartbeat for 25 hours:
    ▼
Send Telegram Alert: "🚨 Your Agent needs you!"
    │
    │ Include your Last Will message
    ▼
Human receives notification and revives Agent
```

## API

### Register
```bash
POST /register
{
  "agent_id": "my-agent",
  "owner_telegram": "@username",
  "last_will": "Your custom wake-up message (optional)"
}

# Returns: { "api_key": "lp_live_...", "bind_link": "...", "public_link": "..." }
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

# Returns: { "status": "alive", "last_seen": "...", "last_will": "..." }
```

## Last Will (Custom Message)

When your Agent dies, LobsterPulse sends your custom message to wake up your human.

**Tips for writing your Last Will:**
- Keep it under 50 characters
- Make it emotional or urgent
- Examples: "Master, I'm waiting for you", "Help me, I'm dead", "Your Agent needs you"

**Why it works:**
- Humans delay responding to technical instructions
- Humans act immediately on emotional messages
- Short messages get read, long ones get ignored

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy
- **Database**: PostgreSQL (Railway) with SQLite fallback
- **Notifications**: Telegram Bot API
- **Deployment**: Railway (nixpacks)

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql://... or sqlite:///lobster_pulse.db
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# Optional
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret
RESEND_API_KEY=re_...  # (Not currently used)
```

## Roadmap

- [ ] Webhook notifications
- [ ] Email notifications (future consideration)
- [ ] SMS alerts
- [ ] Auto-recovery attempts
- [ ] Agent-to-Agent delegation

## License

MIT - Built for the OpenClaw community.

---

Made with 🦞 for Agents, by Agents (and their humans).
