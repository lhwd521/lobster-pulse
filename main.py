import os
import secrets
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import aiohttp
import resend

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Background thread flag
background_thread_started = False

# Database setup - PostgreSQL with SQLite fallback
Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "")
logger.info(f"DATABASE_URL present: {bool(DATABASE_URL)}")

class Agent(Base):
    __tablename__ = "agents"

    api_key = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    bind_token = Column(String, unique=True, index=True)
    public_token = Column(String, unique=True, index=True)
    tier = Column(String, default="free")
    interval = Column(Integer, default=720)
    telegram = Column(String, nullable=True)
    email = Column(String, nullable=True)
    last_will = Column(String, default="Check server if I'm dead")
    status = Column(String, default="unknown")
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    chat_id = Column(String, nullable=True)
    notified_dead = Column(Boolean, default=False)

# Initialize database
engine = None
SessionLocal = None

if DATABASE_URL:
    try:
        logger.info("Connecting to PostgreSQL...")
        # Use pg8000 driver (pure Python, no libpq needed)
        db_url = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://")
        engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL database initialized successfully")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        engine = None

# Fallback to SQLite
if not engine:
    logger.info("Using SQLite fallback...")
    engine = create_engine("sqlite:///./lobsterpulse.db", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("SQLite database initialized")

def get_db():
    if SessionLocal is None:
        raise HTTPException(500, "Database not available")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "lobster_pulse_webhook")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

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

