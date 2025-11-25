"""
NFL Trade Service - Orchestrates the complete NFL trading pipeline.

Coordinates:
1. Scoring event reception
2. Market mapping
3. Decision engine evaluation
4. Risk management approval
5. Order execution
6. Position tracking
"""
import uuid
from datetime import datetime
from typing import Optional
from loguru import logger

from config import settings
from core.models import (
    NFLScoringEvent, NFLGame, OrderIntent, Order, Position, Trade,
    PositionStatus, OrderStatus
)
from core.nfl_mapper import nfl_market_mapper
from core.nfl_decision_engine import nfl_decision_engine
from core.risk_manager import risk_manager
from core.order_executor import order_executor
from core.state import state_manager
from services.monitoring import monitoring_service


class NFLTradeService:
    """
    Main NFL trading service that orchestrates the entire flow.
    
    Pipeline:
    Scoring Event -> Market Lookup -> Decision -> Risk Check -> Execute -> Track
    """
    
    def __init__(self):
        self._enabled = True
    
    def enable(self) -> None:
        """Enable trading."""
        self._enabled = True
        logger.info("NFL Trading enabled")
    
    def disable(self) -> None:
        """Disable trading (will still process but not execute)."""
        self._enabled = False
        logger.info("NFL Trading disabled")
    
    def is_enabled(self) -> bool:
        """Check if trading is enabled."""
        return self._enabled
    
    async def process_scoring_event(
        self,
        event: NFLScoringEvent,
        game: NFLGame
    ) -> Optional[Trade]:
        """
        Process a scoring event through the complete trading pipeline.
        
        Args:
            event: The detected scoring event.
            game: Current game state.
            
        Returns:
            Trade object if a trade was executed, None otherwise.
        """
        pipeline_start = datetime.utcnow()
        logger.info(f"Processing NFL score: {event.id}")
        
        # Record scoring event for monitoring
        monitoring_service.record_goal_event(event.id, event.timestamp)
        
        try:
            # Step 1: Get or create market mapping
            mapping = state_manager.get_nfl_mapping(game.id)
            if not mapping:
                logger.info(f"Creating market mapping for game {game.id}")
                mapping = await nfl_market_mapper.create_mapping(game)
                state_manager.set_nfl_mapping(game.id, mapping)
            
            if not mapping.markets:
                logger.warning(f"No markets found for game {game.display_name}")
                return None
            
            # Step 2: Run decision engine
            intent = nfl_decision_engine.evaluate_scoring_event(event, game, mapping)
            
            if not intent:
                logger.info("Decision engine: No trade signal generated")
                return None
            
            logger.info(f"Decision engine generated intent: {intent.reason}")
            
            # Step 3: Risk management approval
            approved_intent, risk_reason = risk_manager.approve_trade(intent)
            
            if not approved_intent:
                logger.info(f"Risk manager rejected: {risk_reason}")
                return None
            
            logger.info(f"Risk manager approved: {risk_reason}")
            
            # Step 4: Execute order (if trading enabled)
            if not self._enabled:
                logger.info("Trading disabled - skipping execution")
                return None
            
            order, exec_message = await order_executor.execute(approved_intent)
            
            # Record order submission for monitoring
            monitoring_service.record_order_submitted(event.id, datetime.utcnow())
            
            if not order or order.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED):
                logger.warning(f"Order execution failed: {exec_message}")
                risk_manager.record_error(exec_message)
                monitoring_service.record_order_rejected(exec_message)
                return None
            
            risk_manager.record_success()
            
            # Record fill for monitoring
            if order.status == OrderStatus.FILLED:
                monitoring_service.record_order_filled(
                    event.id,
                    order.id,
                    datetime.utcnow(),
                    approved_intent.limit_price,
                    order.avg_fill_price or approved_intent.limit_price
                )
            
            # Step 5: Create position
            position = Position(
                id=str(uuid.uuid4()),
                match_id=game.id,
                market_id=order.market_id,
                exchange=order.exchange,
                outcome=order.outcome,
                size=order.size,
                entry_price=order.avg_fill_price or order.limit_price,
                current_price=order.avg_fill_price or order.limit_price,
                status=PositionStatus.OPEN,
                opened_at=datetime.utcnow(),
                entry_order_id=order.id
            )
            
            state_manager.add_position(position)
            risk_manager.add_position(position)
            
            # Step 6: Record trade
            trade = Trade(
                id=str(uuid.uuid4()),
                match_id=game.id,
                match_name=game.display_name,
                market_id=order.market_id,
                exchange=order.exchange,
                outcome=order.outcome,
                entry_price=position.entry_price,
                size=order.size,
                entry_time=datetime.utcnow(),
                goal_event_id=event.id,
                reason=approved_intent.reason
            )
            
            state_manager.add_trade(trade)
            
            # Record latency
            pipeline_end = datetime.utcnow()
            latency_ms = (pipeline_end - pipeline_start).total_seconds() * 1000
            state_manager.record_latency(latency_ms)
            
            logger.info(
                f"Trade executed: {trade.id} "
                f"({order.outcome} @ {position.entry_price:.2f}, "
                f"size: ${order.size:.2f}, latency: {latency_ms:.0f}ms)"
            )
            
            return trade
            
        except Exception as e:
            logger.error(f"Error processing NFL score {event.id}: {e}")
            risk_manager.record_error(str(e))
            return None
    
    async def close_position(
        self,
        position_id: str,
        reason: str = "manual"
    ) -> Optional[Position]:
        """
        Close an open position.
        
        Args:
            position_id: ID of position to close.
            reason: Reason for closing.
            
        Returns:
            Closed Position object or None.
        """
        position = state_manager.get_position(position_id)
        if not position:
            logger.warning(f"Position {position_id} not found")
            return None
        
        # Create sell order
        intent = OrderIntent(
            id=str(uuid.uuid4()),
            match_id=position.match_id,
            market_id=position.market_id,
            exchange=position.exchange,
            side="sell",
            outcome=position.outcome,
            size=position.size,
            limit_price=position.current_price - 0.02,
            reason=f"Close position: {reason}",
            goal_event_id=""
        )
        
        order, message = await order_executor.execute(intent)
        
        if order and order.status != OrderStatus.REJECTED:
            exit_price = order.avg_fill_price or position.current_price
            closed = state_manager.close_position(
                position_id,
                exit_price,
                order.id
            )
            
            if closed:
                # Update trade with exit info
                for trade in state_manager.get_trades():
                    if trade.match_id == position.match_id and trade.exit_time is None:
                        trade.exit_price = exit_price
                        trade.exit_time = datetime.utcnow()
                        trade.pnl = closed.realized_pnl
                        trade.pnl_pct = (
                            (exit_price - trade.entry_price) / trade.entry_price * 100
                            if trade.entry_price > 0 else 0
                        )
                        break
                
                # Record P/L
                risk_manager.record_trade_result(
                    position.match_id,
                    closed.realized_pnl,
                    -position.size
                )
                
                logger.info(
                    f"Position closed: {position_id} "
                    f"(P/L: ${closed.realized_pnl:.2f})"
                )
            
            return closed
        
        logger.warning(f"Failed to close position: {message}")
        return None


# Singleton instance
nfl_trade_service = NFLTradeService()
