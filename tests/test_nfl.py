"""
Tests for NFL-specific functionality.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from core.models import (
    NFLGame, NFLTeam, NFLScoringEvent, NFLGameStatus,
    NFLGameMarketMapping, Market, OrderSide
)
from core.nfl_decision_engine import NFLDecisionEngine
from core.nfl_mapper import NFLMarketMapper
from core.state import StateManager


class TestNFLDecisionEngine:
    """Tests for NFL decision engine."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.engine = NFLDecisionEngine()
        
        # Create test teams
        self.home_team = NFLTeam(
            id=1,
            name="Kansas City Chiefs",
            abbreviation="KC"
        )
        self.away_team = NFLTeam(
            id=2,
            name="Las Vegas Raiders",
            abbreviation="LV"
        )
        
        # Create test game
        self.game = NFLGame(
            id=12345,
            home_team=self.home_team,
            away_team=self.away_team,
            home_score=14,
            away_score=7,
            status=NFLGameStatus.SECOND_QUARTER,
            quarter=2,
            clock="8:30",
            kickoff=datetime.utcnow(),
            spread=-7.5,  # Chiefs favored by 7.5
            over_under=48.5
        )
        
        # Create test market
        self.market = Market(
            id="NFL-RAIDERS-WIN",
            exchange="kalshi",
            title="Las Vegas Raiders to win",
            yes_price=0.35,
            no_price=0.65,
            yes_volume=500,
            no_volume=500,
            status="open"
        )
        
        # Create test mapping
        self.mapping = NFLGameMarketMapping(
            game_id=12345,
            home_team_name="Kansas City Chiefs",
            away_team_name="Las Vegas Raiders",
            kickoff=datetime.utcnow(),
            markets=[self.market],
            pre_score_home_prob=0.70,
            pre_score_away_prob=0.30,
            spread=-7.5
        )
    
    def test_is_underdog_away_team_with_spread(self):
        """Test underdog detection for away team with negative spread."""
        # Raiders are underdogs (Chiefs favored by 7.5)
        is_underdog, spread_val, reason = self.engine.is_underdog(
            self.away_team.id, self.game, self.mapping
        )
        
        assert is_underdog is True
        assert "Spread" in reason
    
    def test_is_not_underdog_home_team_with_spread(self):
        """Test that home favorite is not underdog."""
        # Chiefs are favorites
        is_underdog, spread_val, reason = self.engine.is_underdog(
            self.home_team.id, self.game, self.mapping
        )
        
        assert is_underdog is False
    
    def test_check_value_has_value(self):
        """Test value detection when price is low."""
        has_value, reason = self.engine.check_value(
            self.market, 0.30, is_underdog=True
        )
        
        assert has_value is True
        assert "Value" in reason or "below 50%" in reason
    
    def test_check_value_no_value_high_price(self):
        """Test no value when price is too high."""
        high_price_market = Market(
            id="test",
            exchange="kalshi",
            title="Test",
            yes_price=0.75,
            no_price=0.25,
            yes_volume=100,
            no_volume=100
        )
        
        has_value, reason = self.engine.check_value(
            high_price_market, 0.30, is_underdog=True
        )
        
        assert has_value is False
        assert "too high" in reason
    
    def test_check_time_remaining_ok(self):
        """Test time check passes in early quarters."""
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=2,
            clock="8:30",
            scoring_team_id=2,
            scoring_team_name="Las Vegas Raiders",
            is_home_team=False,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=14,
            away_score=14
        )
        
        time_ok, reason = self.engine.check_time_remaining(self.game, event)
        
        assert time_ok is True
        assert "Q2" in reason
    
    def test_check_time_remaining_too_late(self):
        """Test time check fails in 4th quarter."""
        late_game = NFLGame(
            id=12345,
            home_team=self.home_team,
            away_team=self.away_team,
            home_score=21,
            away_score=14,
            status=NFLGameStatus.FOURTH_QUARTER,
            quarter=4,
            clock="5:00",
            kickoff=datetime.utcnow()
        )
        
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=4,
            clock="5:00",
            scoring_team_id=2,
            scoring_team_name="Las Vegas Raiders",
            is_home_team=False,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=21,
            away_score=21
        )
        
        time_ok, reason = self.engine.check_time_remaining(late_game, event)
        
        assert time_ok is False
        assert "Q4" in reason
    
    def test_check_score_differential_competitive(self):
        """Test score differential check for competitive game."""
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=2,
            clock="8:30",
            scoring_team_id=2,
            scoring_team_name="Las Vegas Raiders",
            is_home_team=False,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=14,
            away_score=14
        )
        
        diff_ok, reason = self.engine.check_score_differential(self.game, event)
        
        assert diff_ok is True
        assert "Competitive" in reason or "differential" in reason
    
    def test_check_score_differential_blowout(self):
        """Test score differential check rejects blowouts."""
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=3,
            clock="10:00",
            scoring_team_id=2,
            scoring_team_name="Las Vegas Raiders",
            is_home_team=False,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=42,
            away_score=14
        )
        
        diff_ok, reason = self.engine.check_score_differential(self.game, event)
        
        assert diff_ok is False
        assert "Blowout" in reason
    
    def test_evaluate_scoring_event_generates_intent(self):
        """Test that underdog TD generates order intent."""
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=2,
            clock="8:30",
            scoring_team_id=2,  # Raiders (underdog)
            scoring_team_name="Las Vegas Raiders",
            is_home_team=False,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=14,
            away_score=14
        )
        
        intent = self.engine.evaluate_scoring_event(event, self.game, self.mapping)
        
        assert intent is not None
        assert intent.side == OrderSide.BUY
        assert "Underdog" in intent.reason
    
    def test_evaluate_scoring_event_no_intent_for_favorite(self):
        """Test that favorite TD does not generate intent."""
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=2,
            clock="8:30",
            scoring_team_id=1,  # Chiefs (favorite)
            scoring_team_name="Kansas City Chiefs",
            is_home_team=True,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=21,
            away_score=7
        )
        
        intent = self.engine.evaluate_scoring_event(event, self.game, self.mapping)
        
        assert intent is None
    
    def test_evaluate_scoring_event_no_intent_for_field_goal(self):
        """Test that field goal (3 pts) does not generate intent."""
        event = NFLScoringEvent(
            id="test-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=2,
            clock="8:30",
            scoring_team_id=2,  # Raiders (underdog)
            scoring_team_name="Las Vegas Raiders",
            is_home_team=False,
            points_scored=3,  # Field goal
            scoring_type="field_goal",
            home_score=14,
            away_score=10
        )
        
        intent = self.engine.evaluate_scoring_event(event, self.game, self.mapping)
        
        assert intent is None  # Field goals don't trigger trades


