"""
SQLAlchemy database models for persistence.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TradeRecord(Base):
    """Persisted trade record."""
    __tablename__ = "trades"
    
    id = Column(String, primary_key=True)
    match_id = Column(Integer, index=True)
    match_name = Column(String)
    market_id = Column(String)
    exchange = Column(String)
    outcome = Column(String)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    size = Column(Float)
    pnl = Column(Float, default=0)
    pnl_pct = Column(Float, default=0)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    goal_event_id = Column(String)
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class PositionRecord(Base):
    """Persisted position record."""
    __tablename__ = "positions"
    
    id = Column(String, primary_key=True)
    match_id = Column(Integer, index=True)
    market_id = Column(String)
    exchange = Column(String)
    outcome = Column(String)
    size = Column(Float)
    entry_price = Column(Float)
    current_price = Column(Float)
    unrealized_pnl = Column(Float, default=0)
    realized_pnl = Column(Float, default=0)
    status = Column(String, default="open")
    opened_at = Column(DateTime)
    closed_at = Column(DateTime, nullable=True)
    entry_order_id = Column(String)
    exit_order_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GoalEventRecord(Base):
    """Persisted goal event record."""
    __tablename__ = "goal_events"
    
    id = Column(String, primary_key=True)
    match_id = Column(Integer, index=True)
    timestamp = Column(DateTime)
    minute = Column(Integer)
    scoring_team_id = Column(Integer)
    scoring_team_name = Column(String)
    is_home_team = Column(Boolean)
    home_score = Column(Integer)
    away_score = Column(Integer)
    player_name = Column(String, nullable=True)
    processed = Column(Boolean, default=False)
    trade_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConfigRecord(Base):
    """Persisted configuration."""
    __tablename__ = "config"
    
    key = Column(String, primary_key=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)


class MetricsSnapshot(Base):
    """Periodic metrics snapshots for historical tracking."""
    __tablename__ = "metrics_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0)
    total_pnl = Column(Float, default=0)
    daily_pnl = Column(Float, default=0)
    avg_latency_ms = Column(Float, default=0)
    open_positions = Column(Integer, default=0)
    total_exposure = Column(Float, default=0)
