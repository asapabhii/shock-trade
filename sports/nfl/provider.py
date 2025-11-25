"""
NFL Data Provider using ESPN API.

Free, no API key required, no rate limits.
"""
import httpx
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from sports.base import (
    BaseDataProvider, BaseGame, BaseTeam, BaseScoringEvent, GameStatus
)


class NFLDataProvider(BaseDataProvider):
    """
    Fetches live NFL data from ESPN API.
    
    ESPN API is unofficial but reliable and completely free.
    """
    
    sport_name = "nfl"
    
    def __init__(self):
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_scores: Dict[int, Dict[str, int]] = {}
        self._seen_events: set = set()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _parse_status(self, status_data: Dict) -> GameStatus:
        """Convert ESPN status to GameStatus."""
        state = status_data.get("type", {}).get("state", "")
        
        if state == "pre":
            return GameStatus.SCHEDULED
        elif state == "in":
            return GameStatus.IN_PROGRESS
        elif state == "post":
            return GameStatus.FINAL
        
        status_name = status_data.get("type", {}).get("name", "")
        if "HALFTIME" in status_name:
            return GameStatus.HALFTIME
        elif "POSTPONED" in status_name:
            return GameStatus.POSTPONED
        elif "CANCELED" in status_name:
            return GameStatus.CANCELLED
        
        return GameStatus.SCHEDULED
    
    def _parse_game(self, event_data: Dict) -> BaseGame:
        """Parse ESPN event data into BaseGame."""
        competition = event_data.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        home_data = None
        away_data = None
        for comp in competitors:
            if comp.get("homeAway") == "home":
                home_data = comp
            else:
                away_data = comp
        
        # Parse teams
        home_team = BaseTeam(
            id=int(home_data["team"]["id"]) if home_data else 0,
            name=home_data["team"]["displayName"] if home_data else "Unknown",
            abbreviation=home_data["team"]["abbreviation"] if home_data else "",
            logo=home_data["team"].get("logo") if home_data else None
        )
        
        away_team = BaseTeam(
            id=int(away_data["team"]["id"]) if away_data else 0,
            name=away_data["team"]["displayName"] if away_data else "Unknown",
            abbreviation=away_data["team"]["abbreviation"] if away_data else "",
            logo=away_data["team"].get("logo") if away_data else None
        )
        
        # Parse scores
        home_score = int(home_data.get("score", 0)) if home_data else 0
        away_score = int(away_data.get("score", 0)) if away_data else 0
        
        # Parse status
        status_data = event_data.get("status", {})
        status = self._parse_status(status_data)
        period = status_data.get("period", 0)
        clock = status_data.get("displayClock", "")
        
        # Parse start time
        try:
            start_time = datetime.fromisoformat(
                event_data.get("date", "").replace("Z", "+00:00")
            )
        except:
            start_time = datetime.utcnow()
        
        # Get odds
        odds_data = competition.get("odds", [{}])
        spread = None
        over_under = None
        if odds_data:
            odds = odds_data[0] if odds_data else {}
            spread = float(odds.get("spread", 0)) if odds.get("spread") else None
            over_under = float(odds.get("overUnder", 0)) if odds.get("overUnder") else None
        
        return BaseGame(
            id=int(event_data["id"]),
            sport="nfl",
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            status=status,
            period=period,
            clock=clock,
            start_time=start_time,
            venue=competition.get("venue", {}).get("fullName"),
            spread=spread,
            over_under=over_under
        )
    
    async def get_live_games(self) -> List[BaseGame]:
        """Fetch all currently live NFL games."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            data = response.json()
            
            games = []
            for event in data.get("events", []):
                game = self._parse_game(event)
                if game.status in (GameStatus.IN_PROGRESS, GameStatus.HALFTIME):
                    games.append(game)
            
            logger.info(f"Fetched {len(games)} live NFL games")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching NFL games: {e}")
            return []
    
    async def get_games_today(self) -> List[BaseGame]:
        """Fetch all NFL games for today."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            data = response.json()
            
            games = [self._parse_game(event) for event in data.get("events", [])]
            logger.info(f"Fetched {len(games)} NFL games for today")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching NFL games: {e}")
            return []
    
    async def detect_scoring_events(
        self,
        previous_games: Dict[int, BaseGame],
        current_games: List[BaseGame]
    ) -> List[BaseScoringEvent]:
        """Detect new scoring by comparing game states."""
        events = []
        
        for game in current_games:
            prev = previous_games.get(game.id)
            if prev is None:
                self._seen_scores[game.id] = {
                    "home": game.home_score,
                    "away": game.away_score
                }
                continue
            
            # Check for home scoring
            if game.home_score > prev.home_score:
                points = game.home_score - prev.home_score
                event_id = f"nfl-{game.id}-home-{game.home_score}-{game.period}"
                
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    scoring_type = self._determine_scoring_type(points)
                    
                    events.append(BaseScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        sport="nfl",
                        timestamp=datetime.utcnow(),
                        period=game.period,
                        clock=game.clock,
                        scoring_team_id=game.home_team.id,
                        scoring_team_name=game.home_team.name,
                        is_home_team=True,
                        points_scored=points,
                        scoring_type=scoring_type,
                        home_score=game.home_score,
                        away_score=game.away_score
                    ))
                    logger.info(
                        f"NFL SCORE! {game.home_team.name} {scoring_type} (+{points}) "
                        f"{game.home_score}-{game.away_score}"
                    )
            
            # Check for away scoring
            if game.away_score > prev.away_score:
                points = game.away_score - prev.away_score
                event_id = f"nfl-{game.id}-away-{game.away_score}-{game.period}"
                
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    scoring_type = self._determine_scoring_type(points)
                    
                    events.append(BaseScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        sport="nfl",
                        timestamp=datetime.utcnow(),
                        period=game.period,
                        clock=game.clock,
                        scoring_team_id=game.away_team.id,
                        scoring_team_name=game.away_team.name,
                        is_home_team=False,
                        points_scored=points,
                        scoring_type=scoring_type,
                        home_score=game.home_score,
                        away_score=game.away_score
                    ))
                    logger.info(
                        f"NFL SCORE! {game.away_team.name} {scoring_type} (+{points}) "
                        f"{game.home_score}-{game.away_score}"
                    )
        
        return events
    
    def _determine_scoring_type(self, points: int) -> str:
        """Determine scoring type based on points."""
        if points == 6:
            return "touchdown"
        elif points == 7:
            return "touchdown_pat"
        elif points == 8:
            return "touchdown_2pt"
        elif points == 3:
            return "field_goal"
        elif points == 2:
            return "safety"
        elif points == 1:
            return "extra_point"
        return "score"
    
    def clear_cache(self):
        """Clear seen events cache."""
        self._seen_events.clear()
        self._seen_scores.clear()


# Singleton instance
nfl_provider = NFLDataProvider()
