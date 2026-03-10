import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request
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

# Pydantic models
class RegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64)
    owner_telegram: Optional[str] = None
    owner_email: Optional[str] = None
    last_will: Optional[str] = None
    tier: str = "free"

class HeartbeatRequest(BaseModel):
    status: str = "alive"

# In-memory storage for MVP
agents_db = {}

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

    tier_config = {
        "free": {"interval": 240, "price": 0},
        "guard": {"interval": 30, "price": 1},
        "shield": {"interval": 5, "price": 5}
    }.get(request.tier, {"interval": 240, "price": 0})

    agents_db[api_key] = {
        "id": request.agent_id,
        "api_key": api_key,
        "tier": request.tier,
        "interval": tier_config["interval"],
        "telegram": request.owner_telegram,
        "email": request.owner_email,
        "last_will": request.last_will or "Check server if I'm dead",
        "status": "unknown",
        "last_seen": None,
        "created_at": datetime.utcnow()
    }

    logger.info(f"Registered agent: {request.agent_id}")

    return {
        "agent_id": request.agent_id,
        "api_key": api_key,
        "tier": request.tier,
        "interval_minutes": tier_config["interval"],
        "message": "Registered successfully"
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
        "created_at": agent["created_at"].isoformat()
    }

@app.get("/tiers")
async def list_tiers():
    """List available tiers"""
    return {
        "free": {"price": 0, "interval_minutes": 240, "name": "Free"},
        "guard": {"price": 1, "interval_minutes": 30, "name": "Guard"},
        "shield": {"price": 5, "interval_minutes": 5, "name": "Shield"}
    }

@app.get("/install.sh", response_class=PlainTextResponse)
async def install_script():
    """One-line installer script for Agents"""
    host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "lobster-pulse-production.up.railway.app")
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
echo "Next steps:"
echo "1. Restart Gateway: openclaw gateway restart"
echo "2. Check status: curl -H 'X-API-Key: ${{API_KEY:0:10}}...' ${{LOBSTER_PULSE_HOST}}/status/${{AGENT_ID}}"
echo ""
echo "Your Agent is now insured. 🦞"
'''

@app.get("/docs", response_class=FileResponse)
async def docs():
    """API Documentation page"""
    return {"message": "API Documentation", "endpoints": ["/register", "/heartbeat", "/status/{id}", "/tiers"]}

logger.info("LobsterPulse loaded - ready to start")
