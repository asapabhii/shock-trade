"""
Configuration API router - Runtime configuration management.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from config import settings
from core.risk_manager import risk_manager
from core.decision_engine import decision_engine
from services.trade_service import trade_service

router = APIRouter()


class TradingConfig(BaseModel):
    """Trading configuration model."""
    bankroll: float = Field(ge=0, description="Total demo bankroll")
    max_per_trade_pct: float = Field(ge=0, le=100, description="Max % of bankroll per trade")
    underdog_threshold: float = Field(ge=0, le=1, description="Probability threshold for underdog")
    daily_loss_limit: float = Field(ge=0, description="Max daily loss before stopping")
    per_match_max_exposure: float = Field(ge=0, description="Max exposure per match")
    take_profit_pct: float = Field(ge=0, le=1, description="Take profit percentage")
    stop_loss_pct: float = Field(ge=0, le=1, description="Stop loss percentage")


class ConfigUpdate(BaseModel):
    """Partial config update model."""
    bankroll: Optional[float] = None
    max_per_trade_pct: Optional[float] = None
    underdog_threshold: Optional[float] = None
    daily_loss_limit: Optional[float] = None
    per_match_max_exposure: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None


@router.get("/", response_model=TradingConfig)
async def get_config():
    """Get current trading configuration."""
    return TradingConfig(
        bankroll=risk_manager.bankroll,
        max_per_trade_pct=risk_manager.max_per_trade_pct * 100,
        underdog_threshold=decision_engine.underdog_threshold,
        daily_loss_limit=risk_manager.daily_loss_limit,
        per_match_max_exposure=risk_manager.per_match_max_exposure,
        take_profit_pct=settings.take_profit_pct,
        stop_loss_pct=settings.stop_loss_pct
    )


@router.patch("/")
async def update_config(update: ConfigUpdate):
    """Update trading configuration."""
    updated = {}
    
    if update.bankroll is not None:
        risk_manager.bankroll = update.bankroll
        updated["bankroll"] = update.bankroll
    
    if update.max_per_trade_pct is not None:
        risk_manager.max_per_trade_pct = update.max_per_trade_pct / 100
        updated["max_per_trade_pct"] = update.max_per_trade_pct
    
    if update.underdog_threshold is not None:
        decision_engine.underdog_threshold = update.underdog_threshold
        updated["underdog_threshold"] = update.underdog_threshold
    
    if update.daily_loss_limit is not None:
        risk_manager.daily_loss_limit = update.daily_loss_limit
        updated["daily_loss_limit"] = update.daily_loss_limit
    
    if update.per_match_max_exposure is not None:
        risk_manager.per_match_max_exposure = update.per_match_max_exposure
        updated["per_match_max_exposure"] = update.per_match_max_exposure
    
    return {
        "status": "success",
        "updated": updated
    }


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker():
    """Reset the circuit breaker."""
    risk_manager.reset_circuit_breaker()
    return {"status": "success", "message": "Circuit breaker reset"}


@router.post("/trading/enable")
async def enable_trading():
    """Enable trading."""
    trade_service.enable()
    return {"status": "success", "trading_enabled": True}


@router.post("/trading/disable")
async def disable_trading():
    """Disable trading."""
    trade_service.disable()
    return {"status": "success", "trading_enabled": False}


@router.get("/trading/status")
async def get_trading_status():
    """Get trading enabled status."""
    return {
        "trading_enabled": trade_service.is_enabled(),
        "circuit_breaker_active": risk_manager.get_status().circuit_breaker_active
    }
