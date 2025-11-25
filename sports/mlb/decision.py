"""MLB Decision Engine - Trading strategy for MLB."""
from typing import Tuple, Optional
from loguru import logger
from sports.base import BaseDecisionEngine, BaseGame, BaseGameMarketMapping, BaseScoringEvent


class MLBDecisionEngine(BaseDecisionEngine):
    """MLB strategy: React when underdog takes lead in late innings."""
    
    sport_name = "mlb"
    min_points_for_signal = 1
    
    def __init__(self):
        self.late_inning_start = 6  # 6th inning onwards
        self.max_run_differential = 5
    
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
        inning = event.period or game.period
        if inning >= self.late_inning_start:
            return (True, f"Late innings ({inning}th) - prime time")
        return (True, f"Inning {inning}")
    
    def check_score_differential(self, game: BaseGame, event: BaseScoringEvent) -> Tuple[bool, str]:
        diff = abs(event.home_score - event.away_score)
        if diff > self.max_run_differential:
            return (False, f"Blowout ({diff} runs)")
        return (True, f"Competitive ({diff} runs)")
    
    def _check_lead_change(self, event: BaseScoringEvent, game: BaseGame, prev_home: int, prev_away: int) -> bool:
        """Check if this scoring event caused a lead change."""
        was_home_leading = prev_home > prev_away
        was_away_leading = prev_away > prev_home
        was_tied = prev_home == prev_away
        
        now_home_leading = event.home_score > event.away_score
        now_away_leading = event.away_score > event.home_score
        
        if event.is_home_team:
            return (was_away_leading or was_tied) and now_home_leading
        else:
            return (was_home_leading or was_tied) and now_away_leading
    
    def should_trade(self, event: BaseScoringEvent, game: BaseGame, mapping: BaseGameMarketMapping) -> Tuple[bool, str]:
        logger.info(f"Evaluating MLB runs: {event.scoring_team_name} +{event.points_scored}")
        
        is_underdog, spread_val, underdog_reason = self.is_underdog(event.scoring_team_id, game, mapping)
        if not is_underdog:
            return (False, f"Favorite scored ({underdog_reason})")
        
        time_ok, time_reason = self.check_time_remaining(game, event)
        diff_ok, diff_reason = self.check_score_differential(game, event)
        if not diff_ok:
            return (False, diff_reason)
        
        # Prefer late inning scoring
        inning = event.period or game.period
        if inning < self.late_inning_start:
            return (False, f"Early innings ({inning}th) - waiting for late game")
        
        return (True, f"Underdog {event.scoring_team_name} scores in {inning}th. {underdog_reason}. {diff_reason}.")

mlb_decision_engine = MLBDecisionEngine()
