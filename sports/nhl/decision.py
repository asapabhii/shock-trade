"""NHL Decision Engine - Trading strategy for NHL."""
from typing import Tuple, Optional
from loguru import logger
from sports.base import BaseDecisionEngine, BaseGame, BaseGameMarketMapping, BaseScoringEvent


class NHLDecisionEngine(BaseDecisionEngine):
    """NHL strategy: React when underdog scores a goal."""
    
    sport_name = "nhl"
    min_points_for_signal = 1
    
    def __init__(self):
        self.max_period_for_trade = 2  # Don't trade in 3rd period
        self.max_goal_differential = 3
    
    def is_underdog(self, team_id: int, game: BaseGame, mapping: BaseGameMarketMapping) -> Tuple[bool, Optional[float], str]:
        is_home = team_id == game.home_team.id
        spread = mapping.spread or game.spread
        if spread is not None:
            if is_home:
                is_underdog = spread > 0
                return (is_underdog, spread, f"Spread: {spread:+.1f}")
            else:
                is_underdog = spread < 0
                return (is_underdog, -spread, f"Spread: {-spread:+.1f}")
        return (not is_home, None, "Away team (default)")
    
    def check_time_remaining(self, game: BaseGame, event: BaseScoringEvent) -> Tuple[bool, str]:
        period = event.period or game.period
        if period >= 3:
            return (False, f"Too late (Period {period})")
        return (True, f"Period {period} - good timing")
    
    def check_score_differential(self, game: BaseGame, event: BaseScoringEvent) -> Tuple[bool, str]:
        diff = abs(event.home_score - event.away_score)
        if diff > self.max_goal_differential:
            return (False, f"Blowout ({diff} goals)")
        return (True, f"Competitive ({diff} goals)")
    
    def should_trade(self, event: BaseScoringEvent, game: BaseGame, mapping: BaseGameMarketMapping) -> Tuple[bool, str]:
        logger.info(f"Evaluating NHL goal: {event.scoring_team_name}")
        
        is_underdog, spread_val, underdog_reason = self.is_underdog(event.scoring_team_id, game, mapping)
        if not is_underdog:
            return (False, f"Favorite scored ({underdog_reason})")
        
        time_ok, time_reason = self.check_time_remaining(game, event)
        if not time_ok:
            return (False, time_reason)
        
        diff_ok, diff_reason = self.check_score_differential(game, event)
        if not diff_ok:
            return (False, diff_reason)
        
        return (True, f"Underdog {event.scoring_team_name} goal. {underdog_reason}. {time_reason}. {diff_reason}.")

nhl_decision_engine = NHLDecisionEngine()
