"""
Risk Manager - Controls position sizing and risk limits.

Implements:
- Per-trade position sizing
- Per-match exposure limits
- Daily loss limits
- Circuit breaker for consecutive errors
"""
from datetime import datetime, date
from typing import Optional, Tuple
from loguru import logger

from config import settings
from core.models import OrderIntent, RiskStatus, Position


class RiskManager:
    """
    Manages trading risk and position sizing.
    
    Enforces:
    - Maximum position size per trade
    - Maximum exposure per match
    - Daily loss limits
    - Circuit breaker on consecutive errors
    """
    
    def __init__(self):
        self.bankroll = settings.bankroll
        self.max_per_trade_pct = settings.max_per_trade_pct / 100  # Convert to decimal
        self.daily_loss_limit = settings.daily_loss_limit
        self.per_match_max_exposure = settings.per_match_max_exposure
        self.max_consecutive_errors = settings.max_consecutive_errors
        
        # State tracking
        self._daily_pnl: float = 0.0
        self._current_date: date = date.today()
        self._match_exposure: dict[int, float] = {}  # match_id -> exposure
        self._consecutive_errors: int = 0
        self._circuit_breaker_active: bool = False
        self._last_error: Optional[str] = None
        self._open_positions: list[Position] = []
    
    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters if it's a new day."""
        today = date.today()
        if today != self._current_date:
            logger.info(f"New day detected. Resetting daily P/L from {self._daily_pnl}")
            self._daily_pnl = 0.0
            self._current_date = today
            self._match_exposure.clear()
    
    def get_status(self) -> RiskStatus:
        """Get current risk status."""
        self._reset_daily_if_needed()
        
        total_exposure = sum(self._match_exposure.values())
        
        return RiskStatus(
            daily_pnl=self._daily_pnl,
            daily_loss_limit=self.daily_loss_limit,
            daily_loss_remaining=self.daily_loss_limit + self._daily_pnl,  # Negative PnL reduces remaining
            current_exposure=total_exposure,
            max_exposure=self.per_match_max_exposure * 10,  # Rough total max
            consecutive_errors=self._consecutive_errors,
            circuit_breaker_active=self._circuit_breaker_active,
            last_error=self._last_error
        )
    
    def calculate_position_size(
        self,
        intent: OrderIntent,
        current_price: float
    ) -> float:
        """
        Calculate appropriate position size for a trade.
        
        Args:
            intent: The order intent.
            current_price: Current market price.
            
        Returns:
            Position size in dollars.
        """
        self._reset_daily_if_needed()
        
        # Base size from bankroll percentage
        base_size = self.bankroll * self.max_per_trade_pct
        
        # Adjust for remaining daily loss budget
        daily_remaining = self.daily_loss_limit + self._daily_pnl
        if daily_remaining < base_size:
            base_size = max(0, daily_remaining)
        
        # Adjust for per-match exposure
        current_match_exposure = self._match_exposure.get(intent.match_id, 0)
        match_remaining = self.per_match_max_exposure - current_match_exposure
        if match_remaining < base_size:
            base_size = max(0, match_remaining)
        
        # Round to reasonable amount
        size = round(base_size, 2)
        
        logger.debug(
            f"Position size calculated: ${size} "
            f"(base: ${self.bankroll * self.max_per_trade_pct:.2f}, "
            f"daily remaining: ${daily_remaining:.2f}, "
            f"match remaining: ${match_remaining:.2f})"
        )
        
        return size
    
    def check_trade_allowed(
        self,
        intent: OrderIntent
    ) -> Tuple[bool, str]:
        """
        Check if a trade is allowed under current risk rules.
        
        Args:
            intent: The order intent to check.
            
        Returns:
            Tuple of (allowed, reason).
        """
        self._reset_daily_if_needed()
        
        # Check circuit breaker
        if self._circuit_breaker_active:
            return (False, f"Circuit breaker active after {self._consecutive_errors} consecutive errors")
        
        # Check daily loss limit
        if self._daily_pnl <= -self.daily_loss_limit:
            return (False, f"Daily loss limit reached (${self._daily_pnl:.2f})")
        
        # Check per-match exposure
        current_match_exposure = self._match_exposure.get(intent.match_id, 0)
        if current_match_exposure >= self.per_match_max_exposure:
            return (False, f"Per-match exposure limit reached (${current_match_exposure:.2f})")
        
        # Check if size would be meaningful
        size = self.calculate_position_size(intent, intent.limit_price)
        if size < 1.0:  # Minimum $1 trade
            return (False, f"Position size too small (${size:.2f})")
        
        return (True, "Trade allowed")
    
    def approve_trade(
        self,
        intent: OrderIntent
    ) -> Tuple[Optional[OrderIntent], str]:
        """
        Approve a trade and set the position size.
        
        Args:
            intent: The order intent to approve.
            
        Returns:
            Tuple of (approved_intent with size, reason).
        """
        allowed, reason = self.check_trade_allowed(intent)
        
        if not allowed:
            logger.warning(f"Trade rejected: {reason}")
            return (None, reason)
        
        # Calculate and set size
        size = self.calculate_position_size(intent, intent.limit_price)
        
        # Create new intent with size
        approved_intent = intent.model_copy(update={"size": size})
        
        logger.info(f"Trade approved: ${size:.2f} on {intent.market_id}")
        return (approved_intent, f"Approved with size ${size:.2f}")
    
    def record_trade_result(
        self,
        match_id: int,
        pnl: float,
        exposure_change: float
    ) -> None:
        """
        Record the result of a trade.
        
        Args:
            match_id: The match ID.
            pnl: Realized P/L from the trade.
            exposure_change: Change in exposure (positive for new position, negative for close).
        """
        self._reset_daily_if_needed()
        
        self._daily_pnl += pnl
        
        current_exposure = self._match_exposure.get(match_id, 0)
        self._match_exposure[match_id] = max(0, current_exposure + exposure_change)
        
        logger.info(
            f"Trade recorded: P/L ${pnl:.2f}, "
            f"Daily P/L: ${self._daily_pnl:.2f}, "
            f"Match {match_id} exposure: ${self._match_exposure[match_id]:.2f}"
        )
    
    def record_error(self, error_message: str) -> None:
        """
        Record an error for circuit breaker tracking.
        
        Args:
            error_message: Description of the error.
        """
        self._consecutive_errors += 1
        self._last_error = error_message
        
        if self._consecutive_errors >= self.max_consecutive_errors:
            self._circuit_breaker_active = True
            logger.error(
                f"Circuit breaker ACTIVATED after {self._consecutive_errors} errors. "
                f"Last error: {error_message}"
            )
    
    def record_success(self) -> None:
        """Record a successful operation, resetting error counter."""
        self._consecutive_errors = 0
    
    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._circuit_breaker_active = False
        self._consecutive_errors = 0
        self._last_error = None
        logger.info("Circuit breaker reset")
    
    def update_bankroll(self, new_bankroll: float) -> None:
        """Update the bankroll amount."""
        self.bankroll = new_bankroll
        logger.info(f"Bankroll updated to ${new_bankroll:.2f}")
    
    def add_position(self, position: Position) -> None:
        """Track an open position."""
        self._open_positions.append(position)
        self._match_exposure[position.match_id] = (
            self._match_exposure.get(position.match_id, 0) + position.size
        )
    
    def remove_position(self, position_id: str) -> Optional[Position]:
        """Remove a closed position."""
        for i, pos in enumerate(self._open_positions):
            if pos.id == position_id:
                removed = self._open_positions.pop(i)
                return removed
        return None
    
    def get_open_positions(self) -> list[Position]:
        """Get all open positions."""
        return self._open_positions.copy()


# Singleton instance
risk_manager = RiskManager()
