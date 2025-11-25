"""
Tests for the decision engine.
"""
import pytest
from datetime import datetime

from core.decision_engine import DecisionEngine
from core.models import Match, Team, GoalEvent, Market, MatchMarketMapping, MatchStatus


class TestDecisionEngine:
    """Test suite for DecisionEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = DecisionEngine()
        self.engine.underdog_threshold = 0.5
        self.engine.min_liquidity = 100
        self.engine.max_price_after_goal = 0.65
        self.engine.min_time_remaining = 15
    
    def test_is_underdog_away_team(self, sample_match, sample_mapping):
        """Test underdog detection for away team."""
        # Away team (Liverpool) has 0.35 pre-goal prob - should be underdog
        is_underdog, prob = self.engine.is_underdog(
            team_id=2,  # Liverpool
            match=sample_match,
            mapping=sample_mapping
        )
        
        assert is_underdog is True
        assert prob == 0.35
    
    def test_is_not_underdog_home_team(self, sample_match, sample_mapping):
        """Test that favorite is not detected as underdog."""
        # Home team (Man Utd) has 0.55 pre-goal prob - not underdog
        is_underdog, prob = self.engine.is_underdog(
            team_id=1,  # Man Utd
            match=sample_match,
            mapping=sample_mapping
        )
        
        assert is_underdog is False
        assert prob == 0.55
    
    def test_check_value_has_value(self, sample_market):
        """Test value detection when price is favorable."""
        # Market at 0.35, pre-goal was 0.35 - still has value
        has_value, reason = self.engine.check_value(sample_market, 0.35)
        
        assert has_value is True
        assert "value" in reason.lower() or "below" in reason.lower()
    
    def test_check_value_no_value_high_price(self, sample_market):
        """Test no value when price is too high."""
        sample_market.yes_price = 0.70  # Above max threshold
        
        has_value, reason = self.engine.check_value(sample_market, 0.35)
        
        assert has_value is False
        assert "too high" in reason.lower()
    
    def test_check_liquidity_sufficient(self, sample_market):
        """Test liquidity check with sufficient volume."""
        has_liquidity, reason = self.engine.check_liquidity(sample_market)
        
        assert has_liquidity is True
        assert "ok" in reason.lower()
    
    def test_check_liquidity_insufficient(self, sample_market):
        """Test liquidity check with insufficient volume."""
        sample_market.yes_volume = 10
        sample_market.no_volume = 10
        
        has_liquidity, reason = self.engine.check_liquidity(sample_market)
        
        assert has_liquidity is False
        assert "insufficient" in reason.lower()
    
    def test_check_time_remaining_ok(self, sample_match, sample_goal_event):
        """Test time check with enough time remaining."""
        sample_goal_event = GoalEvent(
            id="test",
            match_id=sample_match.id,
            timestamp=datetime.utcnow(),
            minute=30,
            scoring_team_id=2,
            scoring_team_name="Liverpool",
            is_home_team=False,
            home_score=0,
            away_score=1
        )
        
        time_ok, reason = self.engine.check_time_remaining(sample_match, sample_goal_event)
        
        assert time_ok is True
        assert "ok" in reason.lower()
    
    def test_check_time_remaining_too_late(self, sample_match):
        """Test time check when too late in match."""
        late_goal = GoalEvent(
            id="test-late",
            match_id=sample_match.id,
            timestamp=datetime.utcnow(),
            minute=85,  # Only 5 mins left
            scoring_team_id=2,
            scoring_team_name="Liverpool",
            is_home_team=False,
            home_score=0,
            away_score=1
        )
        
        time_ok, reason = self.engine.check_time_remaining(sample_match, late_goal)
        
        assert time_ok is False
        assert "not enough" in reason.lower()
    
    def test_evaluate_goal_generates_intent(
        self, sample_match, sample_goal_event, sample_mapping
    ):
        """Test that underdog goal generates order intent."""
        intent = self.engine.evaluate_goal(
            sample_goal_event,
            sample_match,
            sample_mapping
        )
        
        # Should generate intent for underdog goal
        assert intent is not None
        assert intent.market_id == sample_mapping.markets[0].id
        assert intent.side.value == "buy"
        assert "underdog" in intent.reason.lower()
    
    def test_evaluate_goal_no_intent_for_favorite(
        self, sample_match, sample_mapping
    ):
        """Test that favorite goal does not generate intent."""
        # Home team (favorite) scores
        favorite_goal = GoalEvent(
            id="test-fav",
            match_id=sample_match.id,
            timestamp=datetime.utcnow(),
            minute=30,
            scoring_team_id=1,  # Man Utd (favorite)
            scoring_team_name="Manchester United",
            is_home_team=True,
            home_score=1,
            away_score=0
        )
        
        intent = self.engine.evaluate_goal(
            favorite_goal,
            sample_match,
            sample_mapping
        )
        
        assert intent is None
