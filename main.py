import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
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

@app.get("/")
async def root():
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

logger.info("LobsterPulse loaded - ready to start")
