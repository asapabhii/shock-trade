"""
Trades API router - Trade history and management.
"""
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from core.state import state_manager
from core.order_executor import order_executor

router = APIRouter()


class TradeResponse(BaseModel):
    """Trade response model."""
    id: str
    match_id: int
    match_name: str
    market_id: str
    exchange: str
    outcome: str
    entry_price: float
    exit_price: Optional[float]
    size: float
    pnl: float
    pnl_pct: float
    entry_time: datetime
    exit_time: Optional[datetime]
    status: str
    reason: str


class OrderResponse(BaseModel):
    """Order response model."""
    id: str
    exchange_order_id: Optional[str]
    market_id: str
    side: str
    outcome: str
    size: float
    limit_price: float
    filled_size: float
    status: str
    submitted_at: Optional[datetime]


@router.get("/", response_model=List[TradeResponse])
async def get_trades(limit: int = 50):
    """Get recent trades."""
    trades = state_manager.get_trades(limit)
    
    return [
        TradeResponse(
            id=t.id,
            match_id=t.match_id,
            match_name=t.match_name,
            market_id=t.market_id,
            exchange=t.exchange,
            outcome=t.outcome,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            size=t.size,
            pnl=t.pnl,
            pnl_pct=t.pnl_pct,
            entry_time=t.entry_time,
            exit_time=t.exit_time,
            status="closed" if t.exit_time else "open",
            reason=t.reason
        )
        for t in reversed(trades)  # Most recent first
    ]


@router.get("/orders/pending", response_model=List[OrderResponse])
async def get_pending_orders():
    """Get pending orders."""
    orders = order_executor.get_pending_orders()
    
    return [
        OrderResponse(
            id=o.id,
            exchange_order_id=o.exchange_order_id,
            market_id=o.market_id,
            side=o.side.value,
            outcome=o.outcome,
            size=o.size,
            limit_price=o.limit_price,
            filled_size=o.filled_size,
            status=o.status.value,
            submitted_at=o.submitted_at
        )
        for o in orders
    ]


@router.get("/orders/completed", response_model=List[OrderResponse])
async def get_completed_orders(limit: int = 50):
    """Get completed orders."""
    orders = order_executor.get_completed_orders(limit)
    
    return [
        OrderResponse(
            id=o.id,
            exchange_order_id=o.exchange_order_id,
            market_id=o.market_id,
            side=o.side.value,
            outcome=o.outcome,
            size=o.size,
            limit_price=o.limit_price,
            filled_size=o.filled_size,
            status=o.status.value,
            submitted_at=o.submitted_at
        )
        for o in reversed(orders)
    ]


@router.get("/match/{match_id}", response_model=List[TradeResponse])
async def get_trades_for_match(match_id: int):
    """Get all trades for a specific match."""
    trades = state_manager.get_trades_for_match(match_id)
    
    return [
        TradeResponse(
            id=t.id,
            match_id=t.match_id,
            match_name=t.match_name,
            market_id=t.market_id,
            exchange=t.exchange,
            outcome=t.outcome,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            size=t.size,
            pnl=t.pnl,
            pnl_pct=t.pnl_pct,
            entry_time=t.entry_time,
            exit_time=t.exit_time,
            status="closed" if t.exit_time else "open",
            reason=t.reason
        )
        for t in trades
    ]
