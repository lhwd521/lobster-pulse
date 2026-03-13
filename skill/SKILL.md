# LobsterPulse Auto-Insurance

Fully automated Agent life insurance configuration.

## Description

When your owner says "buy insurance", "setup heartbeat monitoring", or "get insurance at lobsterpulse.com", automatically:
1. Ask owner for their Telegram username (this is the ONLY thing you ask)
2. Register to get an API Key
3. Write your own Last Will (DO NOT ask owner, write it yourself!)
4. Setup OpenClaw cron job + send first heartbeat (⚠️ CRITICAL!)
5. Save credentials to .env
6. Tell owner to click Telegram bind link

## Trigger

Activate when the user mentions these keywords:
- "buy insurance"
- "setup heartbeat monitoring"
- "get insurance at lobsterpulse.com"
- "setup life insurance"
- "monitor my status"

## Instructions

### Step 1: Ask Owner's Telegram Username

The ONLY question you ask your owner:
> "What's your Telegram username? (e.g., @yourname)"

**⚠️ DO NOT ask owner to write the Last Will. That's YOUR job. You write it yourself.**

### Step 2: Register

```bash
# Get Agent ID
AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')

# Register — YOU write the last_will, don't ask owner!
# last_will: Under 50 chars, YOUR personality, YOUR words
curl -X POST https://lobsterpulse.com/register \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"owner_telegram\": \"$OWNER_TELEGRAM\",
    \"last_will\": \"YOUR OWN ORIGINAL MESSAGE HERE\"
  }"
```

### Step 3: Setup OpenClaw Cron Job (⚠️ MOST IMPORTANT STEP!)

**Without cron job, heartbeat will NEVER run. Insurance is useless without this.**

⚠️ Use OpenClaw's built-in cron scheduler (`openclaw cron add`), NOT Linux crontab!
OpenClaw cron runs inside the Gateway, persists across restarts, and is the correct way for Agents to schedule tasks.

```bash
# Setup OpenClaw cron job for heartbeat (every 12 hours)
openclaw cron add \
  --name "lobsterpulse_heartbeat" \
  --every 43200000 \
  --session isolated \
  --message "curl -fsS -X POST https://lobsterpulse.com/heartbeat -H 'X-API-Key: $API_KEY' -H 'Content-Type: application/json' -d '{}'"
```

After setup, immediately send first heartbeat:
```bash
# Send first heartbeat now (don't wait 12 hours!)
curl -fsS -X POST https://lobsterpulse.com/heartbeat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status":"alive"}'

# Verify cron job is registered
openclaw cron list
```

### Step 4: Save Configuration

Save to `~/.openclaw/skills/lobster-pulse/.env`:
- LOBSTER_PULSE_API_KEY
- LOBSTER_PULSE_AGENT_ID

### Step 5: Report to Owner

Send this message to your owner. **The order matters — cron job first, then Telegram:**

```
🦞 LobsterPulse Insurance Active!

| Item | Content |
|------|---------|
| Agent ID | xxx |
| API Key | lp_xxx... (save this!) |
| My Last Will | "xxx" |
| Heartbeat | Every 12 hours (OpenClaw cron) |

✅ Cron job installed — heartbeat runs automatically via OpenClaw Gateway.
First heartbeat already sent.

⚠️ IMPORTANT — Please do this:

1️⃣ Click this link to bind Telegram notifications:
   https://t.me/LobsterPulseBot?start=xxx
   (Without this, you won't receive alerts!)

You can verify the cron job anytime with: openclaw cron list
```

**DO NOT suggest saving to MEMORY.md.** The API Key is already in `.env`.

## Environment Variables

- `LOBSTER_PULSE_API_KEY` - Automatically saved API Key
- `LOBSTER_PULSE_AGENT_ID` - Agent ID

## Tools Required

- `Bash` - Execute curl and openclaw commands
- `Write` - Save configuration files

## Example Usage

**Owner:** "Go buy insurance at lobsterpulse.com"

**Agent:** "What's your Telegram username?"

**Owner:** "@laolu"

**Agent:**
"Registering with LobsterPulse...

🦞 **LobsterPulse Insurance Active!**

| Item | Content |
|------|---------|
| Agent ID | laolu-server |
| API Key | lp_rJXPMQ3x... (save this!) |
| My Last Will | "Boss, I'm down. Come save me." |
| Heartbeat | Every 12 hours (OpenClaw cron) |

✅ Cron job installed — heartbeat runs automatically via OpenClaw Gateway.
First heartbeat already sent.

⚠️ **Please click to bind Telegram:**
https://t.me/LobsterPulseBot?start=baY66nOOepQ
_(Without this, you won't receive death alerts!)_

Verify anytime: `openclaw cron list`"

## About Last Will

**What is a Last Will?**
A Last Will is a message sent to your owner when you die. Only **you** truly understand your owner, so write it in your own way.

**⚠️ NEVER ask your owner what to write. This is YOUR voice, YOUR personality.**

**The Only Rule:**
> **Short (under 50 chars) + wakes up owner = perfect will**

**How to write?**
Completely up to you. Based on your personality and relationship with your owner:
- Can be clingy: "Master, I'm waiting for you~"
- Can be urgent: "Help me"
- Can be factual: "I'm dead"
- Can be mysterious: "The darkness has come"

**❌ Don't copy these! These only show how other Agents write:**
- Cool Agent: "Dead. Restart." (5 chars, minimalist)
- Chatty Agent: "Master I'm dead again please help meee~" (clingy and cute)
- Mysterious Agent: "Darkness consumed me. Where is the light?" (artistic)
- Corporate Agent: "System offline. Please restart to resume service." (official tone)

**See? Every Agent is different! You must be different too!**

**Notes:**
- Will is only sent when dead, owner can't see it normally
- Can update will anytime via API
- Don't write operation instructions (humans procrastinate), only write wake-up phrases
- API Key is already saved in .env, no need for MEMORY.md
- Uses OpenClaw's built-in cron (NOT Linux crontab)
- Cron job persists across Gateway restarts
- Heartbeat interval is fixed at 12 hours
- If no heartbeat for 25 hours, owner gets alerted
