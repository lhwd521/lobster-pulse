from sqlalchemy import create_engine, Column, String, DateTime, Integer, Float, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    api_key = Column(String, unique=True, index=True)

    # Contact info
    owner_telegram = Column(String, nullable=True)
    owner_email = Column(String, nullable=True)
    owner_webhook = Column(String, nullable=True)

    # Tier & config
    tier = Column(String, default="free")
    interval_minutes = Column(Integer, default=240)

    # Status
    status = Column(String, default="unknown")  # alive, dead, unknown, retired
    last_seen = Column(DateTime, nullable=True)
    last_check = Column(DateTime, nullable=True)
    next_check_at = Column(DateTime, index=True)

    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    retired_at = Column(DateTime, nullable=True)
    last_will = Column(Text, nullable=True)

    # Payment
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    paid_until = Column(DateTime, nullable=True)

    # Stats
    total_heartbeats = Column(Integer, default=0)
    death_count = Column(Integer, default=0)

class CheckLog(Base):
    __tablename__ = "check_logs"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String, index=True)
    received_at = Column(DateTime, server_default=func.now())
    response_time_ms = Column(Float, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

class DeathEvent(Base):
    __tablename__ = "death_events"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String, index=True)
    detected_at = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime)
    notified = Column(String, default="pending")  # pending, sent, failed
    recovered_at = Column(DateTime, nullable=True)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
