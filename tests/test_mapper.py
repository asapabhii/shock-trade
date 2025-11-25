"""
Tests for the market mapper.
"""
import pytest
from core.mapper import MarketMapper
from core.models import Match, Team, Market, MatchStatus
from datetime import datetime


class TestMarketMapper:
    """Test suite for MarketMapper."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = MarketMapper()
    
    def test_normalize_team_name(self):
        """Test team name normalization."""
        assert self.mapper._normalize_team_name("Manchester United FC") == "manchester"
        assert self.mapper._normalize_team_name("Liverpool") == "liverpool"
        assert self.mapper._normalize_team_name("Tottenham Hotspur") == "tottenham hotspur"
    
    def test_get_team_aliases(self):
        """Test getting team aliases."""
        aliases = self.mapper._get_team_aliases("Manchester United")
        
        assert "manchester" in aliases or "manchester united" in aliases
    
    def test_similarity_score(self):
        """Test string similarity scoring."""
        # Exact match
        score = self.mapper._similarity_score("liverpool", "liverpool")
        assert score == 1.0
        
        # Similar
        score = self.mapper._similarity_score("liverpool", "liverpol")
        assert score > 0.8
        
        # Different
        score = self.mapper._similarity_score("liverpool", "arsenal")
        assert score < 0.5
    
    def test_match_team_in_text(self):
        """Test matching team name in text."""
        # Direct match
        score = self.mapper._match_team_in_text(
            "Liverpool",
            "Liverpool to win the Premier League"
        )
        assert score >= 0.9
        
        # Full name match
        score = self.mapper._match_team_in_text(
            "Manchester United",
            "Manchester United vs Chelsea"
        )
        assert score >= 0.9
        
        # No match
        score = self.mapper._match_team_in_text(
            "Liverpool",
            "Arsenal vs Chelsea"
        )
        assert score < 0.7
    
    def test_find_markets_for_match_with_cache(self, sample_match):
        """Test finding markets with pre-populated cache."""
        # Pre-populate cache
        self.mapper._market_cache = {
            "all": [
                Market(
                    id="MKT1",
                    exchange="kalshi",
                    title="Manchester United vs Liverpool - Liverpool to win",
                    yes_price=0.35,
                    no_price=0.65
                ),
                Market(
                    id="MKT2",
                    exchange="kalshi",
                    title="Arsenal vs Chelsea",
                    yes_price=0.50,
                    no_price=0.50
                )
            ]
        }
        self.mapper._cache_timestamp = datetime.utcnow()
        
        # This is sync test, so we test the matching logic directly
        all_markets = self.mapper._market_cache["all"]
        matching = []
        
        for market in all_markets:
            search_text = f"{market.title} {market.subtitle or ''}"
            home_score = self.mapper._match_team_in_text(
                sample_match.home_team.name, search_text
            )
            away_score = self.mapper._match_team_in_text(
                sample_match.away_team.name, search_text
            )
            
            if home_score >= 0.7 and away_score >= 0.7:
                matching.append(market)
        
        assert len(matching) == 1
        assert matching[0].id == "MKT1"
    
    def test_cache_validity(self):
        """Test cache validity checking."""
        # No cache
        assert self.mapper._is_cache_valid() is False
        
        # Fresh cache
        self.mapper._cache_timestamp = datetime.utcnow()
        assert self.mapper._is_cache_valid() is True
