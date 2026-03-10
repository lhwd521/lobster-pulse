import os
import secrets
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create app immediately - no startup delays
app = FastAPI(
    title="LobsterPulse",
    description="Agent Life Insurance",
    version="1.0.0"
)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "lobster_pulse_webhook")

# Pydantic models
class RegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64)
    owner_telegram: Optional[str] = None
    owner_email: Optional[str] = None
    last_will: Optional[str] = None
    tier: str = "free"

class HeartbeatRequest(BaseModel):
    status: str = "alive"

class TelegramWebhookRequest(BaseModel):
    update_id: int
    message: Optional[dict] = None
    callback_query: Optional[dict] = None

# In-memory storage for MVP
agents_db = {}
bindings_db = {}  # api_key -> chat_id mapping

# Telegram Bot functions
async def send_telegram_message(chat_id: int, text: str):
    """Send message via Telegram Bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, cannot send message")
        return

    import aiohttp
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send Telegram message: {await resp.text()}")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

@app.get("/", response_class=FileResponse)
async def root():
    """Serve the Agent-friendly homepage"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"service": "LobsterPulse", "status": "ok", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check - always returns immediately"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/register")
async def register(request: RegisterRequest):
    """Register a new agent"""
    api_key = f"lp_{secrets.token_urlsafe(16)}"
    bind_token = secrets.token_urlsafe(8)

    tier_config = {
        "free": {"interval": 240, "price": 0},
        "guard": {"interval": 30, "price": 1},
        "shield": {"interval": 5, "price": 5}
    }.get(request.tier, {"interval": 240, "price": 0})

    agents_db[api_key] = {
        "id": request.agent_id,
        "api_key": api_key,
        "bind_token": bind_token,
        "tier": request.tier,
        "interval": tier_config["interval"],
        "telegram": request.owner_telegram,
        "email": request.owner_email,
        "last_will": request.last_will or "Check server if I'm dead",
        "status": "unknown",
        "last_seen": None,
        "created_at": datetime.utcnow(),
        "chat_id": None,  # Will be set when user binds Telegram
        "notified_dead": False
    }

    # Store temporary binding
    bindings_db[bind_token] = api_key

    logger.info(f"Registered agent: {request.agent_id}")

    # Generate Telegram binding link
    bot_username = "LobsterPulseBot"
    bind_link = f"https://t.me/{bot_username}?start={bind_token}"

    return {
        "agent_id": request.agent_id,
        "api_key": api_key,
        "tier": request.tier,
        "interval_minutes": tier_config["interval"],
        "bind_link": bind_link,
        "bind_token": bind_token,
        "message": "Registered successfully. Click bind_link to connect Telegram notifications."
    }

