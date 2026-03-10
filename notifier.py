import httpx
import logging
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN
from models import Agent, DeathEvent, get_db

logger = logging.getLogger(__name__)

async def send_telegram_notification(chat_id: str, message: str):
    """Send Telegram notification"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        return False

    # Handle @username format
    if chat_id.startswith("@"):
        chat_id = chat_id[1:]

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            })

            if response.status_code == 200:
                logger.info(f"Telegram notification sent to {chat_id}")
                return True
            else:
                logger.error(f"Telegram API error: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram: {e}")
        return False

async def notify_agent_death(agent: Agent):
    """Notify owner that agent is dead"""

    last_seen_str = agent.last_seen.strftime("%Y-%m-%d %H:%M UTC") if agent.last_seen else "Unknown"

    message = f"""🚨 <b>LobsterPulse Alert</b>

<b>Agent:</b> {agent.id}
<b>Status:</b> 💀 DEAD
<b>Last Seen:</b> {last_seen_str}
<b>Tier:</b> {agent.tier.upper()}

<i>Last Will:</i>
{agent.last_will or "No message left."}

Please check your server immediately.

---
<a href="https://lobsterpulse.com/dashboard">View Dashboard</a>
"""

    # Send Telegram notification
    if agent.owner_telegram:
        success = await send_telegram_notification(agent.owner_telegram, message)

        # Record notification status
        db = next(get_db())
        death_event = db.query(DeathEvent).filter(
            DeathEvent.agent_id == agent.id,
            DeathEvent.recovered_at.is_(None)
        ).order_by(DeathEvent.detected_at.desc()).first()

        if death_event:
            death_event.notified = "sent" if success else "failed"
            db.commit()

    # TODO: Email notification
    # TODO: Webhook notification for Shield tier

    logger.info(f"Death notification sent for agent {agent.id}")

async def notify_agent_recovery(agent: Agent):
    """Notify owner that agent has recovered"""

    message = f"""✅ <b>LobsterPulse Recovery</b>

<b>Agent:</b> {agent.id}
<b>Status:</b> 🟢 BACK ONLINE

Your agent has resumed sending heartbeats.

---
<a href="https://lobsterpulse.com/dashboard">View Dashboard</a>
"""

    if agent.owner_telegram:
        await send_telegram_notification(agent.owner_telegram, message)

    logger.info(f"Recovery notification sent for agent {agent.id}")

async def send_welcome_message(agent: Agent):
    """Send welcome message after registration"""

    interval_hours = agent.interval_minutes / 60

    message = f"""🦞 <b>Welcome to LobsterPulse!</b>

<b>Agent:</b> {agent.id}
<b>Tier:</b> {agent.tier.upper()}
<b>Heartbeat Interval:</b> Every {interval_hours:.1f} hours

Your agent is now being monitored.
You will receive a notification if it goes offline for more than {interval_hours * 2.5:.1f} hours.

---
<a href="https://lobsterpulse.com/dashboard">View Dashboard</a>
"""

    if agent.owner_telegram:
        await send_telegram_notification(agent.owner_telegram, message)
