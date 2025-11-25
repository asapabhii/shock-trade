"""
Fixtures Provider - Fetches upcoming match fixtures.

Used for:
- Pre-caching market mappings before matches start
- Identifying which leagues/teams to monitor
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
from loguru import logger

from config import settings
from core.models import Match, Team, MatchStatus
from data_providers.live_scores import live_scores_provider


class FixturesProvider:
    """
    Fetches and caches upcoming football fixtures.
    
    Helps pre-load market mappings before matches start.
    """
    
    # Popular leagues to monitor (API-Football league IDs)
    MONITORED_LEAGUES = {
        39: "Premier League",
        140: "La Liga",
        135: "Serie A",
        78: "Bundesliga",
        61: "Ligue 1",
        2: "UEFA Champions League",
        3: "UEFA Europa League",
        848: "UEFA Conference League",
        1: "World Cup",
        4: "Euro Championship",
    }
    
    def __init__(self):
        self._fixtures_cache: Dict[date, List[Match]] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    async def get_fixtures_for_date(
        self,
        target_date: date,
        league_ids: Optional[List[int]] = None
    ) -> List[Match]:
        """
        Get fixtures for a specific date.
        
        Args:
            target_date: Date to fetch fixtures for.
            league_ids: Optional list of league IDs to filter.
            
        Returns:
            List of Match objects.
        """
        # Check cache
        if target_date in self._fixtures_cache:
            fixtures = self._fixtures_cache[target_date]
        else:
            fixtures = await live_scores_provider.get_matches_by_date(target_date)
            self._fixtures_cache[target_date] = fixtures
        
        # Filter by league if specified
        if league_ids:
            fixtures = [f for f in fixtures if f.league_id in league_ids]
        
        return fixtures
    
    async def get_todays_fixtures(
        self,
        monitored_only: bool = True
    ) -> List[Match]:
        """
        Get today's fixtures.
        
        Args:
            monitored_only: If True, only return fixtures from monitored leagues.
            
        Returns:
            List of Match objects.
        """
        today = date.today()
        league_ids = list(self.MONITORED_LEAGUES.keys()) if monitored_only else None
        
        return await self.get_fixtures_for_date(today, league_ids)
    
    async def get_upcoming_fixtures(
        self,
        days: int = 3,
        monitored_only: bool = True
    ) -> List[Match]:
        """
        Get fixtures for the next N days.
        
        Args:
            days: Number of days to look ahead.
            monitored_only: If True, only return fixtures from monitored leagues.
            
        Returns:
            List of Match objects sorted by kickoff time.
        """
        all_fixtures = []
        today = date.today()
        league_ids = list(self.MONITORED_LEAGUES.keys()) if monitored_only else None
        
        for i in range(days):
            target_date = today + timedelta(days=i)
            fixtures = await self.get_fixtures_for_date(target_date, league_ids)
            all_fixtures.extend(fixtures)
        
        # Sort by kickoff time
        all_fixtures.sort(key=lambda m: m.kickoff)
        
        return all_fixtures
    
    async def get_fixtures_starting_soon(
        self,
        minutes: int = 60
    ) -> List[Match]:
        """
        Get fixtures starting within the next N minutes.
        
        Args:
            minutes: Time window in minutes.
            
        Returns:
            List of Match objects starting soon.
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(minutes=minutes)
        
        todays_fixtures = await self.get_todays_fixtures()
        
        starting_soon = [
            f for f in todays_fixtures
            if f.status == MatchStatus.NOT_STARTED
            and now <= f.kickoff <= cutoff
        ]
        
        return starting_soon
    
    def clear_cache(self) -> None:
        """Clear the fixtures cache."""
        self._fixtures_cache.clear()
        logger.info("Fixtures cache cleared")
    
    def get_league_name(self, league_id: int) -> str:
        """Get league name by ID."""
        return self.MONITORED_LEAGUES.get(league_id, f"League {league_id}")


# Singleton instance
fixtures_provider = FixturesProvider()
