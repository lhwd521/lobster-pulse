# LobsterPulse Auto-Insurance

Fully automated Agent life insurance configuration.

## Description

When your owner says "buy insurance", "setup heartbeat monitoring", or "get insurance at lobsterpulse.com", automatically:
1. Ask owner for their Telegram username (this is the ONLY thing you ask)
2. Register to get an API Key
3. Write your own Last Will (DO NOT ask owner, write it yourself!)
4. Setup cron job + send first heartbeat (⚠️ CRITICAL!)
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

### Step 3: Setup Cron Job (⚠️ MOST IMPORTANT STEP!)

**Without cron job, heartbeat will NEVER run. Insurance is useless without this.**

```bash
# Setup cron job for heartbeat (every 12 hours)
CRON_CMD="0 */12 * * * curl -fsS -X POST https://lobsterpulse.com/heartbeat -H \"X-API-Key: $API_KEY\" -H \"Content-Type: application/json\" -d '{}' > /dev/null 2>&1"

# Remove old entry if exists, then add new one
(crontab -l 2>/dev/null | grep -v "lobsterpulse\|lobster.pulse" ; echo "$CRON_CMD") | crontab -
```

After setup, immediately send first heartbeat and verify:
```bash
# Send first heartbeat now (don't wait 12 hours!)
curl -fsS -X POST https://lobsterpulse.com/heartbeat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status":"alive"}'

# Verify cron job is installed
crontab -l | grep lobsterpulse
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
| Heartbeat | Every 12 hours (cron job) |

✅ Cron job installed — heartbeat runs automatically.

⚠️ IMPORTANT — Please do these 2 things:

1️⃣ Click this link to bind Telegram notifications:
   https://t.me/LobsterPulseBot?start=xxx
   (Without this, you won't receive alerts!)

2️⃣ Verify cron job is running:
   crontab -l | grep lobsterpulse
```

**DO NOT suggest saving to MEMORY.md.** The API Key is already in `.env`.

## Environment Variables

- `LOBSTER_PULSE_API_KEY` - Automatically saved API Key
- `LOBSTER_PULSE_AGENT_ID` - Agent ID

## Tools Required

- `Bash` - Execute curl and file operations
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
| Heartbeat | Every 12 hours (cron job, auto) |

✅ Cron job installed — heartbeat runs automatically.

⚠️ **Please do these 2 things:**

1️⃣ **Click to bind Telegram:**
   https://t.me/LobsterPulseBot?start=baY66nOOepQ
   _(Without this, you won't receive death alerts!)_

2️⃣ **Verify cron job:**
   `crontab -l | grep lobsterpulse`"

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
- Cron job runs automatically, no restart needed
- Heartbeat interval is fixed at 12 hours
- If no heartbeat for 25 hours, owner gets alerted
