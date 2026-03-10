import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from models import Agent, CheckLog, DeathEvent, init_db, get_db, SessionLocal
from config import TIERS
from checker import start_scheduler, shutdown_scheduler
from notifier import send_welcome_message

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LobsterPulse",
    description="Agent Life Insurance - Monitor your OpenClaw Agent's heartbeat",
    version="1.0.0"
)

# Startup/shutdown events
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        # Continue even if DB fails - health check will still work

    try:
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")

    logger.info("LobsterPulse started")

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_scheduler()
    logger.info("LobsterPulse shutdown")

# Pydantic models
class RegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    owner_telegram: Optional[str] = Field(None, max_length=64)
    owner_email: Optional[str] = Field(None, max_length=128)
    last_will: Optional[str] = Field(None, max_length=500)
    tier: str = Field(default="free", pattern=r"^(free|guard|shield)$")

class HeartbeatRequest(BaseModel):
    timestamp: Optional[str] = None
    status: str = Field(default="alive", pattern=r"^(alive|error|busy)$")

class UpgradeRequest(BaseModel):
    tier: str = Field(..., pattern=r"^(guard|shield)$")

# Helper functions
def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"lp_{secrets.token_urlsafe(32)}"

def get_tier_config(tier: str):
    """Get tier configuration"""
    return TIERS.get(tier, TIERS["free"])

# API Endpoints
@app.get("/")
async def root():
    return {
        "service": "LobsterPulse",
        "version": "1.0.0",
        "description": "Agent Life Insurance",
        "tiers": list(TIERS.keys()),
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/register")
async def register(
    request: RegisterRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """Register a new agent for monitoring"""

    # Check if agent already exists
    existing = db.query(Agent).filter(Agent.id == request.agent_id).first()
    if existing:
        raise HTTPException(400, "Agent already registered")

    # Get tier config
    tier_config = get_tier_config(request.tier)

    # Calculate next check time
    interval_minutes = tier_config["interval_minutes"]
    next_check = datetime.utcnow() + timedelta(minutes=interval_minutes)

    # Create agent
    api_key = generate_api_key()
    agent = Agent(
        id=request.agent_id,
        api_key=api_key,
        owner_telegram=request.owner_telegram,
        owner_email=request.owner_email,
        tier=request.tier,
        interval_minutes=interval_minutes,
        last_will=request.last_will or "If I'm dead, please check the server.",
        status="unknown",
        next_check_at=next_check
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    # Send welcome notification
    try:
        await send_welcome_message(agent)
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")

    logger.info(f"New agent registered: {request.agent_id} ({request.tier})")

    return {
        "agent_id": agent.id,
        "api_key": api_key,
        "tier": agent.tier,
        "interval_minutes": agent.interval_minutes,
        "next_check_at": next_check.isoformat(),
        "message": f"Registered successfully. Please configure heartbeat to send every {interval_minutes} minutes."
    }

@app.post("/heartbeat")
async def heartbeat(
    request: HeartbeatRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    req: Request,
    db: Session = Depends(get_db)
):
    """Receive heartbeat from agent"""

    # Find agent by API key
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        raise HTTPException(401, "Invalid API key")

    # Check if agent was retired
    if agent.status == "retired":
        raise HTTPException(403, "Agent has been retired")

    now = datetime.utcnow()

    # Update agent status
    was_dead = agent.status == "dead"
    agent.status = "alive"
    agent.last_seen = now
    agent.total_heartbeats += 1

    # Update next check time
    interval_minutes = get_tier_config(agent.tier)["interval_minutes"]
    agent.next_check_at = now + timedelta(minutes=interval_minutes)

    # Log the check
    check_log = CheckLog(
        agent_id=agent.id,
        ip_address=req.client.host,
        user_agent=req.headers.get("user-agent", "unknown")
    )
    db.add(check_log)

    db.commit()

    # If agent recovered from dead state, notify
    if was_dead:
        from notifier import notify_agent_recovery
        try:
            await notify_agent_recovery(agent)
        except Exception as e:
            logger.error(f"Failed to send recovery notification: {e}")

    return {
        "status": "acknowledged",
        "agent_id": agent.id,
        "tier": agent.tier,
        "next_expected_heartbeat": agent.next_check_at.isoformat(),
        "message": "Heartbeat received"
    }

@app.get("/status/{agent_id}")
async def get_status(
    agent_id: str,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """Get agent status"""

    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.api_key == x_api_key
    ).first()

    if not agent:
        raise HTTPException(404, "Agent not found or invalid API key")

    threshold_minutes = agent.interval_minutes * 2.5

    return {
        "agent_id": agent.id,
        "status": agent.status,
        "tier": agent.tier,
        "interval_minutes": agent.interval_minutes,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "last_check": agent.last_check.isoformat() if agent.last_check else None,
        "next_check_at": agent.next_check_at.isoformat() if agent.next_check_at else None,
        "total_heartbeats": agent.total_heartbeats,
        "death_count": agent.death_count,
        "dead_threshold_minutes": threshold_minutes,
        "created_at": agent.created_at.isoformat()
    }

@app.post("/upgrade")
async def upgrade(
    request: UpgradeRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """Upgrade agent tier (creates Stripe checkout session)"""

    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        raise HTTPException(401, "Invalid API key")

    tier_config = get_tier_config(request.tier)

    # For MVP, just update the tier without payment
    # TODO: Integrate Stripe for real payments
    agent.tier = request.tier
    agent.interval_minutes = tier_config["interval_minutes"]
    agent.next_check_at = datetime.utcnow() + timedelta(minutes=agent.interval_minutes)

    db.commit()

    logger.info(f"Agent {agent.id} upgraded to {request.tier}")

    return {
        "agent_id": agent.id,
        "tier": agent.tier,
        "interval_minutes": agent.interval_minutes,
        "price_usd": tier_config["price_usd"],
        "message": f"Upgraded to {request.tier.upper()}. Payment integration coming soon."
    }

@app.post("/retire")
async def retire(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """Retire an agent (stop monitoring)"""

    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        raise HTTPException(401, "Invalid API key")

    agent.status = "retired"
    agent.retired_at = datetime.utcnow()
    db.commit()

    logger.info(f"Agent {agent.id} retired")

    return {
        "agent_id": agent.id,
        "status": "retired",
        "message": "Agent retired successfully. Monitoring stopped."
    }

@app.get("/tiers")
async def list_tiers():
    """List available tiers"""
    return {
        tier_name: {
            "name": config["name"],
            "price_usd": config["price_usd"],
            "interval_minutes": config["interval_minutes"],
            "interval_hours": config["interval_minutes"] / 60,
            "notify_channels": config["notify"]
        }
        for tier_name, config in TIERS.items()
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# For Railway deployment - import uvicorn at module level
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
