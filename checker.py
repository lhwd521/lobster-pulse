import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_

from models import Agent, DeathEvent, get_db, SessionLocal
from notifier import notify_agent_death, notify_agent_recovery
from config import CHECK_INTERVAL_SECONDS, DEAD_THRESHOLD_MULTIPLIER, TIERS

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def get_dead_threshold_minutes(tier: str) -> int:
    """Calculate dead threshold based on tier interval"""
    interval = TIERS.get(tier, TIERS["free"])["interval_minutes"]
    return int(interval * DEAD_THRESHOLD_MULTIPLIER)

async def check_dead_agents():
    """Check for agents that haven't sent heartbeat in threshold time"""

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # Find agents that should be checked
        agents = db.query(Agent).filter(
            and_(
                Agent.status.in_(["alive", "unknown"]),
                Agent.next_check_at <= now
            )
        ).all()

        for agent in agents:
            threshold_minutes = get_dead_threshold_minutes(agent.tier)
            threshold_time = now - timedelta(minutes=threshold_minutes)

            # Check if agent is dead
            if not agent.last_seen or agent.last_seen < threshold_time:
                # Agent is dead
                if agent.status != "dead":
                    agent.status = "dead"
                    agent.death_count += 1

                    # Create death event
                    death_event = DeathEvent(
                        agent_id=agent.id,
                        last_seen=agent.last_seen,
                        notified="pending"
                    )
                    db.add(death_event)

                    # Send notification
                    await notify_agent_death(agent)

                    logger.warning(f"Agent {agent.id} marked as DEAD")
            else:
                # Agent is alive, update next check
                agent.status = "alive"
                interval_minutes = TIERS.get(agent.tier, TIERS["free"])["interval_minutes"]
                agent.next_check_at = now + timedelta(minutes=interval_minutes)

            agent.last_check = now

        db.commit()

    except Exception as e:
        logger.error(f"Error in check_dead_agents: {e}")
        db.rollback()
    finally:
        db.close()

async def check_recovered_agents():
    """Check for agents that recovered from dead state"""

    db = SessionLocal()
    try:
        # Find dead agents that have sent recent heartbeat
        dead_agents = db.query(Agent).filter(Agent.status == "dead").all()

        for agent in dead_agents:
            if agent.last_seen:
                threshold_minutes = get_dead_threshold_minutes(agent.tier)
                threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)

                if agent.last_seen > threshold_time:
                    # Agent has recovered
                    agent.status = "alive"

                    # Update death event
                    death_event = db.query(DeathEvent).filter(
                        DeathEvent.agent_id == agent.id,
                        DeathEvent.recovered_at.is_(None)
                    ).order_by(DeathEvent.detected_at.desc()).first()

                    if death_event:
                        death_event.recovered_at = datetime.utcnow()

                    # Send recovery notification
                    await notify_agent_recovery(agent)

                    logger.info(f"Agent {agent.id} recovered")

        db.commit()

    except Exception as e:
        logger.error(f"Error in check_recovered_agents: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    """Start the background scheduler"""

    # Add death check job
    scheduler.add_job(
        check_dead_agents,
        IntervalTrigger(seconds=CHECK_INTERVAL_SECONDS),
        id="check_dead_agents",
        replace_existing=True
    )

    # Add recovery check job
    scheduler.add_job(
        check_recovered_agents,
        IntervalTrigger(seconds=CHECK_INTERVAL_SECONDS),
        id="check_recovered_agents",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started")

def shutdown_scheduler():
    """Shutdown the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler shutdown")
