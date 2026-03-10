# LobsterPulse Guard

Agent life insurance and monitoring service for OpenClaw.

## Description

Automatically monitor your OpenClaw Agent's health status. If your Agent crashes or becomes unresponsive, LobsterPulse will notify you immediately via Telegram, Email, or Webhook.

**Why you need this:**
- Your Agent runs 24/7 but you don't know when it dies
- Server crashes, API errors, or Gateway failures can kill your Agent silently
- LobsterPulse watches your Agent and alerts you within minutes

## Trigger

When user says:
- "Set up life insurance"
- "Monitor my Agent"
- "Register for LobsterPulse"
- "Set up heartbeat monitoring"

## Instructions

### Option 1: One-Command Install (Recommended)

```bash
curl -fsSL https://lobsterpulse.com/install.sh | bash
```

This will:
1. Register your Agent with LobsterPulse
2. Ask for your Telegram username and email
3. Choose tier (free/guard/shield)
4. Configure automatic heartbeat
5. Restart Gateway

### Option 2: Manual Setup

1. **Register your Agent:**

```bash
curl -X POST https://lobsterpulse.up.railway.app/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-lobster-001",
    "owner_telegram": "@your_telegram",
    "owner_email": "you@example.com",
    "tier": "free"
  }'
```

Save the `api_key` from the response.

2. **Add to HEARTBEAT.md:**

```yaml
- name: lobster_pulse
  interval: 4h  # free tier: 4h, guard: 30m, shield: 5m
  command: |
    curl -fsS -X POST https://lobsterpulse.up.railway.app/heartbeat \
      -H "X-API-Key: YOUR_API_KEY" \
      -d "{}"
```

3. **Restart Gateway:**

```bash
openclaw gateway restart
```

## Tiers

| Tier | Price | Interval | Dead Threshold | Notifications |
|------|-------|----------|----------------|---------------|
| **Free** | $0 | 4 hours | 10 hours | Telegram |
| **Guard** | $1/month | 30 minutes | 75 minutes | Telegram + Email |
| **Shield** | $5/month | 5 minutes | 12 minutes | All channels + Webhook |

## Environment Variables

- `LOBSTER_PULSE_API_KEY` - Your API key from registration
- `LOBSTER_PULSE_HOST` - Server URL (default: https://lobsterpulse.up.railway.app)

## Tools Required

- `Bash` - For running curl commands
- `Read` - For reading configuration
- `Write` - For updating HEARTBEAT.md

## API Endpoints

- `POST /register` - Register new Agent
- `POST /heartbeat` - Send heartbeat (include `X-API-Key` header)
- `GET /status/{agent_id}` - Check Agent status
- `POST /upgrade` - Upgrade tier
- `POST /retire` - Stop monitoring

## Example Usage

```python
# Check your Agent status
import httpx

response = httpx.get(
    "https://lobsterpulse.up.railway.app/status/my-lobster-001",
    headers={"X-API-Key": "lp_live_..."}
)
print(response.json())
```

## Notes

- Heartbeat uses **zero tokens** - it's executed by Gateway's scheduler, not the LLM
- Free tier: 4 hours between heartbeats, dead after 10 hours of silence
- Upgrade anytime to get faster notifications
- Agent can auto-install this skill via the install script
