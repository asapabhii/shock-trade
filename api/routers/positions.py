"""
Positions API router - Open position management.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from core.state import state_manager
from services.trade_service import trade_service

router = APIRouter()


class PositionResponse(BaseModel):
    """Position response model."""
    id: str
    match_id: int
    market_id: str
    exchange: str
    outcome: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    status: str
    opened_at: datetime
    time_open_mins: float


@router.get("/", response_model=List[PositionResponse])
async def get_open_positions():
    """Get all open positions."""
    positions = state_manager.get_open_positions()
    now = datetime.utcnow()
    
    return [
        PositionResponse(
            id=p.id,
            match_id=p.match_id,
            market_id=p.market_id,
            exchange=p.exchange,
            outcome=p.outcome,
            size=p.size,
            entry_price=p.entry_price,
            current_price=p.current_price,
            unrealized_pnl=p.unrealized_pnl,
            unrealized_pnl_pct=(
                (p.current_price - p.entry_price) / p.entry_price * 100
                if p.entry_price > 0 else 0
            ),
            status=p.status.value,
            opened_at=p.opened_at,
            time_open_mins=(now - p.opened_at).total_seconds() / 60
        )
        for p in positions
    ]


@router.post("/{position_id}/close")
async def close_position(position_id: str, reason: str = "manual"):
    """Manually close a position."""
    position = state_manager.get_position(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    closed = await trade_service.close_position(position_id, reason)
    
    if closed:
        return {
            "status": "success",
            "position_id": position_id,
            "realized_pnl": closed.realized_pnl
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to close position")


@router.get("/{position_id}")
async def get_position(position_id: str):
    """Get a specific position."""
    position = state_manager.get_position(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    now = datetime.utcnow()
    
    return PositionResponse(
        id=position.id,
        match_id=position.match_id,
        market_id=position.market_id,
        exchange=position.exchange,
        outcome=position.outcome,
        size=position.size,
        entry_price=position.entry_price,
        current_price=position.current_price,
        unrealized_pnl=position.unrealized_pnl,
        unrealized_pnl_pct=(
            (position.current_price - position.entry_price) / position.entry_price * 100
            if position.entry_price > 0 else 0
        ),
        status=position.status.value,
        opened_at=position.opened_at,
        time_open_mins=(now - position.opened_at).total_seconds() / 60
    )
