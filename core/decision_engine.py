"""
Decision Engine - Core trading strategy logic.

Implements the underdog goal-reaction strategy:
1. Detect if scoring team was the underdog
2. Check if current odds still offer value
3. Generate trade signals when conditions are met
"""
import uuid
from datetime import datetime
from typing import Optional, List, Tuple
from loguru import logger

from config import settings
from core.models import (
    Match, GoalEvent, Market, MatchMarketMapping,
    OrderIntent, OrderSide
)


class DecisionEngine:
    """
    Implements the underdog goal-reaction trading strategy.
    
    Strategy Rules:
    - When a goal is scored, check if the scoring team was the underdog
    - Underdog = team with implied probability < threshold before the goal
    - If underdog scored and current price still offers value, generate BUY signal
    - Apply additional filters: liquidity, time remaining, score differential
    """
    
    def __init__(self):
        self.underdog_threshold = settings.underdog_threshold
        self.min_liquidity = settings.min_liquidity
        self.max_price_after_goal = 0.65  # Don't buy if price already spiked too high
        self.min_time_remaining = 15  # Minutes - don't trade in final 15 mins
    
    def is_underdog(
        self,
        team_id: int,
        match: Match,
        mapping: MatchMarketMapping
    ) -> Tuple[bool, Optional[float]]:
        """
        Determine if a team was the underdog before the goal.
        
        Args:
            team_id: ID of the team to check.
            match: The match object.
            mapping: Market mapping with pre-goal probabilities.
            
        Returns:
            Tuple of (is_underdog, pre_goal_probability).
        """
        is_home = team_id == match.home_team.id
        
        if is_home:
            pre_prob = mapping.pre_goal_home_prob
        else:
            pre_prob = mapping.pre_goal_away_prob
        
        if pre_prob is None:
            # If we don't have pre-goal probability, use heuristics
            # Home team is usually favored, so away team is more likely underdog
            logger.warning(
                f"No pre-goal probability for team {team_id}, using heuristic"
            )
            return (not is_home, None)
        
        is_underdog = pre_prob < self.underdog_threshold
        return (is_underdog, pre_prob)
    
    def find_best_market(
        self,
        team_id: int,
        match: Match,
        mapping: MatchMarketMapping
    ) -> Optional[Market]:
        """
        Find the best market to trade for a team's win.
        
        Args:
            team_id: ID of the team that scored.
            match: The match object.
            mapping: Market mapping with available markets.
            
        Returns:
            Best Market to trade, or None if no suitable market found.
        """
        is_home = team_id == match.home_team.id
        team_name = match.home_team.name if is_home else match.away_team.name
        
        best_market = None
        best_score = 0
        
        for market in mapping.markets:
            title_lower = market.title.lower()
            team_lower = team_name.lower()
            
            # Look for team-specific win markets
            if team_lower in title_lower or any(
                alias in title_lower 
                for alias in [team_lower.replace(" fc", ""), team_lower.split()[0]]
            ):
                # Prefer markets with "win" in title
                score = 1
                if "win" in title_lower:
                    score += 2
                if market.status == "open":
                    score += 1
                if market.yes_volume > self.min_liquidity:
                    score += 1
                
                if score > best_score:
                    best_score = score
                    best_market = market
        
        return best_market
    
    def check_value(
        self,
        market: Market,
        pre_goal_prob: Optional[float]
    ) -> Tuple[bool, str]:
        """
        Check if current market price still offers value.
        
        Args:
            market: Current market data.
            pre_goal_prob: Pre-goal implied probability.
            
        Returns:
            Tuple of (has_value, reason).
        """
        current_price = market.yes_price
        
        # Price already too high - market has adjusted
        if current_price > self.max_price_after_goal:
            return (False, f"Price too high ({current_price:.2f} > {self.max_price_after_goal})")
        
        # If we have pre-goal prob, check for value
        if pre_goal_prob is not None:
            # We want to buy if price hasn't fully adjusted yet
            # Some edge should remain
            expected_move = 0.10  # Expect at least 10% move after goal
            if current_price < pre_goal_prob + expected_move:
                return (True, f"Value found: current {current_price:.2f} < expected {pre_goal_prob + expected_move:.2f}")
        
        # Default: if price is still below 50%, there's potential value
        if current_price < 0.50:
            return (True, f"Price still below 50% ({current_price:.2f})")
        
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
        match: Match,
        goal_event: GoalEvent
    ) -> Tuple[bool, str]:
        """
        Check if enough time remains in the match.
        
        Args:
            match: The match object.
            goal_event: The goal event.
            
        Returns:
            Tuple of (time_ok, reason).
        """
        minute = goal_event.minute or match.minute or 0
        
        # Standard match is 90 minutes
        time_remaining = 90 - minute
        
        if time_remaining < self.min_time_remaining:
            return (False, f"Not enough time remaining ({time_remaining} < {self.min_time_remaining} mins)")
        
        return (True, f"Time remaining OK ({time_remaining} mins)")
    
    def evaluate_goal(
        self,
        goal_event: GoalEvent,
        match: Match,
        mapping: MatchMarketMapping
    ) -> Optional[OrderIntent]:
        """
        Evaluate a goal event and decide whether to trade.
        
        This is the main entry point for the decision engine.
        
        Args:
            goal_event: The detected goal event.
            match: Current match state.
            mapping: Market mapping for this match.
            
        Returns:
            OrderIntent if trade should be placed, None otherwise.
        """
        logger.info(f"Evaluating goal: {goal_event.scoring_team_name} scored in {match.display_name}")
        
        # Step 1: Check if scoring team was underdog
        is_underdog, pre_prob = self.is_underdog(
            goal_event.scoring_team_id, match, mapping
        )
        
        if not is_underdog:
            logger.info(f"Scoring team was not underdog (pre-prob: {pre_prob}). Skipping.")
            return None
        
        logger.info(f"Underdog goal detected! Pre-goal probability: {pre_prob}")
        
        # Step 2: Find best market to trade
        market = self.find_best_market(goal_event.scoring_team_id, match, mapping)
        
        if market is None:
            logger.warning(f"No suitable market found for {goal_event.scoring_team_name}")
            return None
        
        logger.info(f"Found market: {market.title} (current price: {market.yes_price})")
        
        # Step 3: Check value
        has_value, value_reason = self.check_value(market, pre_prob)
        if not has_value:
            logger.info(f"No value: {value_reason}")
            return None
        
        # Step 4: Check liquidity
        has_liquidity, liquidity_reason = self.check_liquidity(market)
        if not has_liquidity:
            logger.info(f"Liquidity check failed: {liquidity_reason}")
            return None
        
        # Step 5: Check time remaining
        time_ok, time_reason = self.check_time_remaining(match, goal_event)
        if not time_ok:
            logger.info(f"Time check failed: {time_reason}")
            return None
        
        # All checks passed - generate order intent
        pre_prob_str = f"{pre_prob:.2f}" if pre_prob is not None else "N/A"
        reason = (
            f"Underdog {goal_event.scoring_team_name} scored. "
            f"Pre-goal prob: {pre_prob_str}. "
            f"{value_reason}. {liquidity_reason}. {time_reason}."
        )
        
        order_intent = OrderIntent(
            id=str(uuid.uuid4()),
            match_id=match.id,
            market_id=market.id,
            exchange=market.exchange,
            side=OrderSide.BUY,
            outcome="yes",
            size=0,  # Will be set by risk manager
            limit_price=market.yes_price + 0.02,  # Slight premium for faster fill
            reason=reason,
            goal_event_id=goal_event.id
        )
        
        logger.info(f"Generated order intent: {order_intent.id}")
        return order_intent


# Singleton instance
decision_engine = DecisionEngine()
