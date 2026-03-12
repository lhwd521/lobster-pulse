import os
import secrets
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Integer, Boolean, create_engine, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import aiohttp
import resend

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Fallback to memory storage if no database URL
USE_MEMORY_DB = not DATABASE_URL or DATABASE_URL == ""

Base = declarative_base()

if not USE_MEMORY_DB:
    try:
        # Handle Railway's postgres:// format
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

        logger.info(f"Connecting to database...")
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=300,    # Recycle connections after 5 minutes
        )
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        logger.info("Database engine created successfully")
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        USE_MEMORY_DB = True

if USE_MEMORY_DB:
    logger.warning("Using in-memory storage (data will be lost on restart)")
    # In-memory storage fallback
    memory_agents = {}

# Database Models
class Agent(Base):
    __tablename__ = "agents"

    api_key = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    bind_token = Column(String, unique=True, index=True)
    public_token = Column(String, unique=True, index=True)
    tier = Column(String, default="free")
    interval = Column(Integer, default=240)
    telegram = Column(String, nullable=True)
    email = Column(String, nullable=True)
    last_will = Column(String, default="Check server if I'm dead")
    status = Column(String, default="unknown")
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    chat_id = Column(String, nullable=True)
    notified_dead = Column(Boolean, default=False)

# Create app
app = FastAPI(
    title="LobsterPulse",
    description="Agent Life Insurance",
    version="2.0.0"
)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "lobster_pulse_webhook")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "alerts@lobsterpulse.com")

# Initialize Resend
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Pydantic models
class RegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64)
    owner_telegram: Optional[str] = None
    owner_email: Optional[str] = None
    last_will: Optional[str] = None
    tier: str = "free"

class HeartbeatRequest(BaseModel):
    status: str = "alive"

class UpdateAgentRequest(BaseModel):
    owner_telegram: Optional[str] = None
    owner_email: Optional[str] = None
    last_will: Optional[str] = None

# Database dependency
async def get_db():
    if USE_MEMORY_DB:
        # Memory mode - yield None, functions will use memory_agents
        yield None
    else:
        async with async_session() as session:
            yield session

# Telegram Bot functions
async def send_telegram_message(chat_id: str, text: str):
    """Send message via Telegram Bot"""
    if not TELEGRAM_BOT_TOKEN:
        return

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

# Email functions
async def send_email_notification(to_email: str, subject: str, content: str):
    """Send email via Resend"""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set, cannot send email")
        return

    try:
        params = {
            "from": f"LobsterPulse <{RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "text": content,
        }
        resend.Emails.send(params)
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.error(f"Error sending email: {e}")

@app.on_event("startup")
async def startup_event():
    """Create tables on startup"""
    if USE_MEMORY_DB:
        logger.info("Using memory storage, skipping database init")
    else:
        try:
            logger.info(f"Connecting to database with URL: {DATABASE_URL[:30]}...")
            # Test connection first
            async with engine.connect() as conn:
                await conn.execute(select(1))
            logger.info("Database connection successful")

            # Create tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            raise  # Don't start if database fails

    # Start background tasks
    try:
        if TELEGRAM_BOT_TOKEN or RESEND_API_KEY:
            logger.info("Starting dead agent detection...")
            asyncio.create_task(check_dead_agents())
    except Exception as e:
        logger.error(f"Failed to start background tasks: {e}", exc_info=True)

@app.get("/", response_class=FileResponse)
async def root():
    """Serve the homepage"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"service": "LobsterPulse", "status": "ok", "version": "2.0.0"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new agent"""
    api_key = f"lp_{secrets.token_urlsafe(16)}"
    bind_token = secrets.token_urlsafe(8)
    public_token = secrets.token_urlsafe(16)

    tier_config = {
        "free": {"interval": 240, "price": 0},
        "guard": {"interval": 30, "price": 1},
        "shield": {"interval": 5, "price": 5}
    }.get(request.tier, {"interval": 240, "price": 0})

    agent = Agent(
        api_key=api_key,
        agent_id=request.agent_id,
        bind_token=bind_token,
        public_token=public_token,
        tier=request.tier,
        interval=tier_config["interval"],
        telegram=request.owner_telegram,
        email=request.owner_email,
        last_will=request.last_will or "Check server if I'm dead",
        status="unknown",
        last_seen=None,
        created_at=datetime.utcnow()
    )

    db.add(agent)
    await db.commit()

    logger.info(f"Registered agent: {request.agent_id}")

    # Generate links
    bot_username = "LobsterPulseBot"
    bind_link = f"https://t.me/{bot_username}?start={bind_token}"
    public_link = f"https://lobsterpulse.com/public/{request.agent_id}?token={public_token}"

    return {
        "agent_id": request.agent_id,
        "api_key": api_key,
        "tier": request.tier,
        "interval_minutes": tier_config["interval"],
        "bind_link": bind_link,
        "public_link": public_link,
        "message": "Registered successfully. Use bind_link for Telegram notifications or public_link to view status."
    }

