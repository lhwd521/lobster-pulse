import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lobster_pulse.db")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Tier Configuration
TIERS = {
    "free": {
        "price_usd": 0,
        "interval_minutes": 240,  # 4 hours
        "notify": ["telegram"],
        "name": "Free"
    },
    "guard": {
        "price_usd": 1,
        "interval_minutes": 30,   # 30 minutes
        "notify": ["telegram", "email"],
        "name": "Guard",
        "stripe_price_id": os.getenv("STRIPE_PRICE_GUARD", "price_guard_placeholder")
    },
    "shield": {
        "price_usd": 5,
        "interval_minutes": 5,    # 5 minutes
        "notify": ["telegram", "email", "webhook"],
        "name": "Shield",
        "stripe_price_id": os.getenv("STRIPE_PRICE_SHIELD", "price_shield_placeholder")
    }
}

# Check configuration
CHECK_INTERVAL_SECONDS = 60  # Run death check every 60 seconds
DEAD_THRESHOLD_MULTIPLIER = 2.5  # Mark dead after 2.5x interval (e.g., 4h * 2.5 = 10h for free tier)
