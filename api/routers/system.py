"""
System API router - Bot control and system status.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from services.goal_listener import goal_listener
from services.trade_service import trade_service
from services.nfl_score_listener import nfl_score_listener
from services.nfl_trade_service import nfl_trade_service
from exchanges.kalshi_client import kalshi_client
from data_providers.live_scores import live_scores_provider
from data_providers.nfl_scores import nfl_scores_provider
from core.state import state_manager

router = APIRouter()


class SystemStatus(BaseModel):
    """System status response."""
    # Legacy soccer
    goal_listener_running: bool
    # NFL
    nfl_listener_running: bool
    trading_enabled: bool
    kalshi_connected: bool
    live_matches_count: int  # Soccer
    live_nfl_games_count: int  # NFL
    open_positions_count: int
    uptime_seconds: float
    mode: str  # "nfl" or "soccer"


# Track startup time
_startup_time = datetime.utcnow()
_current_mode = "nfl"  # Default to NFL


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get overall system status."""
    return SystemStatus(
        goal_listener_running=goal_listener.is_running(),
        nfl_listener_running=nfl_score_listener.is_running(),
        trading_enabled=nfl_trade_service.is_enabled() if _current_mode == "nfl" else trade_service.is_enabled(),
        kalshi_connected=kalshi_client._authenticated,
        live_matches_count=len(state_manager.get_live_matches()),
        live_nfl_games_count=len(state_manager.get_live_nfl_games()),
        open_positions_count=len(state_manager.get_open_positions()),
        uptime_seconds=(datetime.utcnow() - _startup_time).total_seconds(),
        mode=_current_mode
    )


@router.post("/bot/start")
async def start_bot(mode: str = "nfl"):
    """Start the trading bot. Mode can be 'nfl' or 'soccer'."""
    global _current_mode
    _current_mode = mode
    
    # Login to Kalshi first
    kalshi_success = await kalshi_client.login()
    
    if mode == "nfl":
        if nfl_score_listener.is_running():
            return {"status": "already_running", "mode": "nfl"}
        
        # Register NFL trade service callback
        nfl_score_listener.on_score(nfl_trade_service.process_scoring_event)
        
        # Start listening
        await nfl_score_listener.start()
        
        return {
            "status": "started",
            "mode": "nfl",
            "kalshi_connected": kalshi_success
        }
    else:
        if goal_listener.is_running():
            return {"status": "already_running", "mode": "soccer"}
        
        # Register soccer trade service callback
        goal_listener.on_goal(trade_service.process_goal)
        
        # Start listening
        await goal_listener.start()
        
        return {
            "status": "started",
            "mode": "soccer",
            "kalshi_connected": kalshi_success
        }


@router.post("/bot/stop")
async def stop_bot():
    """Stop the trading bot (both modes)."""
    stopped = []
    
    if nfl_score_listener.is_running():
        await nfl_score_listener.stop()
        stopped.append("nfl")
    
    if goal_listener.is_running():
        await goal_listener.stop()
        stopped.append("soccer")
    
    if not stopped:
        return {"status": "already_stopped"}
    
    return {"status": "stopped", "modes": stopped}


@router.post("/kalshi/login")
async def kalshi_login():
    """Login to Kalshi API."""
    success = await kalshi_client.login()
    
    if success:
        return {"status": "success", "message": "Logged into Kalshi"}
    else:
        return {"status": "error", "message": "Failed to login to Kalshi"}


@router.get("/kalshi/balance")
async def get_kalshi_balance():
    """Get Kalshi account balance."""
    balance = await kalshi_client.get_balance()
    
    if balance:
        return {"status": "success", "balance": balance}
    else:
        return {"status": "error", "message": "Failed to fetch balance"}


@router.get("/kalshi/markets")
async def get_kalshi_markets(limit: int = 20):
    """Get available Kalshi markets."""
    markets = await kalshi_client.get_markets(limit=limit)
    
    return {
        "count": len(markets),
        "markets": [
            {
                "id": m.id,
                "title": m.title,
                "yes_price": m.yes_price,
                "no_price": m.no_price,
                "status": m.status
            }
            for m in markets
        ]
    }


@router.post("/refresh/matches")
async def refresh_matches():
    """Manually refresh live soccer matches."""
    matches = await live_scores_provider.get_live_matches()
    state_manager.update_matches(matches)
    
    return {
        "status": "success",
        "matches_count": len(matches)
    }


@router.post("/refresh/nfl")
async def refresh_nfl_games():
    """Manually refresh NFL games."""
    games = await nfl_scores_provider.get_live_games()
    state_manager.update_nfl_games(games)
    
    return {
        "status": "success",
        "games_count": len(games),
        "live_count": len([g for g in games if g.is_live])
    }


@router.post("/refresh/markets")
async def refresh_markets():
    """Manually refresh market cache (both soccer and NFL)."""
    from core.mapper import market_mapper
    from core.nfl_mapper import nfl_market_mapper
    
    await market_mapper.refresh_market_cache()
    await nfl_market_mapper.refresh_market_cache()
    
    return {"status": "success"}


@router.post("/state/reset")
async def reset_state():
    """Reset application state (for testing)."""
    state_manager.reset()
    return {"status": "success", "message": "State reset"}


@router.get("/logs")
async def get_recent_logs(limit: int = 50):
    """Get recent log entries (placeholder - would need log capture)."""
    # In a real implementation, you'd capture logs to a buffer
    return {
        "message": "Log capture not implemented - check console output",
        "hint": "Run with LOG_LEVEL=DEBUG for verbose logging"
    }



