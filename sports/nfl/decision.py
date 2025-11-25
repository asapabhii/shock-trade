"""
NFL Decision Engine - Trading strategy for NFL.

Strategy: React when underdog team scores a touchdown.
"""
from typing import Tuple, Optional
from loguru import logger

from sports.base import (
    BaseDecisionEngine, BaseGame, BaseGameMarketMapping, BaseScoringEvent
)


class NFLDecisionEngine(BaseDecisionEngine):
    """
    NFL-specific trading strategy.
    
    Strategy: When underdog scores a touchdown, bet on momentum.
    Underdog determined by point spread.
    """
    
    sport_name = "nfl"
    min_points_for_signal = 6  # Only touchdowns (6+ points)
    
    def __init__(self):
        self.max_quarter_for_trade = 3  # Don't trade in 4th quarter
        self.max_point_differential = 21  # Skip blowouts
    
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
            # Spread is from home team perspective
            # Negative = home favored, Positive = away favored
            if is_home:
                is_underdog = spread > 0
                team_spread = spread
            else:
                is_underdog = spread < 0
                team_spread = -spread
            
            return (is_underdog, team_spread, f"Spread: {team_spread:+.1f}")
        
        # Use probabilities if available
        if mapping.pre_event_home_prob and mapping.pre_event_away_prob:
            prob = mapping.pre_event_home_prob if is_home else mapping.pre_event_away_prob
            is_underdog = prob < 0.45
            return (is_underdog, prob, f"Win prob: {prob:.1%}")
        
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
        if quarter <= 2:
            return (True, f"First half (Q{quarter})")
        return (True, f"Third quarter (Q{quarter})")
    
    def check_score_differential(
        self,
        game: BaseGame,
        event: BaseScoringEvent
    ) -> Tuple[bool, str]:
        """Check if game is competitive."""
        diff = abs(event.home_score - event.away_score)
        
        if diff > self.max_point_differential:
            return (False, f"Blowout ({diff} pts)")
        if diff <= 14:
            return (True, f"Competitive ({diff} pts)")
        return (True, f"Moderate lead ({diff} pts)")
    
    def should_trade(
        self,
        event: BaseScoringEvent,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, str]:
        """Determine if this score should trigger a trade."""
        logger.info(
            f"Evaluating NFL score: {event.scoring_team_name} "
            f"{event.scoring_type} (+{event.points_scored})"
        )
        
        # Only react to touchdowns
        if event.points_scored < self.min_points_for_signal:
            return (False, f"Not a touchdown ({event.points_scored} pts)")
        
        # Check if underdog scored
        is_underdog, spread_val, underdog_reason = self.is_underdog(
            event.scoring_team_id, game, mapping
        )
        
        if not is_underdog:
            return (False, f"Favorite scored ({underdog_reason})")
        
        # Check time remaining
        time_ok, time_reason = self.check_time_remaining(game, event)
        if not time_ok:
            return (False, time_reason)
        
        # Check score differential
        diff_ok, diff_reason = self.check_score_differential(game, event)
        if not diff_ok:
            return (False, diff_reason)
        
        reason = (
            f"Underdog {event.scoring_team_name} {event.scoring_type}. "
            f"{underdog_reason}. {time_reason}. {diff_reason}."
        )
        return (True, reason)


# Singleton instance
nfl_decision_engine = NFLDecisionEngine()