class TestNFLMarketMapper:
    """Tests for NFL market mapper."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mapper = NFLMarketMapper()
    
    def test_normalize_team_name(self):
        """Test team name normalization."""
        assert self.mapper._normalize_team_name("Kansas City Chiefs") == "kansas city chiefs"
        assert self.mapper._normalize_team_name("  Green Bay Packers  ") == "green bay packers"
    
    def test_get_team_aliases(self):
        """Test team alias lookup."""
        aliases = self.mapper._get_team_aliases("Kansas City Chiefs")
        
        assert "kansas city chiefs" in aliases
        assert "chiefs" in aliases
        assert "kc" in aliases
    
    def test_match_team_in_text(self):
        """Test team matching in market text."""
        score = self.mapper._match_team_in_text(
            "Kansas City Chiefs",
            "Will the Chiefs win against the Raiders?"
        )
        
        assert score >= 0.9  # Should find "Chiefs"
    
    def test_match_team_in_text_no_match(self):
        """Test team matching returns low score for no match."""
        score = self.mapper._match_team_in_text(
            "Kansas City Chiefs",
            "Will the Lakers win the NBA championship?"
        )
        
        assert score < 0.5


class TestNFLStateManager:
    """Tests for NFL state management."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.state = StateManager()
        self.state.reset()
        
        self.game = NFLGame(
            id=12345,
            home_team=NFLTeam(id=1, name="Chiefs", abbreviation="KC"),
            away_team=NFLTeam(id=2, name="Raiders", abbreviation="LV"),
            home_score=14,
            away_score=7,
            status=NFLGameStatus.SECOND_QUARTER,
            quarter=2,
            clock="8:30",
            kickoff=datetime.utcnow()
        )
    
    def test_update_nfl_games(self):
        """Test NFL game state updates."""
        self.state.update_nfl_games([self.game])
        
        assert len(self.state.get_all_nfl_games()) == 1
        assert self.state.get_nfl_game(12345) is not None
    
    def test_get_live_nfl_games(self):
        """Test filtering for live NFL games."""
        finished_game = NFLGame(
            id=99999,
            home_team=NFLTeam(id=3, name="Bills", abbreviation="BUF"),
            away_team=NFLTeam(id=4, name="Dolphins", abbreviation="MIA"),
            home_score=24,
            away_score=21,
            status=NFLGameStatus.FINAL,
            quarter=4,
            clock="0:00",
            kickoff=datetime.utcnow()
        )
        
        self.state.update_nfl_games([self.game, finished_game])
        
        live_games = self.state.get_live_nfl_games()
        assert len(live_games) == 1
        assert live_games[0].id == 12345
    
    def test_nfl_score_processing(self):
        """Test NFL score event tracking."""
        event = NFLScoringEvent(
            id="test-score-1",
            game_id=12345,
            timestamp=datetime.utcnow(),
            quarter=2,
            clock="8:30",
            scoring_team_id=2,
            scoring_team_name="Raiders",
            is_home_team=False,
            points_scored=7,
            scoring_type="touchdown_pat",
            home_score=14,
            away_score=14
        )
        
        assert not self.state.is_nfl_score_processed(event.id)
        
        self.state.mark_nfl_score_processed(event)
        
        assert self.state.is_nfl_score_processed(event.id)
        assert len(self.state.get_nfl_score_history()) == 1
