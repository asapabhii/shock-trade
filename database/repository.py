"""
Database Repository - Handles persistence of trades, positions, and events.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.models import TradeRecord, PositionRecord, GoalEventRecord, MetricsSnapshot
from core.models import Trade, Position, GoalEvent, TradingMetrics


class TradeRepository:
    """Repository for trade persistence."""
    
    @staticmethod
    async def save(session: AsyncSession, trade: Trade) -> None:
        """Save a trade to the database."""
        record = TradeRecord(
            id=trade.id,
            match_id=trade.match_id,
            match_name=trade.match_name,
            market_id=trade.market_id,
            exchange=trade.exchange,
            outcome=trade.outcome,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            size=trade.size,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            goal_event_id=trade.goal_event_id,
            reason=trade.reason
        )
        session.add(record)
        await session.commit()
        logger.debug(f"Saved trade {trade.id} to database")
    
    @staticmethod
    async def update(session: AsyncSession, trade: Trade) -> None:
        """Update an existing trade."""
        stmt = (
            update(TradeRecord)
            .where(TradeRecord.id == trade.id)
            .values(
                exit_price=trade.exit_price,
                exit_time=trade.exit_time,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct
            )
        )
        await session.execute(stmt)
        await session.commit()
    
    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        stmt = (
            select(TradeRecord)
            .order_by(desc(TradeRecord.entry_time))
            .limit(limit)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        return [
            Trade(
                id=r.id,
                match_id=r.match_id,
                match_name=r.match_name,
                market_id=r.market_id,
                exchange=r.exchange,
                outcome=r.outcome,
                entry_price=r.entry_price,
                exit_price=r.exit_price,
                size=r.size,
                pnl=r.pnl,
                pnl_pct=r.pnl_pct,
                entry_time=r.entry_time,
                exit_time=r.exit_time,
                goal_event_id=r.goal_event_id,
                reason=r.reason
            )
            for r in records
        ]
    
    @staticmethod
    async def get_by_match(session: AsyncSession, match_id: int) -> List[Trade]:
        """Get trades for a specific match."""
        stmt = (
            select(TradeRecord)
            .where(TradeRecord.match_id == match_id)
            .order_by(desc(TradeRecord.entry_time))
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        return [
            Trade(
                id=r.id,
                match_id=r.match_id,
                match_name=r.match_name,
                market_id=r.market_id,
                exchange=r.exchange,
                outcome=r.outcome,
                entry_price=r.entry_price,
                exit_price=r.exit_price,
                size=r.size,
                pnl=r.pnl,
                pnl_pct=r.pnl_pct,
                entry_time=r.entry_time,
                exit_time=r.exit_time,
                goal_event_id=r.goal_event_id,
                reason=r.reason
            )
            for r in records
        ]


class PositionRepository:
    """Repository for position persistence."""
    
    @staticmethod
    async def save(session: AsyncSession, position: Position) -> None:
        """Save a position to the database."""
        record = PositionRecord(
            id=position.id,
            match_id=position.match_id,
            market_id=position.market_id,
            exchange=position.exchange,
            outcome=position.outcome,
            size=position.size,
            entry_price=position.entry_price,
            current_price=position.current_price,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            status=position.status.value,
            opened_at=position.opened_at,
            closed_at=position.closed_at,
            entry_order_id=position.entry_order_id,
            exit_order_id=position.exit_order_id
        )
        session.add(record)
        await session.commit()
        logger.debug(f"Saved position {position.id} to database")
    
    @staticmethod
    async def update(session: AsyncSession, position: Position) -> None:
        """Update an existing position."""
        stmt = (
            update(PositionRecord)
            .where(PositionRecord.id == position.id)
            .values(
                current_price=position.current_price,
                unrealized_pnl=position.unrealized_pnl,
                realized_pnl=position.realized_pnl,
                status=position.status.value,
                closed_at=position.closed_at,
                exit_order_id=position.exit_order_id
            )
        )
        await session.execute(stmt)
        await session.commit()
    
    @staticmethod
    async def get_open(session: AsyncSession) -> List[Position]:
        """Get all open positions."""
        stmt = (
            select(PositionRecord)
            .where(PositionRecord.status == "open")
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        from core.models import PositionStatus
        return [
            Position(
                id=r.id,
                match_id=r.match_id,
                market_id=r.market_id,
                exchange=r.exchange,
                outcome=r.outcome,
                size=r.size,
                entry_price=r.entry_price,
                current_price=r.current_price,
                unrealized_pnl=r.unrealized_pnl,
                realized_pnl=r.realized_pnl,
                status=PositionStatus(r.status),
                opened_at=r.opened_at,
                closed_at=r.closed_at,
                entry_order_id=r.entry_order_id,
                exit_order_id=r.exit_order_id
            )
            for r in records
        ]


class GoalEventRepository:
    """Repository for goal event persistence."""
    
    @staticmethod
    async def save(session: AsyncSession, goal: GoalEvent, trade_generated: bool = False) -> None:
        """Save a goal event to the database."""
        record = GoalEventRecord(
            id=goal.id,
            match_id=goal.match_id,
            timestamp=goal.timestamp,
            minute=goal.minute,
            scoring_team_id=goal.scoring_team_id,
            scoring_team_name=goal.scoring_team_name,
            is_home_team=goal.is_home_team,
            home_score=goal.home_score,
            away_score=goal.away_score,
            player_name=goal.player_name,
            processed=True,
            trade_generated=trade_generated
        )
        session.add(record)
        await session.commit()
    
    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 50) -> List[GoalEvent]:
        """Get recent goal events."""
        stmt = (
            select(GoalEventRecord)
            .order_by(desc(GoalEventRecord.timestamp))
            .limit(limit)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        return [
            GoalEvent(
                id=r.id,
                match_id=r.match_id,
                timestamp=r.timestamp,
                minute=r.minute,
                scoring_team_id=r.scoring_team_id,
                scoring_team_name=r.scoring_team_name,
                is_home_team=r.is_home_team,
                home_score=r.home_score,
                away_score=r.away_score,
                player_name=r.player_name
            )
            for r in records
        ]


class MetricsRepository:
    """Repository for metrics snapshots."""
    
    @staticmethod
    async def save_snapshot(session: AsyncSession, metrics: TradingMetrics) -> None:
        """Save a metrics snapshot."""
        record = MetricsSnapshot(
            timestamp=datetime.utcnow(),
            total_trades=metrics.total_trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            win_rate=metrics.win_rate,
            total_pnl=metrics.total_pnl,
            daily_pnl=metrics.daily_pnl,
            avg_latency_ms=metrics.avg_latency_ms,
            open_positions=metrics.open_positions,
            total_exposure=metrics.total_exposure
        )
        session.add(record)
        await session.commit()
    
    @staticmethod
    async def get_history(session: AsyncSession, hours: int = 24) -> List[dict]:
        """Get metrics history for charting."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        stmt = (
            select(MetricsSnapshot)
            .where(MetricsSnapshot.timestamp > cutoff)
            .order_by(MetricsSnapshot.timestamp)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "total_pnl": r.total_pnl,
                "daily_pnl": r.daily_pnl,
                "total_trades": r.total_trades,
                "win_rate": r.win_rate
            }
            for r in records
        ]