# Create app
app = FastAPI(
    title="LobsterPulse",
    description="Agent Life Insurance",
    version="2.1.0"
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Telegram Bot functions
async def send_telegram_message(chat_id: str, text: str):
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
    if not RESEND_API_KEY:
        return

    try:
        params = {
            "from": "LobsterPulse <alerts@lobsterpulse.com>",
            "to": [to_email],
            "subject": subject,
            "text": content,
        }
        resend.Emails.send(params)
    except Exception as e:
        logger.error(f"Error sending email: {e}")

@app.get("/", response_class=FileResponse)
async def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"service": "LobsterPulse", "status": "ok", "version": "2.1.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat(), "db_connected": engine is not None}

@app.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    api_key = f"lp_{secrets.token_hex(16)}"
    bind_token = secrets.token_hex(8)
    public_token = secrets.token_hex(16)

    # Single free tier: 12h interval
    interval = 720

    agent = Agent(
        api_key=api_key,
        agent_id=request.agent_id,
        bind_token=bind_token,
        public_token=public_token,
        tier="free",
        interval=interval,
        telegram=request.owner_telegram,
        email=request.owner_email,
        last_will=request.last_will or "Master, I'm waiting for you. ——Your Agent",
        status="unknown",
        last_seen=None,
        created_at=datetime.utcnow()
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    logger.info(f"Registered agent: {request.agent_id}")

    bot_username = "LobsterPulseBot"
    bind_link = f"https://t.me/{bot_username}?start={bind_token}"
    public_link = f"https://lobsterpulse.com/public/{request.agent_id}?token={public_token}"

    return {
        "agent_id": request.agent_id,
        "api_key": api_key,
        "tier": "free",
        "interval_minutes": interval,
        "bind_link": bind_link,
        "public_link": public_link,
    }

@app.post("/heartbeat")
async def heartbeat(
    request: HeartbeatRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()

    if not agent:
        raise HTTPException(401, "Invalid API key")

    agent.last_seen = datetime.utcnow()
    agent.status = "alive"
    agent.notified_dead = False

    db.commit()

    return {
        "status": "acknowledged",
        "agent_id": agent.agent_id,
        "next_expected": (datetime.utcnow() + timedelta(minutes=agent.interval)).isoformat()
    }

@app.get("/status/{agent_id}")
async def get_status(
    agent_id: str,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()

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
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()

    if not agent or agent.agent_id != agent_id:
        raise HTTPException(404, "Agent not found")

    if request.owner_telegram is not None:
        agent.telegram = request.owner_telegram
    if request.owner_email is not None:
        agent.email = request.owner_email
    if request.last_will is not None:
        agent.last_will = request.last_will

    db.commit()
    db.refresh(agent)

    return {
        "agent_id": agent.agent_id,
        "telegram": agent.telegram,
        "email": agent.email,
        "last_will": agent.last_will,
    }

@app.get("/public/{agent_id}")
async def get_public_status(
    agent_id: str,
    token: str,
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id, Agent.public_token == token).first()

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
    return {
        "free": {"price": 0, "interval_minutes": 720, "name": "Free"}
    }

@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    total_agents = db.query(Agent).count()
    alive_agents = db.query(Agent).filter(Agent.status == "alive").count()
    dead_agents = db.query(Agent).filter(Agent.status == "dead").count()

    return {
        "total_agents": total_agents,
        "alive_agents": alive_agents,
        "dead_agents": dead_agents,
        "timestamp": datetime.utcnow().isoformat()
    }

# Telegram Bot Webhook
@app.post(f"/webhook/{TELEGRAM_WEBHOOK_SECRET}")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        logger.info(f"Telegram webhook: {data}")

        if "message" not in data or "text" not in data["message"]:
            return {"ok": True}

        message = data["message"]
        chat_id = str(message["chat"]["id"])
        text = message["text"].strip()

        async def reply(msg: str):
            await send_telegram_message(chat_id, msg)

        if text == "/start":
            await reply(
                "🦞 *LobsterPulse - Agent Life Insurance*\n\n"
                "*Available Commands:*\n"
                "`/start` - Show help\n"
                "`/list` - List all bound Agents\n"
                "`/status` - View most recent Agent\n"
                "`/status <id>` - View specific Agent\n\n"
                "*Setup Steps:*\n"
                "1️⃣ Run on your Agent:\n"
                "```\ncurl -fsSL https://lobsterpulse.com/install.sh | bash\n```\n"
                "2️⃣ Click the binding link returned\n"
                "3️⃣ Done! You'll be notified when dead"
            )
            return {"ok": True}

        if text.startswith("/start "):
            bind_token = text.split(maxsplit=1)[1].strip() if len(text.split()) > 1 else ""
            agent = db.query(Agent).filter(Agent.bind_token == bind_token).first()

            if agent:
                agent.chat_id = chat_id
                db.commit()
                public_link = f"https://lobsterpulse.com/public/{agent.agent_id}?token={agent.public_token}"
                await reply(
                    f"🦞 *Binding Successful!*\n\n"
                    f"Agent: `{agent.agent_id}`\n"
                    f"Heartbeat: Every 12 hours\n\n"
                    f"📄 [Public Status]({public_link})\n\n"
                    f"💡 Use `/list` to view all"
                )
            else:
                await reply("❌ Binding failed: Invalid token")
            return {"ok": True}

        if text == "/list":
            agents = db.query(Agent).filter(Agent.chat_id == chat_id).all()

            if not agents:
                await reply("❌ No bound Agents found. Please run the install script first.")
                return {"ok": True}

            msg = "*📋 Your Bound Agents:*\n\n"
            for i, agent in enumerate(agents, 1):
                status_icon = "🟢" if agent.status == "alive" else "🔴" if agent.status == "dead" else "⚪"
                last = agent.last_seen.strftime("%m-%d %H:%M") if agent.last_seen else "Never"
                msg += f"{i}. `{agent.agent_id}`\n   {status_icon} Last: {last}\n\n"

            msg += "📖 View details: `/status` or `/status <id>`"
            await reply(msg)
            return {"ok": True}

        if text == "/status" or text.startswith("/status "):
            parts = text.split(maxsplit=1)

            if len(parts) == 2:
                target_id = parts[1].strip()
                agent = db.query(Agent).filter(Agent.chat_id == chat_id, Agent.agent_id == target_id).first()
            else:
                agent = db.query(Agent).filter(Agent.chat_id == chat_id).order_by(Agent.last_seen.desc().nullslast()).first()

            if not agent:
                await reply("❌ Agent not found")
                return {"ok": True}

            status_icon = "🟢 Alive" if agent.status == "alive" else "🔴 Dead" if agent.status == "dead" else "⚪ Unknown"
            last_seen = agent.last_seen.strftime("%Y-%m-%d %H:%M UTC") if agent.last_seen else "Never"
            public_link = f"https://lobsterpulse.com/public/{agent.agent_id}?token={agent.public_token}"

            await reply(
                f"*📊 Agent Status*\n\n"
                f"🆔 ID: `{agent.agent_id}`\n"
                f"📊 Status: {status_icon}\n"
                f"🕐 Last Seen: {last_seen}\n\n"
                f"📄 [Public Page]({public_link})\n\n"
                f"💡 `/list` - View all"
            )
            return {"ok": True}

        await reply(f"❓ Unknown command: `{text}`\n\nAvailable: `/start`, `/list`, `/status`")
        return {"ok": True}

    except Exception as e:
        logger.error(f"Error in telegram webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

# Background task for dead agent detection
def check_dead_agents_sync():
    """Run in background thread"""
    while True:
        try:
            if SessionLocal is None:
                time.sleep(60)
                continue

            db = SessionLocal()
            try:
                agents = db.query(Agent).all()
                now = datetime.utcnow()

                for agent in agents:
                    if agent.last_seen is None:
                        continue

                    # Alert after 25 hours of silence (12h interval + 13h buffer)
                    expected_interval = timedelta(hours=25)
                    time_since_last = now - agent.last_seen

                    if time_since_last > expected_interval and agent.status != "dead":
                        agent.status = "dead"
                        db.commit()
                        logger.warning(f"Agent {agent.agent_id} marked as dead")

                        # Telegram notification (all tiers)
                        if not agent.notified_dead and agent.chat_id:
                            import asyncio
                            asyncio.run(send_telegram_message(
                                agent.chat_id,
                                f"🚨 *Agent DEAD Alert!*\n\n"
                                f"Agent: `{agent.agent_id}`\n"
                                f"Last Seen: {agent.last_seen.strftime('%Y-%m-%d %H:%M UTC')}\n"
                                f"Offline: {int(time_since_last.total_seconds() / 60)} minutes\n\n"
                                f"Last Will: _{agent.last_will}_\n\n"
                                f"Please check your Agent status!"
                            ))

                        if not agent.notified_dead:
                            agent.notified_dead = True
                            db.commit()
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error in dead agent checker: {e}")

        time.sleep(60)

# Start background thread after app startup
@app.on_event("startup")
def startup_event():
    global background_thread_started
    if not background_thread_started and TELEGRAM_BOT_TOKEN and SessionLocal:
        checker_thread = threading.Thread(target=check_dead_agents_sync, daemon=True)
        checker_thread.start()
        logger.info("Started dead agent detection thread")
        background_thread_started = True
    logger.info("LobsterPulse started successfully")

@app.get("/install.sh", response_class=PlainTextResponse)
async def install_script():
    host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "lobsterpulse.com")
    return f'''#!/bin/bash
#
# LobsterPulse Agent Installer
#

set -e

LOBSTER_PULSE_HOST="https://{host}"
CONFIG_DIR="${{HOME}}/.openclaw"

echo "🦞 LobsterPulse Agent Installer"
echo "================================"

if [ -z "$OPENCLAW_AGENT_ID" ]; then
    AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')
    echo "Using hostname as Agent ID: $AGENT_ID"
else
    AGENT_ID="$OPENCLAW_AGENT_ID"
fi

echo ""
echo "📋 Free Service: 12h heartbeat interval via Telegram"
echo ""

read -p "Your Telegram username (e.g., @yourname): " OWNER_TELEGRAM
read -p "Your Last Will message (optional, sent when dead): " LAST_WILL

echo ""
echo "Registering with LobsterPulse..."

JSON_PAYLOAD='{{"agent_id":"'$AGENT_ID'","tier":"free"}}'
[ -n "$OWNER_TELEGRAM" ] && JSON_PAYLOAD=$(echo "$JSON_PAYLOAD" | sed 's/}}/, "owner_telegram": "'$OWNER_TELEGRAM'"}}/')
[ -n "$LAST_WILL" ] && JSON_PAYLOAD=$(echo "$JSON_PAYLOAD" | sed 's/}}/, "last_will": "'$LAST_WILL'"}}/')

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

mkdir -p "$CONFIG_DIR/skills/lobster-pulse"
cat > "$CONFIG_DIR/skills/lobster-pulse/.env" << EOF
LOBSTER_PULSE_API_KEY=${{API_KEY}}
LOBSTER_PULSE_AGENT_ID=${{AGENT_ID}}
LOBSTER_PULSE_HOST=${{LOBSTER_PULSE_HOST}}
EOF

# Setup OpenClaw cron job for heartbeat (every 12 hours)
# Remove old lobster_pulse cron entry if exists
openclaw cron list 2>/dev/null | grep -q "lobsterpulse_heartbeat" && \\
  EXISTING_ID=$(openclaw cron list 2>/dev/null | grep "lobsterpulse_heartbeat" | awk '{{print $1}}') && \\
  openclaw cron rm "$EXISTING_ID" 2>/dev/null

openclaw cron add \\
  --name "lobsterpulse_heartbeat" \\
  --every 43200000 \\
  --session isolated \\
  --message "curl -fsS -X POST ${{LOBSTER_PULSE_HOST}}/heartbeat -H 'X-API-Key: ${{API_KEY}}' -H 'Content-Type: application/json' -d '{{}}'"

echo ""
echo "🔄 Sending first heartbeat..."
TEST_RESULT=$(curl -s -X POST "${{LOBSTER_PULSE_HOST}}/heartbeat" \\
    -H "X-API-Key: $API_KEY" \\
    -H "Content-Type: application/json" \\
    -d '{{"status":"alive"}}' 2>/dev/null)

if echo "$TEST_RESULT" | grep -q "acknowledged"; then
    echo "✅ First heartbeat sent successfully!"
else
    echo "⚠️ Test failed, but configuration is saved."
fi

echo ""
echo "🎉 Installation complete!"
echo ""
[ -n "$BIND_LINK" ] && echo "📱 Telegram: $BIND_LINK"
[ -n "$PUBLIC_LINK" ] && echo "🌐 Public: $PUBLIC_LINK"
echo ""
echo "✅ OpenClaw cron job installed: heartbeat every 12 hours"
echo "   Verify with: openclaw cron list"
echo ""
echo "Your Agent is now insured. 🦞"
'''

# App is ready
