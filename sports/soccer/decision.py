"""
Soccer Decision Engine - Trading strategy for soccer/football.

Strategy: React when underdog team scores a goal.
"""
from typing import Tuple, Optional
from loguru import logger

from sports.base import (
    BaseDecisionEngine, BaseGame, BaseGameMarketMapping, BaseScoringEvent
)


class SoccerDecisionEngine(BaseDecisionEngine):
    """
    Soccer-specific trading strategy.
    
    Strategy: When underdog scores, bet on their momentum continuing.
    Underdog determined by pre-match odds or home/away status.
    """
    
    sport_name = "soccer"
    min_points_for_signal = 1  # Every goal matters in soccer
    
    def __init__(self):
        self.underdog_threshold = 0.45  # Below 45% win probability = underdog
        self.max_price_after_goal = 0.65
        self.min_period_for_trade = 1  # Can trade in first half
    
    def is_underdog(
        self,
        team_id: int,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, Optional[float], str]:
        """Determine if team is underdog based on odds."""
        is_home = team_id == game.home_team.id
        
        # Use pre-match probabilities if available
        if mapping.pre_event_home_prob and mapping.pre_event_away_prob:
            prob = mapping.pre_event_home_prob if is_home else mapping.pre_event_away_prob
            is_underdog = prob < self.underdog_threshold
            return (is_underdog, prob, f"Win probability: {prob:.1%}")
        
        # Use spread if available (negative = favored)
        if mapping.spread is not None:
            if is_home:
                is_underdog = mapping.spread > 0
                return (is_underdog, mapping.spread, f"Spread: {mapping.spread:+.1f}")
            else:
                is_underdog = mapping.spread < 0
                return (is_underdog, -mapping.spread, f"Spread: {-mapping.spread:+.1f}")
        
        # Default: away team is typically underdog
        is_underdog = not is_home
        return (is_underdog, None, "Away team (default underdog)")
    
    def check_time_remaining(
        self,
        game: BaseGame,
        event: BaseScoringEvent
    ) -> Tuple[bool, str]:
        """Check if enough time remains in the match."""
        # In soccer, goals in first half have more time to realize value
        if game.period == 1:
            return (True, "First half - good timing")
        elif game.period == 2:
            return (True, "Second half - acceptable")
        return (True, "Time check passed")
    
    def check_score_differential(
        self,
        game: BaseGame,
        event: BaseScoringEvent
    ) -> Tuple[bool, str]:
        """Check if game is competitive."""
        diff = abs(event.home_score - event.away_score)
        
        if diff > 3:
            return (False, f"Blowout game ({diff} goal differential)")
        if diff <= 1:
            return (True, f"Close game ({diff} goal differential)")
        return (True, f"Competitive ({diff} goal differential)")
    
    def should_trade(
        self,
        event: BaseScoringEvent,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, str]:
        """Determine if this goal should trigger a trade."""
        logger.info(f"Evaluating soccer goal: {event.scoring_team_name} in {game.display_name}")
        
        # Check if underdog scored
        is_underdog, odds_val, underdog_reason = self.is_underdog(
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
        
        reason = f"Underdog {event.scoring_team_name} scored. {underdog_reason}. {time_reason}. {diff_reason}."
        return (True, reason)


# Singleton instance
soccer_decision_engine = SoccerDecisionEngine()
