"""
Metrics API router - Trading metrics and statistics.
"""
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timedelta

from core.state import state_manager
from core.risk_manager import risk_manager
from services.monitoring import monitoring_service, MonitoringStats

router = APIRouter()


class MetricsResponse(BaseModel):
    """Trading metrics response."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    daily_pnl: float
    avg_pnl_per_trade: float
    avg_latency_ms: float
    max_latency_ms: float
    avg_slippage: float
    open_positions: int
    total_exposure: float


class RiskStatusResponse(BaseModel):
    """Risk status response."""
    daily_pnl: float
    daily_loss_limit: float
    daily_loss_remaining: float
    current_exposure: float
    max_exposure: float
    consecutive_errors: int
    circuit_breaker_active: bool
    last_error: str | None


class EquityPoint(BaseModel):
    """Point on equity curve."""
    timestamp: datetime
    equity: float
    pnl: float


@router.get("/", response_model=MetricsResponse)
async def get_metrics():
    """Get current trading metrics."""
    metrics = state_manager.get_metrics()
    
    return MetricsResponse(
        total_trades=metrics.total_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        win_rate=metrics.win_rate,
        total_pnl=metrics.total_pnl,
        daily_pnl=metrics.daily_pnl,
        avg_pnl_per_trade=metrics.avg_pnl_per_trade,
        avg_latency_ms=metrics.avg_latency_ms,
        max_latency_ms=metrics.max_latency_ms,
        avg_slippage=metrics.avg_slippage,
        open_positions=metrics.open_positions,
        total_exposure=metrics.total_exposure
    )


@router.get("/risk", response_model=RiskStatusResponse)
async def get_risk_status():
    """Get current risk management status."""
    status = risk_manager.get_status()
    
    return RiskStatusResponse(
        daily_pnl=status.daily_pnl,
        daily_loss_limit=status.daily_loss_limit,
        daily_loss_remaining=status.daily_loss_remaining,
        current_exposure=status.current_exposure,
        max_exposure=status.max_exposure,
        consecutive_errors=status.consecutive_errors,
        circuit_breaker_active=status.circuit_breaker_active,
        last_error=status.last_error
    )


@router.get("/equity", response_model=List[EquityPoint])
async def get_equity_curve():
    """Get equity curve data for charting."""
    trades = state_manager.get_trades(100)
    
    if not trades:
        return []
    
    # Build cumulative equity curve
    from config import settings
    equity = settings.bankroll
    points = []
    
    for trade in trades:
        if trade.exit_time:
            equity += trade.pnl
            points.append(EquityPoint(
                timestamp=trade.exit_time,
                equity=equity,
                pnl=trade.pnl
            ))
    
    return points


@router.get("/summary")
async def get_summary():
    """Get a summary of all key metrics."""
    metrics = state_manager.get_metrics()
    risk_status = risk_manager.get_status()
    positions = state_manager.get_open_positions()
    trades = state_manager.get_trades(10)
    
    return {
        "metrics": {
            "total_trades": metrics.total_trades,
            "win_rate": f"{metrics.win_rate * 100:.1f}%",
            "total_pnl": f"${metrics.total_pnl:.2f}",
            "daily_pnl": f"${metrics.daily_pnl:.2f}",
            "avg_latency": f"{metrics.avg_latency_ms:.0f}ms"
        },
        "risk": {
            "circuit_breaker": risk_status.circuit_breaker_active,
            "daily_remaining": f"${risk_status.daily_loss_remaining:.2f}",
            "exposure": f"${risk_status.current_exposure:.2f}"
        },
        "positions": {
            "open": len(positions),
            "total_unrealized": sum(p.unrealized_pnl for p in positions)
        },
        "recent_trades": len(trades)
    }


class MonitoringResponse(BaseModel):
    """Monitoring statistics response."""
    avg_event_to_order_ms: float
    max_event_to_order_ms: float
    min_event_to_order_ms: float
    p95_event_to_order_ms: float
    avg_event_to_fill_ms: float
    max_event_to_fill_ms: float
    avg_slippage_bps: float
    max_slippage_bps: float
    total_orders: int
    filled_orders: int
    rejected_orders: int
    fill_rate: float
    total_errors: int
    errors_last_hour: int
    is_healthy: bool
    health_issues: List[str]


@router.get("/monitoring", response_model=MonitoringResponse)
async def get_monitoring_stats():
    """Get detailed monitoring statistics."""
    stats = monitoring_service.get_stats()
    
    return MonitoringResponse(
        avg_event_to_order_ms=stats.avg_event_to_order_ms,
        max_event_to_order_ms=stats.max_event_to_order_ms,
        min_event_to_order_ms=stats.min_event_to_order_ms,
        p95_event_to_order_ms=stats.p95_event_to_order_ms,
        avg_event_to_fill_ms=stats.avg_event_to_fill_ms,
        max_event_to_fill_ms=stats.max_event_to_fill_ms,
        avg_slippage_bps=stats.avg_slippage_bps,
        max_slippage_bps=stats.max_slippage_bps,
        total_orders=stats.total_orders,
        filled_orders=stats.filled_orders,
        rejected_orders=stats.rejected_orders,
        fill_rate=stats.fill_rate,
        total_errors=stats.total_errors,
        errors_last_hour=stats.errors_last_hour,
        is_healthy=stats.is_healthy,
        health_issues=stats.health_issues
    )


@router.get("/health")
async def get_health():
    """Get system health status."""
    stats = monitoring_service.get_stats()
    risk_status = risk_manager.get_status()
    
    issues = list(stats.health_issues)
    
    if risk_status.circuit_breaker_active:
        issues.append("Circuit breaker is active")
    
    if risk_status.daily_loss_remaining <= 0:
        issues.append("Daily loss limit reached")
    
    return {
        "healthy": stats.is_healthy and not risk_status.circuit_breaker_active,
        "issues": issues,
        "monitoring": {
            "latency_ok": stats.avg_event_to_order_ms < 5000,
            "fill_rate_ok": stats.fill_rate >= 0.8 or stats.total_orders < 10,
            "errors_ok": stats.errors_last_hour < 10
        },
        "risk": {
            "circuit_breaker": risk_status.circuit_breaker_active,
            "daily_limit_ok": risk_status.daily_loss_remaining > 0
        }
    }