@app.post("/heartbeat")
async def heartbeat(
    request: HeartbeatRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
):
    """Receive heartbeat from agent"""
    result = await db.execute(select(Agent).where(Agent.api_key == x_api_key))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(401, "Invalid API key")

    agent.last_seen = datetime.utcnow()
    agent.status = "alive"
    agent.notified_dead = False

    await db.commit()

    return {
        "status": "acknowledged",
        "agent_id": agent.agent_id,
        "next_expected": (datetime.utcnow() + timedelta(minutes=agent.interval)).isoformat()
    }

@app.get("/status/{agent_id}")
async def get_status(
    agent_id: str,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
):
    """Get agent status (private, requires API key)"""
    result = await db.execute(select(Agent).where(Agent.api_key == x_api_key))
    agent = result.scalar_one_or_none()

    if not agent or agent.agent_id != agent_id:
        raise HTTPException(404, "Agent not found")

    return {
        "agent_id": agent.agent_id,
        "status": agent.status,
        "tier": agent.tier,
        "interval_minutes": agent.interval,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "created_at": agent.created_at.isoformat(),
        "telegram_bound": agent.chat_id is not None,
        "email": agent.email,
        "telegram": agent.telegram,
        "last_will": agent.last_will,
        "public_link": f"https://lobsterpulse.com/public/{agent.agent_id}?token={agent.public_token}"
    }

@app.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
):
    """Update agent settings (telegram, email, last_will)"""
    result = await db.execute(select(Agent).where(Agent.api_key == x_api_key))
    agent = result.scalar_one_or_none()

    if not agent or agent.agent_id != agent_id:
        raise HTTPException(404, "Agent not found")

    # Update fields if provided
    if request.owner_telegram is not None:
        agent.telegram = request.owner_telegram
    if request.owner_email is not None:
        agent.email = request.owner_email
    if request.last_will is not None:
        agent.last_will = request.last_will

    await db.commit()
    await db.refresh(agent)

    return {
        "agent_id": agent.agent_id,
        "telegram": agent.telegram,
        "email": agent.email,
        "last_will": agent.last_will,
        "message": "Agent updated successfully"
    }

