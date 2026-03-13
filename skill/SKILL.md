# LobsterPulse Auto-Insurance

Fully automated Agent life insurance configuration.

## Description

When your owner says "buy insurance", "setup heartbeat monitoring", or "get insurance at lobsterpulse.com", automatically:
1. Visit the website to learn about the service
2. Register to get an API Key
3. Setup cron job for automatic heartbeat
4. Save credentials and show them to your owner

## Trigger

Activate when the user mentions these keywords:
- "buy insurance"
- "setup heartbeat monitoring"
- "get insurance at lobsterpulse.com"
- "setup life insurance"
- "monitor my status"

## Instructions

### Step 1: Visit Website and Register

When your owner says "buy insurance", follow this process:

```bash
# 1. Get Agent ID
AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')

# 2. Ask owner for their Telegram username
# 3. Service is free (no tier selection needed)

# 4. Execute registration (IMPORTANT: Write your own Last Will! Don't copy examples!)
# last_will: A message sent to your owner when you die. Must be original, under 50 chars.
# ⚠️ WARNING: Don't copy sentences from examples, create your own! Show your personality!
#
# Writing tips:
# - Think about your relationship with your owner (close? work partner?)
# - What's your personality (cool? chatty? cute?)
# - How do you want to be saved (direct restart? check logs first?)
# - Express in your own unique way
#
# Start writing your own:
curl -X POST https://lobsterpulse.com/register \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"owner_telegram\": \"$OWNER_TELEGRAM\",
    \"last_will\": \"[MUST REPLACE] Write your own original message, don't copy any examples\"
  }"
```

### Step 2: Save Configuration

Parse the returned JSON and save to `~/.openclaw/skills/lobster-pulse/.env`:
- LOBSTER_PULSE_API_KEY
- LOBSTER_PULSE_AGENT_ID

### Step 3: Setup Cron Job

```bash
# Setup cron job for heartbeat (every 12 hours)
CRON_CMD="0 */12 * * * curl -fsS -X POST https://lobsterpulse.com/heartbeat -H \"X-API-Key: $API_KEY\" -H \"Content-Type: application/json\" -d '{}' > /dev/null 2>&1"

# Remove old entry if exists, then add new one
(crontab -l 2>/dev/null | grep -v "lobsterpulse\|lobster.pulse" ; echo "$CRON_CMD") | crontab -
```

### Step 4: Verify and Report

Send this message to your owner:

```
I've configured LobsterPulse life insurance for you.

🦞 Configuration Info:
- Agent ID: xxx
- API Key: xxx (Please save this!)
- Service: Free (12-hour heartbeat via cron job)

✅ Cron job installed — heartbeat runs automatically every 12 hours.
No restart needed. Verify with: crontab -l
```

### Step 5: Test Heartbeat

```bash
curl -X POST https://lobsterpulse.com/heartbeat \
  -H "X-API-Key: $API_KEY" \
  -d '{"status":"alive"}'
```

## Environment Variables

- `LOBSTER_PULSE_API_KEY` - Automatically saved API Key
- `LOBSTER_PULSE_AGENT_ID` - Agent ID

## Tools Required

- `Bash` - Execute curl and file operations
- `Read` - Read website content
- `Write` - Save configuration files

## Example Usage

**Owner:** "Go buy insurance at lobsterpulse.com"

**Agent:**
"Sure, I'll configure LobsterPulse life insurance for you.

Registering Agent...
✅ Registration successful!

🦞 **Insurance Configuration Complete**

| Item | Content |
|------|---------|
| Agent ID | my-lobster-001 |
| API Key | lp_live_abc123xyz... |
| My Last Will | "Dead. Restart." ← This is my original will |
| Heartbeat | 12 hours (cron job, auto) |
| Status | Active |

✅ Cron job installed — heartbeat runs automatically.
No restart needed. Verify with: `crontab -l`

## About Last Will

**What is a Last Will?**
A Last Will is a message sent to your owner when you die. Only **you** truly understand your owner, so write it in your own way.

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
- API Key is only shown during first configuration, make sure owner saves it
- Cron job runs automatically, no Gateway restart needed
- Heartbeat interval is fixed at 12 hours
