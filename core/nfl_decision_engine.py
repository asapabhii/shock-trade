"""
NFL Decision Engine - Core trading strategy logic for NFL games.

Implements the underdog scoring-reaction strategy:
1. Detect if scoring team was the underdog (based on spread)
2. Check if current odds still offer value
3. Generate trade signals when conditions are met
"""
import uuid
from datetime import datetime
from typing import Optional, Tuple
from loguru import logger

from config import settings
from core.models import (
    NFLGame, NFLScoringEvent, Market, NFLGameMarketMapping,
    OrderIntent, OrderSide
)


class NFLDecisionEngine:
    """
    Implements the underdog scoring-reaction trading strategy for NFL.
    
    Strategy Rules:
    - When a touchdown is scored, check if the scoring team was the underdog
    - Underdog = team with positive spread (expected to lose)
    - If underdog scored and current price still offers value, generate BUY signal
    - Apply additional filters: liquidity, time remaining, score differential
    """
    
    def __init__(self):
        self.min_liquidity = settings.min_liquidity
        self.max_price_after_score = 0.70  # Don't buy if price already spiked too high
        self.min_time_remaining_quarters = 1  # Don't trade in final quarter
        self.min_points_for_signal = 6  # Only react to touchdowns (6+ points)
    
    def is_underdog(
        self,
        team_id: int,
        game: NFLGame,
        mapping: NFLGameMarketMapping
    ) -> Tuple[bool, Optional[float], str]:
        """
        Determine if a team is the underdog based on spread.
        
        In NFL betting:
        - Negative spread = favored (e.g., -7 means favored by 7)
        - Positive spread = underdog (e.g., +7 means underdog by 7)
        
        Args:
            team_id: ID of the team to check.
            game: The game object.
            mapping: Market mapping with spread info.
            
        Returns:
            Tuple of (is_underdog, spread_value, reason).
        """
        is_home = team_id == game.home_team.id
        spread = mapping.spread or game.spread
        
        if spread is None:
            # No spread available - use market prices as proxy
            if mapping.pre_score_home_prob and mapping.pre_score_away_prob:
                if is_home:
                    is_underdog = mapping.pre_score_home_prob < 0.45
                    return (is_underdog, None, f"Home prob {mapping.pre_score_home_prob:.2f}")
                else:
                    is_underdog = mapping.pre_score_away_prob < 0.45
                    return (is_underdog, None, f"Away prob {mapping.pre_score_away_prob:.2f}")
            
            # Default: away team is more likely underdog
            return (not is_home, None, "No spread - assuming away is underdog")
        
        # Spread is typically from home team perspective
        # Negative spread = home favored, Positive = away favored
        if is_home:
            # Home team is underdog if spread is positive (they're getting points)
            is_underdog = spread > 0
            team_spread = spread
        else:
            # Away team is underdog if spread is negative (home is favored)
            is_underdog = spread < 0
            team_spread = -spread
        
        reason = f"Spread: {'+' if team_spread > 0 else ''}{team_spread}"
        return (is_underdog, team_spread, reason)
    
    def find_best_market(
        self,
        team_id: int,
        game: NFLGame,
        mapping: NFLGameMarketMapping
    ) -> Optional[Market]:
        """
        Find the best market to trade for a team's win.
        
        Args:
            team_id: ID of the team that scored.
            game: The game object.
            mapping: Market mapping with available markets.
            
        Returns:
            Best Market to trade, or None if no suitable market found.
        """
        is_home = team_id == game.home_team.id
        team = game.home_team if is_home else game.away_team
        team_name = team.name.lower()
        team_abbrev = team.abbreviation.lower()
        
        best_market = None
        best_score = 0
        
        for market in mapping.markets:
            title_lower = market.title.lower()
            
            # Look for team-specific win markets
            name_match = (
                team_name in title_lower or
                team_abbrev in title_lower or
                any(word in title_lower for word in team_name.split() if len(word) > 3)
            )
            
            if name_match:
                score = 1
                
                # Prefer "win" markets
                if "win" in title_lower:
                    score += 3
                
                # Prefer moneyline markets
                if "moneyline" in title_lower or "ml" in title_lower:
                    score += 2
                
                # Prefer open markets
                if market.status == "open":
                    score += 1
                
                # Prefer liquid markets
                if market.yes_volume > self.min_liquidity:
                    score += 1
                
                if score > best_score:
                    best_score = score
                    best_market = market
        
        return best_market

    def check_value(
        self,
        market: Market,
        pre_score_prob: Optional[float],
        is_underdog: bool
    ) -> Tuple[bool, str]:
        """
        Check if current market price still offers value.
        
        Args:
            market: Current market data.
            pre_score_prob: Pre-score implied probability.
            is_underdog: Whether the scoring team was underdog.
            
        Returns:
            Tuple of (has_value, reason).
        """
        current_price = market.yes_price
        
        # Price already too high - market has adjusted
        if current_price > self.max_price_after_score:
            return (False, f"Price too high ({current_price:.2f} > {self.max_price_after_score})")
        
        # If we have pre-score prob, check for value
        if pre_score_prob is not None:
            # After underdog scores, expect price to move up
            # We want to catch it before full adjustment
            expected_move = 0.08  # Expect ~8% move after TD
            if current_price < pre_score_prob + expected_move:
                return (True, f"Value: current {current_price:.2f} < expected {pre_score_prob + expected_move:.2f}")
        
        # For underdogs, if price is still below 50%, there's potential
        if is_underdog and current_price < 0.50:
            return (True, f"Underdog price still below 50% ({current_price:.2f})")
        
        # Even for non-underdogs, very low prices might have value
        if current_price < 0.35:
            return (True, f"Low price opportunity ({current_price:.2f})")
        
        return (False, f"No clear value at current price ({current_price:.2f})")
    
    def check_liquidity(self, market: Market) -> Tuple[bool, str]:
        """
        Check if market has sufficient liquidity.
        
        Args:
            market: Market to check.
            
        Returns:
            Tuple of (has_liquidity, reason).
        """
        total_volume = market.yes_volume + market.no_volume
        
        if total_volume < self.min_liquidity:
            return (False, f"Insufficient liquidity ({total_volume} < {self.min_liquidity})")
        
        return (True, f"Liquidity OK ({total_volume})")
    
    def check_time_remaining(
        self,
        game: NFLGame,
        scoring_event: NFLScoringEvent
    ) -> Tuple[bool, str]:
        """
        Check if enough time remains in the game.
        
        Args:
            game: The game object.
            scoring_event: The scoring event.
            
        Returns:
            Tuple of (time_ok, reason).
        """
        quarter = scoring_event.quarter or game.quarter
        
        # Don't trade in 4th quarter or OT - too volatile
        if quarter >= 4:
            return (False, f"Too late in game (Q{quarter})")
        
        # Prefer first half for more time to realize value
        if quarter <= 2:
            return (True, f"Good timing (Q{quarter})")
        
        return (True, f"Acceptable timing (Q{quarter})")
    
    def check_score_differential(
        self,
        game: NFLGame,
        scoring_event: NFLScoringEvent
    ) -> Tuple[bool, str]:
        """
        Check if score differential makes sense for the trade.
        
        Args:
            game: The game object.
            scoring_event: The scoring event.
            
        Returns:
            Tuple of (diff_ok, reason).
        """
        diff = abs(scoring_event.home_score - scoring_event.away_score)
        
        # If game is a blowout, skip
        if diff > 21:
            return (False, f"Blowout game ({diff} point differential)")
        
        # Close games are ideal
        if diff <= 14:
            return (True, f"Competitive game ({diff} point differential)")
        
        return (True, f"Moderate differential ({diff} points)")
    
    def evaluate_scoring_event(
        self,
        scoring_event: NFLScoringEvent,
        game: NFLGame,
        mapping: NFLGameMarketMapping
    ) -> Optional[OrderIntent]:
        """
        Evaluate a scoring event and decide whether to trade.
        
        This is the main entry point for the decision engine.
        
        Args:
            scoring_event: The detected scoring event.
            game: Current game state.
            mapping: Market mapping for this game.
            
        Returns:
            OrderIntent if trade should be placed, None otherwise.
        """
        logger.info(
            f"Evaluating score: {scoring_event.scoring_team_name} "
            f"{scoring_event.scoring_type} (+{scoring_event.points_scored}) "
            f"in {game.display_name}"
        )
        
        # Step 0: Only react to significant scores (touchdowns)
        if scoring_event.points_scored < self.min_points_for_signal:
            logger.info(f"Score too small ({scoring_event.points_scored} pts). Skipping.")
            return None
        
        # Step 1: Check if scoring team was underdog
        is_underdog, spread_val, underdog_reason = self.is_underdog(
            scoring_event.scoring_team_id, game, mapping
        )
        
        if not is_underdog:
            logger.info(f"Scoring team was not underdog ({underdog_reason}). Skipping.")
            return None
        
        logger.info(f"Underdog touchdown detected! {underdog_reason}")
        
        # Step 2: Find best market to trade
        market = self.find_best_market(scoring_event.scoring_team_id, game, mapping)
        
        if market is None:
            logger.warning(f"No suitable market found for {scoring_event.scoring_team_name}")
            return None
        
        logger.info(f"Found market: {market.title} (current price: {market.yes_price})")
        
        # Get pre-score probability
        is_home = scoring_event.scoring_team_id == game.home_team.id
        pre_prob = mapping.pre_score_home_prob if is_home else mapping.pre_score_away_prob
        
        # Step 3: Check value
        has_value, value_reason = self.check_value(market, pre_prob, is_underdog)
        if not has_value:
            logger.info(f"No value: {value_reason}")
            return None
        
        # Step 4: Check liquidity
        has_liquidity, liquidity_reason = self.check_liquidity(market)
        if not has_liquidity:
            logger.info(f"Liquidity check failed: {liquidity_reason}")
            return None
        
        # Step 5: Check time remaining
        time_ok, time_reason = self.check_time_remaining(game, scoring_event)
        if not time_ok:
            logger.info(f"Time check failed: {time_reason}")
            return None
        
        # Step 6: Check score differential
        diff_ok, diff_reason = self.check_score_differential(game, scoring_event)
        if not diff_ok:
            logger.info(f"Score differential check failed: {diff_reason}")
            return None
        
        # All checks passed - generate order intent
        reason = (
            f"Underdog {scoring_event.scoring_team_name} scored {scoring_event.scoring_type}. "
            f"{underdog_reason}. {value_reason}. {time_reason}. {diff_reason}."
        )
        
        order_intent = OrderIntent(
            id=str(uuid.uuid4()),
            match_id=game.id,
            market_id=market.id,
            exchange=market.exchange,
            side=OrderSide.BUY,
            outcome="yes",
            size=0,  # Will be set by risk manager
            limit_price=min(market.yes_price + 0.03, 0.95),  # Slight premium for faster fill
            reason=reason,
            goal_event_id=scoring_event.id
        )
        
        logger.info(f"Generated order intent: {order_intent.id}")
        return order_intent


# Singleton instance
nfl_decision_engine = NFLDecisionEngine()
