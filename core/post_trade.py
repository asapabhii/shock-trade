"""
Post-Trade Manager - Handles position exits and P/L computation.

Implements:
- Take-profit logic
- Stop-loss logic  
- Time-based exits
- P/L calculation and tracking
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from loguru import logger

from config import settings
from core.models import Position, Trade, PositionStatus
from core.state import state_manager


class PostTradeManager:
    """
    Manages open positions after entry.
    
    Monitors positions for exit conditions and computes P/L.
    """
    
    def __init__(self):
        self.take_profit_pct = settings.take_profit_pct
        self.stop_loss_pct = settings.stop_loss_pct
        self.max_position_time_mins = 90  # Close after 90 minutes
    
    def calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        size: float,
        outcome: str
    ) -> Tuple[float, float]:
        """
        Calculate realized P/L for a closed position.
        
        Args:
            entry_price: Entry price (0-1).
            exit_price: Exit price (0-1).
            size: Position size in dollars.
            outcome: "yes" or "no".
            
        Returns:
            Tuple of (pnl_dollars, pnl_percent).
        """
        if outcome.lower() == "yes":
            # Long YES: profit when price goes up
            pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
        else:
            # Long NO: profit when price goes down
            pnl_pct = (entry_price - exit_price) / entry_price if entry_price > 0 else 0
        
        pnl_dollars = size * pnl_pct
        
        return (pnl_dollars, pnl_pct * 100)
    
    def calculate_unrealized_pnl(self, position: Position) -> Tuple[float, float]:
        """
        Calculate unrealized P/L for an open position.
        
        Args:
            position: The open position.
            
        Returns:
            Tuple of (unrealized_pnl_dollars, unrealized_pnl_percent).
        """
        return self.calculate_pnl(
            position.entry_price,
            position.current_price,
            position.size,
            position.outcome
        )
    
    def check_take_profit(self, position: Position) -> bool:
        """
        Check if position should be closed for take-profit.
        
        Args:
            position: The position to check.
            
        Returns:
            True if take-profit triggered.
        """
        _, pnl_pct = self.calculate_unrealized_pnl(position)
        
        if pnl_pct >= self.take_profit_pct * 100:
            logger.info(
                f"Take-profit triggered for {position.id}: "
                f"+{pnl_pct:.1f}% >= {self.take_profit_pct * 100:.1f}%"
            )
            return True
        
        return False
    
    def check_stop_loss(self, position: Position) -> bool:
        """
        Check if position should be closed for stop-loss.
        
        Args:
            position: The position to check.
            
        Returns:
            True if stop-loss triggered.
        """
        _, pnl_pct = self.calculate_unrealized_pnl(position)
        
        if pnl_pct <= -self.stop_loss_pct * 100:
            logger.info(
                f"Stop-loss triggered for {position.id}: "
                f"{pnl_pct:.1f}% <= -{self.stop_loss_pct * 100:.1f}%"
            )
            return True
        
        return False
    
    def check_time_exit(self, position: Position) -> bool:
        """
        Check if position should be closed due to time.
        
        Args:
            position: The position to check.
            
        Returns:
            True if time exit triggered.
        """
        time_open = (datetime.utcnow() - position.opened_at).total_seconds() / 60
        
        if time_open >= self.max_position_time_mins:
            logger.info(
                f"Time exit triggered for {position.id}: "
                f"{time_open:.0f} mins >= {self.max_position_time_mins} mins"
            )
            return True
        
        return False
    
    def check_match_ended(self, position: Position) -> bool:
        """
        Check if the match has ended (position should be closed).
        
        Args:
            position: The position to check.
            
        Returns:
            True if match ended.
        """
        from core.models import MatchStatus
        
        match = state_manager.get_match(position.match_id)
        if not match:
            return False
        
        ended_statuses = {
            MatchStatus.FINISHED,
            MatchStatus.CANCELLED,
            MatchStatus.ABANDONED,
            MatchStatus.POSTPONED
        }
        
        if match.status in ended_statuses:
            logger.info(f"Match ended for position {position.id}: {match.status}")
            return True
        
        return False
    
    def get_exit_reason(self, position: Position) -> Optional[str]:
        """
        Determine if and why a position should be exited.
        
        Args:
            position: The position to check.
            
        Returns:
            Exit reason string, or None if no exit needed.
        """
        if self.check_take_profit(position):
            return "take_profit"
        
        if self.check_stop_loss(position):
            return "stop_loss"
        
        if self.check_time_exit(position):
            return "time_exit"
        
        if self.check_match_ended(position):
            return "match_ended"
        
        return None
    
    def get_positions_to_exit(self) -> List[Tuple[Position, str]]:
        """
        Get all positions that should be exited.
        
        Returns:
            List of (position, reason) tuples.
        """
        positions = state_manager.get_open_positions()
        to_exit = []
        
        for position in positions:
            reason = self.get_exit_reason(position)
            if reason:
                to_exit.append((position, reason))
        
        return to_exit
    
    def update_position_prices(self, market_prices: dict[str, float]) -> None:
        """
        Update current prices for all open positions.
        
        Args:
            market_prices: Dict of market_id -> current_price.
        """
        positions = state_manager.get_open_positions()
        
        for position in positions:
            if position.market_id in market_prices:
                new_price = market_prices[position.market_id]
                state_manager.update_position_price(position.id, new_price)


# Singleton instance
post_trade_manager = PostTradeManager()
