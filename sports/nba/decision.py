"""
NBA Decision Engine - Trading strategy for NBA.

Strategy: React when underdog team goes on a scoring run.
"""
from typing import Tuple, Optional
from loguru import logger

from sports.base import (
    BaseDecisionEngine, BaseGame, BaseGameMarketMapping, BaseScoringEvent
)


class NBADecisionEngine(BaseDecisionEngine):
    """
    NBA-specific trading strategy.
    
    Strategy: When underdog goes on a 10+ point run, bet on momentum.
    """
    
    sport_name = "nba"
    min_points_for_signal = 10  # Significant scoring run
    
    def __init__(self):
        self.max_quarter_for_trade = 3  # Don't trade in 4th quarter
        self.max_point_differential = 25
    
    def is_underdog(
        self,
        team_id: int,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, Optional[float], str]:
        """Determine if team is underdog based on spread."""
        is_home = team_id == game.home_team.id
        spread = mapping.spread or game.spread
        
        if spread is not None:
            if is_home:
                is_underdog = spread > 0
                team_spread = spread
            else:
                is_underdog = spread < 0
                team_spread = -spread
            return (is_underdog, team_spread, f"Spread: {team_spread:+.1f}")
        
        # Default: away team is underdog
        return (not is_home, None, "Away team (default)")
    
    def check_time_remaining(
        self,
        game: BaseGame,
        event: BaseScoringEvent
    ) -> Tuple[bool, str]:
        """Check if enough time remains."""
        quarter = event.period or game.period
        
        if quarter >= 4:
            return (False, f"Too late (Q{quarter})")
        return (True, f"Q{quarter} - good timing")
    
    def check_score_differential(
        self,
        game: BaseGame,
        event: BaseScoringEvent
    ) -> Tuple[bool, str]:
        """Check if game is competitive."""
        diff = abs(event.home_score - event.away_score)
        
        if diff > self.max_point_differential:
            return (False, f"Blowout ({diff} pts)")
        return (True, f"Competitive ({diff} pts)")
    
    def should_trade(
        self,
        event: BaseScoringEvent,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, str]:
        """Determine if this scoring run should trigger a trade."""
        logger.info(
            f"Evaluating NBA run: {event.scoring_team_name} "
            f"+{event.points_scored} pts"
        )
        
        # Check minimum points
        if event.points_scored < self.min_points_for_signal:
            return (False, f"Run too small ({event.points_scored} pts)")
        
        # Check if underdog
        is_underdog, spread_val, underdog_reason = self.is_underdog(
            event.scoring_team_id, game, mapping
        )
        
        if not is_underdog:
            return (False, f"Favorite on run ({underdog_reason})")
        
        # Check time
        time_ok, time_reason = self.check_time_remaining(game, event)
        if not time_ok:
            return (False, time_reason)
        
        # Check differential
        diff_ok, diff_reason = self.check_score_differential(game, event)
        if not diff_ok:
            return (False, diff_reason)
        
        reason = (
            f"Underdog {event.scoring_team_name} on {event.points_scored}-pt run. "
            f"{underdog_reason}. {time_reason}. {diff_reason}."
        )
        return (True, reason)


nba_decision_engine = NBADecisionEngine()