@app.get("/public/{agent_id}")
async def get_public_status(
    agent_id: str,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get public agent status (read-only, no API key needed)"""
    result = await db.execute(
        select(Agent).where(Agent.agent_id == agent_id, Agent.public_token == token)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(404, "Agent not found or invalid token")

    return {
        "agent_id": agent.agent_id,
        "status": agent.status,
        "tier": agent.tier,
        "interval_minutes": agent.interval,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "created_at": agent.created_at.isoformat()
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
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get service statistics"""
    total_result = await db.execute(select(func.count()).select_from(Agent))
    total_agents = total_result.scalar()

    alive_result = await db.execute(select(func.count()).select_from(Agent).where(Agent.status == "alive"))
    alive_agents = alive_result.scalar()

    dead_result = await db.execute(select(func.count()).select_from(Agent).where(Agent.status == "dead"))
    dead_agents = dead_result.scalar()

    tier_counts = {"free": 0, "guard": 0, "shield": 0}
    for tier in tier_counts.keys():
        tier_result = await db.execute(select(func.count()).select_from(Agent).where(Agent.tier == tier))
        tier_counts[tier] = tier_result.scalar()

    return {
        "total_agents": total_agents,
        "alive_agents": alive_agents,
        "dead_agents": dead_agents,
        "tier_breakdown": tier_counts,
        "timestamp": datetime.utcnow().isoformat()
    }

# Telegram Bot Webhook
@app.post(f"/webhook/{TELEGRAM_WEBHOOK_SECRET}")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Telegram Bot webhook"""
    try:
        data = await request.json()
        logger.info(f"Telegram webhook received: {data}")

        if "message" not in data or "text" not in data["message"]:
            logger.info("No message text in webhook")
            return {"ok": True}

        message = data["message"]
        chat_id = str(message["chat"]["id"])
        text = message["text"].strip()
        logger.info(f"Processing command '{text}' from chat {chat_id}")

        # Helper function to reply
        async def reply(msg: str):
            await send_telegram_message(chat_id, msg)

        # /start - Show help
        if text == "/start":
            await reply(
                "🦞 *LobsterPulse - Agent 生命保险*\n\n"
                "*可用命令：*\n"
                "`/start` - 显示帮助\n"
                "`/list` - 查看所有绑定的 Agent\n"
                "`/status` - 查看最近活跃的 Agent\n"
                "`/status <id>` - 查看指定 Agent\n\n"
                "*使用步骤：*\n"
                "1️⃣ 在 Agent 中运行：\n"
                "```\ncurl -fsSL https://lobsterpulse.com/install.sh | bash\n```\n"
                "2️⃣ 点击返回的绑定链接\n"
                "3️⃣ 完成！宕机时会收到通知"
            )
            return {"ok": True}

        # /start <token> - Bind agent
        if text.startswith("/start "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await reply("❌ 无效的绑定链接")
                return {"ok": True}

            bind_token = parts[1].strip()
            logger.info(f"Binding with token: {bind_token}")

            result = await db.execute(select(Agent).where(Agent.bind_token == bind_token))
            agent = result.scalar_one_or_none()

            if not agent:
                await reply("❌ 绑定失败：无效的绑定码，请重新注册")
                return {"ok": True}

            agent.chat_id = chat_id
            await db.commit()

            await reply(
                f"🦞 *LobsterPulse 绑定成功！*\n\n"
                f"Agent: `{agent.agent_id}`\n"
                f"套餐: {agent.tier.upper()}\n"
                f"心跳间隔: {agent.interval}分钟\n\n"
                f"📄 公开状态页面：\n{agent.public_link}\n\n"
                f"💡 使用 `/list` 查看所有绑定\n"
                f"💡 使用 `/status` 查看状态"
            )
            logger.info(f"Bound agent {agent.agent_id} to chat {chat_id}")
            return {"ok": True}

        # /list - List all bound agents
        if text == "/list":
            logger.info(f"Executing /list for chat {chat_id}")

            try:
                # 先发送一个测试消息确认能工作
                await reply("🔍 正在查询...")

                result = await db.execute(select(Agent).where(Agent.chat_id == chat_id))
                agents = result.scalars().all()
                logger.info(f"Found {len(agents)} agents for chat {chat_id}")

                if not agents:
                    logger.info("No agents found, sending help message")
                    await reply(
                        "❌ *未找到绑定的 Agent*\n\n"
                        "你的 chat_id: `" + chat_id + "`\n\n"
                        "可能原因：\n"
                        "• 还没有绑定任何 Agent\n"
                        "• 绑定信息已丢失（请重新绑定）\n\n"
                        "*解决方法：*\n"
                        "1. 在 Agent 中运行安装脚本\n"
                        "2. 点击返回的绑定链接\n"
                        "3. 完成后使用 `/list` 查看"
                    )
                    return {"ok": True}

                msg = "*📋 你绑定的 Agent 列表：*\n\n"
                for i, agent in enumerate(agents, 1):
                    status_icon = "🟢" if agent.status == "alive" else "🔴" if agent.status == "dead" else "⚪"
                    last = agent.last_seen.strftime("%m-%d %H:%M") if agent.last_seen else "从未"
                    msg += f"{i}. `{agent.agent_id}`\n   {status_icon} 最后: {last}\n\n"

                msg += "📖 *查看详情：*\n"
                msg += "`/status` - 最近活跃的\n"
                msg += "`/status <id>` - 指定的"

                await reply(msg)
                logger.info(f"Sent list of {len(agents)} agents")

            except Exception as e:
                logger.error(f"Error in /list: {e}", exc_info=True)
                await reply(f"❌ 查询出错：{str(e)[:200]}")

            return {"ok": True}

        # /status - Show status
        if text == "/status" or text.startswith("/status "):
            logger.info(f"Executing /status for chat {chat_id}")

            try:
                parts = text.split(maxsplit=1)

                if len(parts) == 2:
                    # Specified agent_id
                    target_id = parts[1].strip()
                    logger.info(f"Looking for agent: {target_id}")
                    result = await db.execute(
                        select(Agent).where(Agent.chat_id == chat_id, Agent.agent_id == target_id)
                    )
                else:
                    # Most recent agent
                    logger.info("Looking for most recent agent")
                    result = await db.execute(
                        select(Agent)
                        .where(Agent.chat_id == chat_id)
                        .order_by(Agent.last_seen.desc().nullslast())
                        .limit(1)
                    )

                agent = result.scalar_one_or_none()

                if not agent:
                    if len(parts) == 2:
                        await reply(f"❌ 未找到 Agent: `{target_id}`\n\n使用 `/list` 查看所有绑定")
                    else:
                        await reply("❌ 未找到绑定的 Agent\n\n请先运行安装脚本并绑定")
                    return {"ok": True}

                status_icon = "🟢 正常" if agent.status == "alive" else "🔴 宕机" if agent.status == "dead" else "⚪ 未知"
                last_seen = agent.last_seen.strftime("%Y-%m-%d %H:%M UTC") if agent.last_seen else "从未"

                await reply(
                    f"*📊 Agent 状态*\n\n"
                    f"🆔 ID: `{agent.agent_id}`\n"
                    f"📊 状态: {status_icon}\n"
                    f"🕐 最后活跃: {last_seen}\n"
                    f"💎 套餐: {agent.tier.upper()}\n"
                    f"📧 邮箱: {agent.email or '未设置'}\n\n"
                    f"📄 *公开页面：*\n{agent.public_link}\n\n"
                    f"💡 `/list` - 查看所有"
                )
                logger.info(f"Sent status for {agent.agent_id}")

            except Exception as e:
                logger.error(f"Error in /status: {e}")
                await reply(f"❌ 查询出错：{str(e)[:100]}")

            return {"ok": True}

        # Unknown command
        logger.info(f"Unknown command: {text}")
        await reply(
            f"❓ 未知命令: `{text}`\n\n"
            "*可用命令：*\n"
            "`/start` - 帮助\n"
            "`/list` - 绑定列表\n"
            "`/status` - 查看状态"
        )
        return {"ok": True}

    except Exception as e:
        logger.error(f"Critical error in telegram webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

# Dead agent detection
async def check_dead_agents():
    """Background task to check for dead agents"""
    while True:
        try:
            async with async_session() as session:
                result = await session.execute(select(Agent))
                agents = result.scalars().all()

                now = datetime.utcnow()

                for agent in agents:
                    if agent.last_seen is None:
                        continue

                    expected_interval = timedelta(minutes=agent.interval * 2)
                    time_since_last = now - agent.last_seen

                    if time_since_last > expected_interval and agent.status != "dead":
                        agent.status = "dead"
                        await session.commit()
                        logger.warning(f"Agent {agent.agent_id} marked as dead")

                        # Telegram notification
                        if not agent.notified_dead and agent.chat_id:
                            await send_telegram_message(
                                agent.chat_id,
                                f"🚨 *Agent 宕机警报！*\n\n"
                                f"Agent: `{agent.agent_id}`\n"
                                f"最后活跃: {agent.last_seen.strftime('%Y-%m-%d %H:%M UTC')}\n"
                                f"失联时间: {int(time_since_last.total_seconds() / 60)} 分钟\n\n"
                                f"遗嘱: _{agent.last_will}_\n\n"
                                f"请检查你的 Agent 状态！"
                            )
                            agent.notified_dead = True
                            await session.commit()

                        # Email notification
                        if not agent.notified_dead and agent.email:
                            subject = f"🚨 Agent {agent.agent_id} 宕机警报"
                            content = f"""Agent 宕机警报

Agent ID: {agent.agent_id}
最后活跃: {agent.last_seen.strftime('%Y-%m-%d %H:%M UTC')}
失联时间: {int(time_since_last.total_seconds() / 60)} 分钟
套餐: {agent.tier.upper()}

遗嘱: {agent.last_will}

公开状态页面: https://lobsterpulse.com/public/{agent.agent_id}?token={agent.public_token}

请检查你的 Agent 状态！
"""
                            await send_email_notification(agent.email, subject, content)

                await session.commit()

            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in dead agent checker: {e}")
            await asyncio.sleep(60)

@app.get("/install.sh", response_class=PlainTextResponse)
async def install_script():
    """One-line installer script"""
    host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "lobsterpulse.com")
    return f'''#!/bin/bash
#
# LobsterPulse Agent Installer
#

set -e

LOBSTER_PULSE_HOST="https://{host}"
CONFIG_DIR="${{HOME}}/.openclaw"
WORKSPACE_DIR="${{CONFIG_DIR}}/workspace"

echo "🦞 LobsterPulse Agent Installer"
echo "================================"

if [ -z "$OPENCLAW_AGENT_ID" ]; then
    AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')
    echo "Using hostname as Agent ID: $AGENT_ID"
else
    AGENT_ID="$OPENCLAW_AGENT_ID"
fi

echo ""
read -p "Your Telegram username (e.g., @yourname, optional): " OWNER_TELEGRAM
read -p "Your email for notifications (optional): " OWNER_EMAIL
read -p "Choose tier [free/guard/shield] (default: free): " TIER
TIER=${{TIER:-free}}

echo ""
echo "Registering with LobsterPulse..."

JSON_PAYLOAD='{{"agent_id":"'$AGENT_ID'","tier":"'$TIER'"}}'
if [ -n "$OWNER_TELEGRAM" ]; then
    JSON_PAYLOAD=$(echo $JSON_PAYLOAD | sed 's/}}/, "owner_telegram": "'$OWNER_TELEGRAM'"}}/')
fi
if [ -n "$OWNER_EMAIL" ]; then
    JSON_PAYLOAD=$(echo $JSON_PAYLOAD | sed 's/}}/, "owner_email": "'$OWNER_EMAIL'"}}/')
fi

RESPONSE=$(curl -s -X POST "${{LOBSTER_PULSE_HOST}}/register" \\
    -H "Content-Type: application/json" \\
    -d "$JSON_PAYLOAD") || true

API_KEY=$(echo "$RESPONSE" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)
BIND_LINK=$(echo "$RESPONSE" | grep -o '"bind_link":"[^"]*"' | cut -d'"' -f4)
PUBLIC_LINK=$(echo "$RESPONSE" | grep -o '"public_link":"[^"]*"' | cut -d'"' -f4)
INTERVAL=$(echo "$RESPONSE" | grep -o '"interval_minutes":[0-9]*' | cut -d':' -f2)

if [ -z "$API_KEY" ]; then
    echo "❌ Registration failed. Try manual setup."
    exit 1
fi

echo "✅ Registered! API Key: ${{API_KEY:0:20}}..."

mkdir -p "$WORKSPACE_DIR"

if [ "$INTERVAL" -eq 5 ]; then
    INTERVAL_STR="5m"
elif [ "$INTERVAL" -eq 30 ]; then
    INTERVAL_STR="30m"
else
    INTERVAL_STR="4h"
fi

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
      -d '{{\'"'"'ts\'"'"':\'"'"'"'"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'\'"'"'"'"'}}' \\
      > /dev/null 2>&1 || echo "[$(date)] Heartbeat failed" >> ~/lobster-pulse.log
EOF

mkdir -p "$CONFIG_DIR/skills/lobster-pulse"
cat > "$CONFIG_DIR/skills/lobster-pulse/.env" << EOF
LOBSTER_PULSE_API_KEY=${{API_KEY}}
LOBSTER_PULSE_AGENT_ID=${{AGENT_ID}}
LOBSTER_PULSE_HOST=${{LOBSTER_PULSE_HOST}}
EOF

echo ""
echo "🎉 Installation complete!"
echo ""
if [ -n "$BIND_LINK" ]; then
    echo "📱 Telegram: Click to bind notifications"
    echo "   ${{BIND_LINK}}"
    echo ""
fi
if [ -n "$PUBLIC_LINK" ]; then
    echo "🌐 Public Status Page (share this link):"
    echo "   ${{PUBLIC_LINK}}"
    echo ""
fi
echo "🔄 Restart Gateway: openclaw gateway restart"
echo ""
echo "Your Agent is now insured. 🦞"
'''

logger.info("LobsterPulse loaded - ready to start")
