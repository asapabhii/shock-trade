"""
NBA Data Provider using ESPN API.

Free, no API key required.
"""
import httpx
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from sports.base import (
    BaseDataProvider, BaseGame, BaseTeam, BaseScoringEvent, GameStatus
)


class NBADataProvider(BaseDataProvider):
    """Fetches live NBA data from ESPN API."""
    
    sport_name = "nba"
    
    def __init__(self):
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_scores: Dict[int, Dict[str, int]] = {}
        self._seen_events: set = set()
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _parse_status(self, status_data: Dict) -> GameStatus:
        state = status_data.get("type", {}).get("state", "")
        if state == "pre":
            return GameStatus.SCHEDULED
        elif state == "in":
            return GameStatus.IN_PROGRESS
        elif state == "post":
            return GameStatus.FINAL
        return GameStatus.SCHEDULED
    
    def _parse_game(self, event_data: Dict) -> BaseGame:
        competition = event_data.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        home_data = away_data = None
        for comp in competitors:
            if comp.get("homeAway") == "home":
                home_data = comp
            else:
                away_data = comp
        
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
        
        status_data = event_data.get("status", {})
        
        try:
            start_time = datetime.fromisoformat(
                event_data.get("date", "").replace("Z", "+00:00")
            )
        except:
            start_time = datetime.utcnow()
        
        # Get odds
        odds_data = competition.get("odds", [{}])
        spread = over_under = None
        if odds_data:
            odds = odds_data[0] if odds_data else {}
            spread = float(odds.get("spread", 0)) if odds.get("spread") else None
            over_under = float(odds.get("overUnder", 0)) if odds.get("overUnder") else None
        
        return BaseGame(
            id=int(event_data["id"]),
            sport="nba",
            home_team=home_team,
            away_team=away_team,
            home_score=int(home_data.get("score", 0)) if home_data else 0,
            away_score=int(away_data.get("score", 0)) if away_data else 0,
            status=self._parse_status(status_data),
            period=status_data.get("period", 0),
            clock=status_data.get("displayClock", ""),
            start_time=start_time,
            venue=competition.get("venue", {}).get("fullName"),
            spread=spread,
            over_under=over_under
        )
    
    async def get_live_games(self) -> List[BaseGame]:
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            data = response.json()
            
            games = []
            for event in data.get("events", []):
                game = self._parse_game(event)
                if game.status == GameStatus.IN_PROGRESS:
                    games.append(game)
            
            logger.info(f"Fetched {len(games)} live NBA games")
            return games
        except Exception as e:
            logger.error(f"Error fetching NBA games: {e}")
            return []
    
    async def get_games_today(self) -> List[BaseGame]:
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            data = response.json()
            
            games = [self._parse_game(event) for event in data.get("events", [])]
            logger.info(f"Fetched {len(games)} NBA games for today")
            return games
        except Exception as e:
            logger.error(f"Error fetching NBA games: {e}")
            return []
    
    async def detect_scoring_events(
        self,
        previous_games: Dict[int, BaseGame],
        current_games: List[BaseGame]
    ) -> List[BaseScoringEvent]:
        """Detect significant scoring runs (10+ point swings)."""
        events = []
        
        for game in current_games:
            prev = previous_games.get(game.id)
            if prev is None:
                self._seen_scores[game.id] = {
                    "home": game.home_score,
                    "away": game.away_score
                }
                continue
            
            # Calculate score changes
            home_change = game.home_score - prev.home_score
            away_change = game.away_score - prev.away_score
            
            # Detect significant home run (scored 10+ while opponent scored <3)
            if home_change >= 10 and away_change < 3:
                event_id = f"nba-{game.id}-home-run-{game.home_score}"
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    events.append(BaseScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        sport="nba",
                        timestamp=datetime.utcnow(),
                        period=game.period,
                        clock=game.clock,
                        scoring_team_id=game.home_team.id,
                        scoring_team_name=game.home_team.name,
                        is_home_team=True,
                        points_scored=home_change,
                        scoring_type="scoring_run",
                        home_score=game.home_score,
                        away_score=game.away_score
                    ))
                    logger.info(f"NBA RUN! {game.home_team.name} on {home_change}-{away_change} run")
            
            # Detect significant away run
            if away_change >= 10 and home_change < 3:
                event_id = f"nba-{game.id}-away-run-{game.away_score}"
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    events.append(BaseScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        sport="nba",
                        timestamp=datetime.utcnow(),
                        period=game.period,
                        clock=game.clock,
                        scoring_team_id=game.away_team.id,
                        scoring_team_name=game.away_team.name,
                        is_home_team=False,
                        points_scored=away_change,
                        scoring_type="scoring_run",
                        home_score=game.home_score,
                        away_score=game.away_score
                    ))
                    logger.info(f"NBA RUN! {game.away_team.name} on {away_change}-{home_change} run")
        
        return events
    
    def clear_cache(self):
        self._seen_events.clear()
        self._seen_scores.clear()


nba_provider = NBADataProvider()
