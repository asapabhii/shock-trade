"""
Pytest configuration and fixtures.
"""
import pytest
from datetime import datetime

from core.models import (
    Match, Team, GoalEvent, Market, MatchMarketMapping,
    OrderIntent, OrderSide, MatchStatus
)


@pytest.fixture
def sample_match():
    """Create a sample match for testing."""
    return Match(
        id=12345,
        league_id=39,
        league_name="Premier League",
        home_team=Team(id=1, name="Manchester United"),
        away_team=Team(id=2, name="Liverpool"),
        home_score=0,
        away_score=0,
        status=MatchStatus.FIRST_HALF,
        minute=25,
        kickoff=datetime(2024, 1, 15, 15, 0, 0)
    )


@pytest.fixture
def sample_goal_event(sample_match):
    """Create a sample goal event."""
    return GoalEvent(
        id="12345-away-1-30",
        match_id=sample_match.id,
        timestamp=datetime.utcnow(),
        minute=30,
        scoring_team_id=2,  # Liverpool (away)
        scoring_team_name="Liverpool",
        is_home_team=False,
        home_score=0,
        away_score=1
    )


@pytest.fixture
def sample_market():
    """Create a sample market."""
    return Market(
        id="SOCCER-EPL-MUFC-LIV-WIN",
        exchange="kalshi",
        title="Liverpool to win vs Manchester United",
        yes_price=0.35,
        no_price=0.65,
        yes_volume=5000,
        no_volume=3000,
        status="open"
    )


@pytest.fixture
def sample_mapping(sample_match, sample_market):
    """Create a sample market mapping."""
    return MatchMarketMapping(
        match_id=sample_match.id,
        home_team_name=sample_match.home_team.name,
        away_team_name=sample_match.away_team.name,
        league_name=sample_match.league_name,
        kickoff=sample_match.kickoff,
        markets=[sample_market],
        pre_goal_home_prob=0.55,
        pre_goal_away_prob=0.35
    )


@pytest.fixture
def sample_order_intent(sample_match, sample_market, sample_goal_event):
    """Create a sample order intent."""
    return OrderIntent(
        id="intent-123",
        match_id=sample_match.id,
        market_id=sample_market.id,
        exchange="kalshi",
        side=OrderSide.BUY,
        outcome="yes",
        size=50.0,
        limit_price=0.37,
        reason="Underdog Liverpool scored",
        goal_event_id=sample_goal_event.id
    )