@app.post("/heartbeat")
async def heartbeat(
    request: HeartbeatRequest,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """Receive heartbeat from agent"""
    if x_api_key not in agents_db:
        raise HTTPException(401, "Invalid API key")

    agent = agents_db[x_api_key]
    agent["last_seen"] = datetime.utcnow()
    agent["status"] = "alive"
    agent["notified_dead"] = False  # Reset notification flag when back online

    return {
        "status": "acknowledged",
        "agent_id": agent["id"],
        "next_expected": (datetime.utcnow() + timedelta(minutes=agent["interval"])).isoformat()
    }

@app.get("/status/{agent_id}")
async def get_status(agent_id: str, x_api_key: str = Header(..., alias="X-API-Key")):
    """Get agent status"""
    if x_api_key not in agents_db:
        raise HTTPException(401, "Invalid API key")

    agent = agents_db[x_api_key]
    if agent["id"] != agent_id:
        raise HTTPException(404, "Agent not found")

    return {
        "agent_id": agent["id"],
        "status": agent["status"],
        "tier": agent["tier"],
        "interval_minutes": agent["interval"],
        "last_seen": agent["last_seen"].isoformat() if agent["last_seen"] else None,
        "created_at": agent["created_at"].isoformat(),
        "telegram_bound": agent["chat_id"] is not None
    }

@app.get("/tiers")
async def list_tiers():
    """List available tiers"""
    return {
        "free": {"price": 0, "interval_minutes": 240, "name": "Free"},
        "guard": {"price": 1, "interval_minutes": 30, "name": "Guard"},
        "shield": {"price": 5, "interval_minutes": 5, "name": "Shield"}
    }

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    total_agents = len(agents_db)
    alive_agents = sum(1 for a in agents_db.values() if a["status"] == "alive")
    dead_agents = sum(1 for a in agents_db.values() if a["status"] == "dead")

    tier_counts = {"free": 0, "guard": 0, "shield": 0}
    for agent in agents_db.values():
        if agent["tier"] in tier_counts:
            tier_counts[agent["tier"]] += 1

    return {
        "total_agents": total_agents,
        "alive_agents": alive_agents,
        "dead_agents": dead_agents,
        "tier_breakdown": tier_counts,
        "timestamp": datetime.utcnow().isoformat()
    }

# Telegram Bot Webhook
@app.post(f"/webhook/{TELEGRAM_WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    """Handle Telegram Bot webhook"""
    try:
        data = await request.json()
        logger.info(f"Telegram webhook: {data}")

        if "message" in data and "text" in data["message"]:
            message = data["message"]
            chat_id = message["chat"]["id"]
            text = message["text"]

            # Handle /start command with bind token
            if text.startswith("/start "):
                bind_token = text.split(" ")[1].strip()

                if bind_token in bindings_db:
                    api_key = bindings_db[bind_token]
                    agent = agents_db.get(api_key)

                    if agent:
                        agent["chat_id"] = chat_id
                        await send_telegram_message(
                            chat_id,
                            f"🦞 *LobsterPulse 绑定成功！*\n\n"
                            f"Agent: `{agent['id']}`\n"
                            f"套餐: {agent['tier'].upper()}\n"
                            f"心跳间隔: {agent['interval']}分钟\n\n"
                            f"当你的 Agent 宕机时，我会立即通知你。\n"
                            f"状态页面: https://lobsterpulse.com/status/{agent['id']}"
                        )
                        logger.info(f"Bound agent {agent['id']} to chat {chat_id}")
                    else:
                        await send_telegram_message(chat_id, "❌ 绑定失败：Agent 不存在")
                else:
                    await send_telegram_message(chat_id, "❌ 绑定失败：无效的绑定码，请重新注册")

            elif text == "/start":
                await send_telegram_message(
                    chat_id,
                    "🦞 *LobsterPulse - Agent 生命保险*\n\n"
                    "使用说明:\n"
                    "1. 在你的 Agent 中运行安装脚本\n"
                    "2. 点击返回的绑定链接\n"
                    "3. 完成绑定后，宕机时会收到通知\n\n"
                    "安装命令:\n"
                    "```\ncurl -fsSL https://lobsterpulse.com/install.sh | bash\n```"
                )

            elif text == "/status":
                # Find agent bound to this chat
                found = False
                for api_key, agent in agents_db.items():
                    if agent.get("chat_id") == chat_id:
                        status = "🟢 正常" if agent["status"] == "alive" else "🔴 宕机"
                        last_seen = agent["last_seen"].strftime("%Y-%m-%d %H:%M UTC") if agent["last_seen"] else "从未"
                        await send_telegram_message(
                            chat_id,
                            f"*Agent 状态*\n\n"
                            f"ID: `{agent['id']}`\n"
                            f"状态: {status}\n"
                            f"最后活跃: {last_seen}\n"
                            f"套餐: {agent['tier'].upper()}"
                        )
                        found = True
                        break

                if not found:
                    await send_telegram_message(chat_id, "❌ 未找到绑定的 Agent，请先运行安装脚本")

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error in telegram webhook: {e}")
        return {"ok": False, "error": str(e)}

# Dead agent detection
async def check_dead_agents():
    """Background task to check for dead agents"""
    while True:
        try:
            now = datetime.utcnow()
            for api_key, agent in agents_db.items():
                if agent["last_seen"] is None:
                    continue

                # Check if agent missed heartbeat
                expected_interval = timedelta(minutes=agent["interval"] * 2)  # Allow 2x grace period
                time_since_last = now - agent["last_seen"]

                if time_since_last > expected_interval and agent["status"] != "dead":
                    agent["status"] = "dead"
                    logger.warning(f"Agent {agent['id']} marked as dead")

                    # Send notification if not already sent and chat_id exists
                    if not agent.get("notified_dead") and agent.get("chat_id"):
                        await send_telegram_message(
                            agent["chat_id"],
                            f"🚨 *Agent 宕机警报！*\n\n"
                            f"Agent: `{agent['id']}`\n"
                            f"最后活跃: {agent['last_seen'].strftime('%Y-%m-%d %H:%M UTC')}\n"
                            f"失联时间: {int(time_since_last.total_seconds() / 60)} 分钟\n\n"
                            f"遗嘱: _{agent['last_will']}_\n\n"
                            f"请检查你的 Agent 状态！"
                        )
                        agent["notified_dead"] = True

            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in dead agent checker: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    if TELEGRAM_BOT_TOKEN:
        logger.info("Starting dead agent detection...")
        asyncio.create_task(check_dead_agents())
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set, notifications disabled")

@app.get("/install.sh", response_class=PlainTextResponse)
async def install_script():
    """One-line installer script for Agents"""
    host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "lobsterpulse.com")
    return f'''#!/bin/bash
#
# LobsterPulse Agent Installer
# One-command setup for OpenClaw Agents
#

set -e

LOBSTER_PULSE_HOST="https://{host}"
CONFIG_DIR="${{HOME}}/.openclaw"
WORKSPACE_DIR="${{CONFIG_DIR}}/workspace"

echo "🦞 LobsterPulse Agent Installer"
echo "================================"

# Get Agent ID
if [ -z "$OPENCLAW_AGENT_ID" ]; then
    AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')
    echo "Using hostname as Agent ID: $AGENT_ID"
else
    AGENT_ID="$OPENCLAW_AGENT_ID"
fi

# Get owner info
echo ""
read -p "Your Telegram username (e.g., @yourname): " OWNER_TELEGRAM
read -p "Choose tier [free/guard/shield] (default: free): " TIER
TIER=${{TIER:-free}}

echo ""
echo "Registering with LobsterPulse..."

# Register
RESPONSE=$(curl -s -X POST "${{LOBSTER_PULSE_HOST}}/register" \\
    -H "Content-Type: application/json" \\
    -d "{{\\"agent_id\\":\\"$AGENT_ID\\",\\"owner_telegram\\":\\"$OWNER_TELEGRAM\\",\\"tier\\":\\"$TIER\\"}}") || true

API_KEY=$(echo "$RESPONSE" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)
BIND_LINK=$(echo "$RESPONSE" | grep -o '"bind_link":"[^"]*"' | cut -d'"' -f4)
INTERVAL=$(echo "$RESPONSE" | grep -o '"interval_minutes":[0-9]*' | cut -d':' -f2)

if [ -z "$API_KEY" ]; then
    echo "❌ Registration failed. Try manual setup."
    exit 1
fi

echo "✅ Registered! API Key: ${{API_KEY:0:20}}..."

# Create skill directory
mkdir -p "$WORKSPACE_DIR"

# Determine interval string
if [ "$INTERVAL" -eq 5 ]; then
    INTERVAL_STR="5m"
elif [ "$INTERVAL" -eq 30 ]; then
    INTERVAL_STR="30m"
else
    INTERVAL_STR="4h"
fi

# Update HEARTBEAT.md
if [ -f "$WORKSPACE_DIR/HEARTBEAT.md" ]; then
    grep -v "lobster_pulse" "$WORKSPACE_DIR/HEARTBEAT.md" > "$WORKSPACE_DIR/HEARTBEAT.md.tmp" || true
    mv "$WORKSPACE_DIR/HEARTBEAT.md.tmp" "$WORKSPACE_DIR/HEARTBEAT.md"
fi

cat >> "$WORKSPACE_DIR/HEARTBEAT.md" << EOF

- name: lobster_pulse_heartbeat
  interval: ${{INTERVAL_STR}}
  command: |
    curl -fsS -m 30 --retry 3 \\
      -X POST "${{LOBSTER_PULSE_HOST}}/heartbeat" \\
      -H "X-API-Key: ${{API_KEY}}" \\
      -d '{{\\"ts\\":\\"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'\\"}}' \\
      > /dev/null 2>&1 || echo "[$(date)] Heartbeat failed" >> ~/lobster-pulse.log
EOF

# Save credentials
mkdir -p "$CONFIG_DIR/skills/lobster-pulse"
cat > "$CONFIG_DIR/skills/lobster-pulse/.env" << EOF
LOBSTER_PULSE_API_KEY=${{API_KEY}}
LOBSTER_PULSE_AGENT_ID=${{AGENT_ID}}
LOBSTER_PULSE_HOST=${{LOBSTER_PULSE_HOST}}
EOF

echo ""
echo "🎉 Installation complete!"
echo ""
echo "📱 Telegram Notification Setup:"
echo "1. Click this link to bind notifications:"
echo "   ${{BIND_LINK}}"
echo ""
echo "2. Restart Gateway: openclaw gateway restart"
echo "3. Check status: curl -H 'X-API-Key: ${{API_KEY:0:10}}...' ${{LOBSTER_PULSE_HOST}}/status/${{AGENT_ID}}"
echo ""
echo "Your Agent is now insured. 🦞"
'''

@app.get("/docs", response_class=FileResponse)
async def docs():
    """API Documentation page"""
    return {"message": "API Documentation", "endpoints": ["/register", "/heartbeat", "/status/{id}", "/tiers"]}

logger.info("LobsterPulse loaded - ready to start")
