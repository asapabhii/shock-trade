"""
State Manager - Tracks application state.

Maintains:
- Current matches being watched
- Pre-goal probabilities
- Open positions
- Trading metrics
"""
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger

from core.models import (
    Match, GoalEvent, Position, Trade, MatchMarketMapping,
    TradingMetrics, PositionStatus,
    NFLGame, NFLScoringEvent, NFLGameMarketMapping, NFLGameStatus
)


class StateManager:
    """
    Centralized state management for the trading bot.
    
    Tracks all runtime state including matches, positions, and metrics.
    """
    
    def __init__(self):
        # Match tracking (soccer - legacy)
        self._matches: Dict[int, Match] = {}
        self._match_mappings: Dict[int, MatchMarketMapping] = {}
        
        # NFL Game tracking
        self._nfl_games: Dict[int, NFLGame] = {}
        self._nfl_mappings: Dict[int, NFLGameMarketMapping] = {}
        
        # Goal tracking (soccer - legacy)
        self._processed_goals: set[str] = set()
        self._goal_history: List[GoalEvent] = []
        
        # NFL Score tracking
        self._processed_nfl_scores: set[str] = set()
        self._nfl_score_history: List[NFLScoringEvent] = []
        
        # Position tracking
        self._open_positions: Dict[str, Position] = {}
        self._closed_positions: List[Position] = []
        
        # Trade history
        self._trades: List[Trade] = []
        
        # Metrics
        self._metrics = TradingMetrics()
        self._latencies: List[float] = []
        self._slippages: List[float] = []
    
    # ==================== Match Management ====================
    
    def update_matches(self, matches: List[Match]) -> None:
        """Update the current match state."""
        for match in matches:
            self._matches[match.id] = match
    
    def get_match(self, match_id: int) -> Optional[Match]:
        """Get a match by ID."""
        return self._matches.get(match_id)
    
    def get_all_matches(self) -> List[Match]:
        """Get all tracked matches."""
        return list(self._matches.values())
    
    def get_live_matches(self) -> List[Match]:
        """Get only live matches."""
        from core.models import MatchStatus
        live_statuses = {
            MatchStatus.FIRST_HALF,
            MatchStatus.SECOND_HALF,
            MatchStatus.HALFTIME,
            MatchStatus.LIVE
        }
        return [m for m in self._matches.values() if m.status in live_statuses]
    
    def get_previous_matches(self) -> Dict[int, Match]:
        """Get matches dict for goal detection comparison."""
        return self._matches.copy()
    
    # ==================== Mapping Management ====================
    
    def set_mapping(self, match_id: int, mapping: MatchMarketMapping) -> None:
        """Store market mapping for a match."""
        self._match_mappings[match_id] = mapping
    
    def get_mapping(self, match_id: int) -> Optional[MatchMarketMapping]:
        """Get market mapping for a match."""
        return self._match_mappings.get(match_id)
    
    # ==================== Goal Management ====================
    
    def is_goal_processed(self, goal_id: str) -> bool:
        """Check if a goal has already been processed."""
        return goal_id in self._processed_goals
    
    def mark_goal_processed(self, goal: GoalEvent) -> None:
        """Mark a goal as processed."""
        self._processed_goals.add(goal.id)
        self._goal_history.append(goal)
    
    def get_goal_history(self, limit: int = 50) -> List[GoalEvent]:
        """Get recent goal history."""
        return self._goal_history[-limit:]
    
    # ==================== NFL Game Management ====================
    
    def update_nfl_games(self, games: List[NFLGame]) -> None:
        """Update the current NFL game state."""
        for game in games:
            self._nfl_games[game.id] = game
    
    def get_nfl_game(self, game_id: int) -> Optional[NFLGame]:
        """Get an NFL game by ID."""
        return self._nfl_games.get(game_id)
    
    def get_all_nfl_games(self) -> List[NFLGame]:
        """Get all tracked NFL games."""
        return list(self._nfl_games.values())
    
    def get_live_nfl_games(self) -> List[NFLGame]:
        """Get only live NFL games."""
        return [g for g in self._nfl_games.values() if g.is_live]
    
    def get_previous_nfl_games(self) -> Dict[int, NFLGame]:
        """Get NFL games dict for score detection comparison."""
        return self._nfl_games.copy()
    
    # ==================== NFL Mapping Management ====================
    
    def set_nfl_mapping(self, game_id: int, mapping: NFLGameMarketMapping) -> None:
        """Store market mapping for an NFL game."""
        self._nfl_mappings[game_id] = mapping
    
    def get_nfl_mapping(self, game_id: int) -> Optional[NFLGameMarketMapping]:
        """Get market mapping for an NFL game."""
        return self._nfl_mappings.get(game_id)
    
    # ==================== NFL Score Management ====================
    
    def is_nfl_score_processed(self, event_id: str) -> bool:
        """Check if an NFL scoring event has already been processed."""
        return event_id in self._processed_nfl_scores
    
    def mark_nfl_score_processed(self, event: NFLScoringEvent) -> None:
        """Mark an NFL scoring event as processed."""
        self._processed_nfl_scores.add(event.id)
        self._nfl_score_history.append(event)
    
    def get_nfl_score_history(self, limit: int = 50) -> List[NFLScoringEvent]:
        """Get recent NFL scoring history."""
        return self._nfl_score_history[-limit:]
    
    # ==================== Position Management ====================
    
    def add_position(self, position: Position) -> None:
        """Add a new open position."""
        self._open_positions[position.id] = position
        self._update_metrics()
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a position by ID."""
        return self._open_positions.get(position_id)
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self._open_positions.values())
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_order_id: str
    ) -> Optional[Position]:
        """Close a position and move to history."""
        position = self._open_positions.pop(position_id, None)
        if position:
            position.status = PositionStatus.CLOSED
            position.current_price = exit_price
            position.closed_at = datetime.utcnow()
            position.exit_order_id = exit_order_id
            
            # Calculate realized P/L
            if position.outcome == "yes":
                position.realized_pnl = (exit_price - position.entry_price) * position.size
            else:
                position.realized_pnl = (position.entry_price - exit_price) * position.size
            
            self._closed_positions.append(position)
            self._update_metrics()
        
        return position
    
    def update_position_price(self, position_id: str, current_price: float) -> None:
        """Update current price for a position."""
        position = self._open_positions.get(position_id)
        if position:
            position.current_price = current_price
            if position.outcome == "yes":
                position.unrealized_pnl = (current_price - position.entry_price) * position.size
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.size
    
    # ==================== Trade Management ====================
    
    def add_trade(self, trade: Trade) -> None:
        """Record a completed trade."""
        self._trades.append(trade)
        self._update_metrics()
    
    def get_trades(self, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        return self._trades[-limit:]
    
    def get_trades_for_match(self, match_id: int) -> List[Trade]:
        """Get all trades for a specific match."""
        return [t for t in self._trades if t.match_id == match_id]
    
    # ==================== Metrics ====================
    
    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self._latencies.append(latency_ms)
        self._update_metrics()
    
    def record_slippage(self, slippage: float) -> None:
        """Record slippage (expected vs actual price)."""
        self._slippages.append(slippage)
        self._update_metrics()
    
    def _update_metrics(self) -> None:
        """Recalculate aggregated metrics."""
        total_trades = len(self._trades)
        winning = sum(1 for t in self._trades if t.pnl > 0)
        losing = sum(1 for t in self._trades if t.pnl < 0)
        total_pnl = sum(t.pnl for t in self._trades)
        
        # Today's P/L
        today = datetime.utcnow().date()
        daily_pnl = sum(
            t.pnl for t in self._trades
            if t.entry_time.date() == today
        )
        
        self._metrics = TradingMetrics(
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=winning / total_trades if total_trades > 0 else 0,
            total_pnl=total_pnl,
            avg_pnl_per_trade=total_pnl / total_trades if total_trades > 0 else 0,
            avg_latency_ms=sum(self._latencies) / len(self._latencies) if self._latencies else 0,
            max_latency_ms=max(self._latencies) if self._latencies else 0,
            avg_slippage=sum(self._slippages) / len(self._slippages) if self._slippages else 0,
            daily_pnl=daily_pnl,
            open_positions=len(self._open_positions),
            total_exposure=sum(p.size for p in self._open_positions.values())
        )
    
    def get_metrics(self) -> TradingMetrics:
        """Get current trading metrics."""
        return self._metrics
    
    # ==================== Cleanup ====================
    
    def clear_finished_matches(self) -> None:
        """Remove finished matches from tracking."""
        from core.models import MatchStatus
        finished_statuses = {
            MatchStatus.FINISHED,
            MatchStatus.CANCELLED,
            MatchStatus.POSTPONED,
            MatchStatus.ABANDONED
        }
        
        to_remove = [
            mid for mid, match in self._matches.items()
            if match.status in finished_statuses
        ]
        
        for mid in to_remove:
            del self._matches[mid]
            self._match_mappings.pop(mid, None)
        
        if to_remove:
            logger.info(f"Cleared {len(to_remove)} finished matches from state")
    
    def clear_finished_nfl_games(self) -> None:
        """Remove finished NFL games from tracking."""
        finished_statuses = {
            NFLGameStatus.FINAL,
            NFLGameStatus.CANCELLED,
            NFLGameStatus.POSTPONED
        }
        
        to_remove = [
            gid for gid, game in self._nfl_games.items()
            if game.status in finished_statuses
        ]
        
        for gid in to_remove:
            del self._nfl_games[gid]
            self._nfl_mappings.pop(gid, None)
        
        if to_remove:
            logger.info(f"Cleared {len(to_remove)} finished NFL games from state")
    
    def reset(self) -> None:
        """Reset all state (for testing or restart)."""
        self._matches.clear()
        self._match_mappings.clear()
        self._processed_goals.clear()
        self._goal_history.clear()
        self._nfl_games.clear()
        self._nfl_mappings.clear()
        self._processed_nfl_scores.clear()
        self._nfl_score_history.clear()
        self._open_positions.clear()
        self._closed_positions.clear()
        self._trades.clear()
        self._latencies.clear()
        self._slippages.clear()
        self._metrics = TradingMetrics()
        logger.info("State manager reset")


# Singleton instance
state_manager = StateManager()
