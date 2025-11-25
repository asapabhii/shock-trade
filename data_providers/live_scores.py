"""
Live football scores provider using API-Football via RapidAPI.
Free tier: 100 requests/day - use wisely!
"""
import httpx
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from loguru import logger

from config import settings
from core.models import Match, Team, MatchStatus, GoalEvent


class LiveScoresProvider:
    """
    Fetches live football match data from API-Football.
    
    API Documentation: https://www.api-football.com/documentation-v3
    """
    
    def __init__(self):
        # Support both RapidAPI and direct API-Sports endpoints
        if "api-sports.io" in settings.rapidapi_host:
            self.base_url = f"https://{settings.rapidapi_host}"
            self.headers = {
                "x-apisports-key": settings.rapidapi_key
            }
        else:
            self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
            self.headers = {
                "X-RapidAPI-Key": settings.rapidapi_key,
                "X-RapidAPI-Host": settings.rapidapi_host
            }
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_goals: set = set()  # Track seen goal events for deduplication
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _parse_match_status(self, short: str, elapsed: Optional[int]) -> MatchStatus:
        """Convert API status to our enum."""
        status_map = {
            "TBD": MatchStatus.NOT_STARTED,
            "NS": MatchStatus.NOT_STARTED,
            "1H": MatchStatus.FIRST_HALF,
            "HT": MatchStatus.HALFTIME,
            "2H": MatchStatus.SECOND_HALF,
            "ET": MatchStatus.EXTRA_TIME,
            "P": MatchStatus.PENALTIES,
            "PEN": MatchStatus.PENALTIES,
            "FT": MatchStatus.FINISHED,
            "AET": MatchStatus.FINISHED,
            "PST": MatchStatus.POSTPONED,
            "CANC": MatchStatus.CANCELLED,
            "ABD": MatchStatus.ABANDONED,
            "SUSP": MatchStatus.SUSPENDED,
            "INT": MatchStatus.SUSPENDED,
            "LIVE": MatchStatus.LIVE,
        }
        return status_map.get(short, MatchStatus.NOT_STARTED)
    
    def _parse_match(self, fixture_data: Dict[str, Any]) -> Match:
        """Parse API response into Match model."""
        fixture = fixture_data["fixture"]
        league = fixture_data["league"]
        teams = fixture_data["teams"]
        goals = fixture_data["goals"]
        
        # Parse kickoff time
        kickoff = datetime.fromisoformat(
            fixture["date"].replace("Z", "+00:00")
        )
        
        status = self._parse_match_status(
            fixture["status"]["short"],
            fixture["status"].get("elapsed")
        )
        
        return Match(
            id=fixture["id"],
            league_id=league["id"],
            league_name=league["name"],
            home_team=Team(
                id=teams["home"]["id"],
                name=teams["home"]["name"],
                logo=teams["home"].get("logo")
            ),
            away_team=Team(
                id=teams["away"]["id"],
                name=teams["away"]["name"],
                logo=teams["away"].get("logo")
            ),
            home_score=goals["home"] or 0,
            away_score=goals["away"] or 0,
            status=status,
            minute=fixture["status"].get("elapsed"),
            kickoff=kickoff,
            venue=fixture.get("venue", {}).get("name")
        )
    
    async def get_live_matches(self) -> List[Match]:
        """
        Fetch all currently live matches.
        
        Returns:
            List of Match objects for live games.
        """
        if not settings.rapidapi_key:
            logger.warning("RapidAPI key not configured - returning empty list")
            return []
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.base_url}/fixtures",
                params={"live": "all"}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("errors"):
                logger.error(f"API-Football errors: {data['errors']}")
                return []
            
            matches = [
                self._parse_match(fixture)
                for fixture in data.get("response", [])
            ]
            
            logger.info(f"Fetched {len(matches)} live matches")
            return matches
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching live matches: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching live matches: {e}")
            return []
    
    async def get_matches_by_date(self, match_date: date) -> List[Match]:
        """
        Fetch matches for a specific date.
        
        Args:
            match_date: Date to fetch matches for.
            
        Returns:
            List of Match objects.
        """
        if not settings.rapidapi_key:
            logger.warning("RapidAPI key not configured - returning empty list")
            return []
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.base_url}/fixtures",
                params={"date": match_date.isoformat()}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("errors"):
                logger.error(f"API-Football errors: {data['errors']}")
                return []
            
            matches = [
                self._parse_match(fixture)
                for fixture in data.get("response", [])
            ]
            
            logger.info(f"Fetched {len(matches)} matches for {match_date}")
            return matches
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching matches: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching matches: {e}")
            return []
    
    async def get_match_events(self, match_id: int) -> List[Dict[str, Any]]:
        """
        Fetch events (goals, cards, subs) for a specific match.
        
        Args:
            match_id: The fixture ID.
            
        Returns:
            List of event dictionaries.
        """
        if not settings.rapidapi_key:
            return []
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.base_url}/fixtures/events",
                params={"fixture": match_id}
            )
            response.raise_for_status()
            data = response.json()
            
            return data.get("response", [])
            
        except Exception as e:
            logger.error(f"Error fetching match events for {match_id}: {e}")
            return []
    
    async def detect_new_goals(
        self,
        previous_matches: Dict[int, Match],
        current_matches: List[Match]
    ) -> List[GoalEvent]:
        """
        Compare previous and current match states to detect new goals.
        
        Args:
            previous_matches: Dict of match_id -> Match from last poll.
            current_matches: List of current Match objects.
            
        Returns:
            List of newly detected GoalEvent objects.
        """
        new_goals = []
        
        for match in current_matches:
            prev = previous_matches.get(match.id)
            
            if prev is None:
                # New match we haven't seen - skip
                continue
            
            # Check for home team goal
            if match.home_score > prev.home_score:
                goals_scored = match.home_score - prev.home_score
                for i in range(goals_scored):
                    event_id = f"{match.id}-home-{match.home_score - goals_scored + i + 1}-{match.minute}"
                    
                    if event_id not in self._seen_goals:
                        self._seen_goals.add(event_id)
                        goal = GoalEvent(
                            id=event_id,
                            match_id=match.id,
                            timestamp=datetime.utcnow(),
                            minute=match.minute or 0,
                            scoring_team_id=match.home_team.id,
                            scoring_team_name=match.home_team.name,
                            is_home_team=True,
                            home_score=prev.home_score + i + 1,
                            away_score=match.away_score
                        )
                        new_goals.append(goal)
                        logger.info(
                            f"⚽ GOAL! {match.home_team.name} scores! "
                            f"{goal.home_score}-{goal.away_score} ({match.minute}')"
                        )
            
            # Check for away team goal
            if match.away_score > prev.away_score:
                goals_scored = match.away_score - prev.away_score
                for i in range(goals_scored):
                    event_id = f"{match.id}-away-{match.away_score - goals_scored + i + 1}-{match.minute}"
                    
                    if event_id not in self._seen_goals:
                        self._seen_goals.add(event_id)
                        goal = GoalEvent(
                            id=event_id,
                            match_id=match.id,
                            timestamp=datetime.utcnow(),
                            minute=match.minute or 0,
                            scoring_team_id=match.away_team.id,
                            scoring_team_name=match.away_team.name,
                            is_home_team=False,
                            home_score=match.home_score,
                            away_score=prev.away_score + i + 1
                        )
                        new_goals.append(goal)
                        logger.info(
                            f"⚽ GOAL! {match.away_team.name} scores! "
                            f"{goal.home_score}-{goal.away_score} ({match.minute}')"
                        )
        
        return new_goals
    
    def clear_seen_goals(self):
        """Clear the seen goals cache (e.g., at start of new day)."""
        self._seen_goals.clear()


# Singleton instance
live_scores_provider = LiveScoresProvider()
