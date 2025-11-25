"""
Soccer Data Provider using Football-Data.org API.

Free tier: 10 requests/minute, no daily limit.
Covers: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League
"""
import httpx
from datetime import datetime, date
from typing import List, Dict, Optional
from loguru import logger

from config import settings
from sports.base import (
    BaseDataProvider, BaseGame, BaseTeam, BaseScoringEvent, GameStatus
)


class SoccerDataProvider(BaseDataProvider):
    """
    Fetches live soccer data from Football-Data.org.
    
    API Documentation: https://www.football-data.org/documentation/quickstart
    """
    
    sport_name = "soccer"
    
    # Competition IDs for major leagues
    COMPETITIONS = {
        "PL": "Premier League",
        "PD": "La Liga", 
        "BL1": "Bundesliga",
        "SA": "Serie A",
        "FL1": "Ligue 1",
        "CL": "Champions League",
        "EC": "European Championship",
        "WC": "World Cup"
    }
    
    def __init__(self):
        self.base_url = "https://api.football-data.org/v4"
        self.api_key = getattr(settings, 'football_data_api_key', '')
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_scores: Dict[int, Dict[str, int]] = {}
        self._seen_events: set = set()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"X-Auth-Token": self.api_key} if self.api_key else {}
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _parse_status(self, status: str) -> GameStatus:
        """Convert API status to GameStatus."""
        status_map = {
            "SCHEDULED": GameStatus.SCHEDULED,
            "TIMED": GameStatus.SCHEDULED,
            "IN_PLAY": GameStatus.IN_PROGRESS,
            "PAUSED": GameStatus.HALFTIME,
            "HALFTIME": GameStatus.HALFTIME,
            "FINISHED": GameStatus.FINAL,
            "POSTPONED": GameStatus.POSTPONED,
            "CANCELLED": GameStatus.CANCELLED,
            "SUSPENDED": GameStatus.POSTPONED,
        }
        return status_map.get(status, GameStatus.SCHEDULED)
    
    def _parse_game(self, match_data: Dict) -> BaseGame:
        """Parse API match data into BaseGame."""
        home = match_data.get("homeTeam", {})
        away = match_data.get("awayTeam", {})
        score = match_data.get("score", {})
        full_time = score.get("fullTime", {}) or {}
        
        # Parse kickoff time
        utc_date = match_data.get("utcDate", "")
        try:
            start_time = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
        except:
            start_time = datetime.utcnow()
        
        # Determine period based on status
        status = self._parse_status(match_data.get("status", "SCHEDULED"))
        period = 0
        if status == GameStatus.IN_PROGRESS:
            # Football-Data doesn't give exact minute in free tier
            period = 1
        elif status == GameStatus.HALFTIME:
            period = 1
        elif status == GameStatus.FINAL:
            period = 2
        
        return BaseGame(
            id=match_data.get("id", 0),
            sport="soccer",
            home_team=BaseTeam(
                id=home.get("id", 0),
                name=home.get("name", "Unknown"),
                abbreviation=home.get("tla", ""),
                logo=home.get("crest")
            ),
            away_team=BaseTeam(
                id=away.get("id", 0),
                name=away.get("name", "Unknown"),
                abbreviation=away.get("tla", ""),
                logo=away.get("crest")
            ),
            home_score=full_time.get("home") or 0,
            away_score=full_time.get("away") or 0,
            status=status,
            period=period,
            clock="",
            start_time=start_time,
            venue=match_data.get("venue")
        )
    
    async def get_live_games(self) -> List[BaseGame]:
        """Fetch all currently live soccer matches."""
        if not self.api_key:
            logger.warning("Football-Data.org API key not configured")
            return []
        
        client = await self._get_client()
        
        try:
            # Get today's matches and filter for live ones
            response = await client.get(
                f"{self.base_url}/matches",
                params={"status": "IN_PLAY,PAUSED"}
            )
            
            if response.status_code == 429:
                logger.warning("Football-Data.org rate limit hit")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            games = [self._parse_game(m) for m in data.get("matches", [])]
            logger.info(f"Fetched {len(games)} live soccer matches")
            return games
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching soccer matches: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching soccer matches: {e}")
            return []
    
    async def get_games_today(self) -> List[BaseGame]:
        """Fetch all soccer matches for today."""
        if not self.api_key:
            logger.warning("Football-Data.org API key not configured")
            return []
        
        client = await self._get_client()
        
        try:
            today = date.today().isoformat()
            response = await client.get(
                f"{self.base_url}/matches",
                params={"dateFrom": today, "dateTo": today}
            )
            
            if response.status_code == 429:
                logger.warning("Football-Data.org rate limit hit")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            games = [self._parse_game(m) for m in data.get("matches", [])]
            logger.info(f"Fetched {len(games)} soccer matches for today")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching soccer matches: {e}")
            return []
    
    async def detect_scoring_events(
        self,
        previous_games: Dict[int, BaseGame],
        current_games: List[BaseGame]
    ) -> List[BaseScoringEvent]:
        """Detect new goals by comparing game states."""
        events = []
        
        for game in current_games:
            prev = previous_games.get(game.id)
            if prev is None:
                self._seen_scores[game.id] = {
                    "home": game.home_score,
                    "away": game.away_score
                }
                continue
            
            # Check for home goal
            if game.home_score > prev.home_score:
                event_id = f"soccer-{game.id}-home-{game.home_score}"
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    events.append(BaseScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        sport="soccer",
                        timestamp=datetime.utcnow(),
                        period=game.period,
                        clock=game.clock,
                        scoring_team_id=game.home_team.id,
                        scoring_team_name=game.home_team.name,
                        is_home_team=True,
                        points_scored=1,
                        scoring_type="goal",
                        home_score=game.home_score,
                        away_score=game.away_score
                    ))
                    logger.info(f"GOAL! {game.home_team.name} scores! {game.home_score}-{game.away_score}")
            
            # Check for away goal
            if game.away_score > prev.away_score:
                event_id = f"soccer-{game.id}-away-{game.away_score}"
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    events.append(BaseScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        sport="soccer",
                        timestamp=datetime.utcnow(),
                        period=game.period,
                        clock=game.clock,
                        scoring_team_id=game.away_team.id,
                        scoring_team_name=game.away_team.name,
                        is_home_team=False,
                        points_scored=1,
                        scoring_type="goal",
                        home_score=game.home_score,
                        away_score=game.away_score
                    ))
                    logger.info(f"GOAL! {game.away_team.name} scores! {game.home_score}-{game.away_score}")
        
        return events
    
    def clear_cache(self):
        """Clear seen events cache."""
        self._seen_events.clear()
        self._seen_scores.clear()


# Singleton instance
soccer_provider = SoccerDataProvider()
