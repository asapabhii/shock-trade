"""MLB Data Provider using ESPN API. Free, no key required."""
import httpx
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from sports.base import BaseDataProvider, BaseGame, BaseTeam, BaseScoringEvent, GameStatus


class MLBDataProvider(BaseDataProvider):
    """Fetches live MLB data from ESPN API."""
    
    sport_name = "mlb"
    
    def __init__(self):
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb"
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
        if state == "pre": return GameStatus.SCHEDULED
        elif state == "in": return GameStatus.IN_PROGRESS
        elif state == "post": return GameStatus.FINAL
        return GameStatus.SCHEDULED
    
    def _parse_game(self, event_data: Dict) -> BaseGame:
        competition = event_data.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        home_data = away_data = None
        for comp in competitors:
            if comp.get("homeAway") == "home": home_data = comp
            else: away_data = comp
        
        status_data = event_data.get("status", {})
        try:
            start_time = datetime.fromisoformat(event_data.get("date", "").replace("Z", "+00:00"))
        except:
            start_time = datetime.utcnow()
        
        odds_data = competition.get("odds", [{}])
        spread = over_under = None
        if odds_data and odds_data[0]:
            spread = float(odds_data[0].get("spread", 0)) if odds_data[0].get("spread") else None
            over_under = float(odds_data[0].get("overUnder", 0)) if odds_data[0].get("overUnder") else None
        
        return BaseGame(
            id=int(event_data["id"]),
            sport="mlb",
            home_team=BaseTeam(
                id=int(home_data["team"]["id"]) if home_data else 0,
                name=home_data["team"]["displayName"] if home_data else "Unknown",
                abbreviation=home_data["team"]["abbreviation"] if home_data else "",
                logo=home_data["team"].get("logo") if home_data else None
            ),
            away_team=BaseTeam(
                id=int(away_data["team"]["id"]) if away_data else 0,
                name=away_data["team"]["displayName"] if away_data else "Unknown",
                abbreviation=away_data["team"]["abbreviation"] if away_data else "",
                logo=away_data["team"].get("logo") if away_data else None
            ),
            home_score=int(home_data.get("score", 0)) if home_data else 0,
            away_score=int(away_data.get("score", 0)) if away_data else 0,
            status=self._parse_status(status_data),
            period=status_data.get("period", 0),  # Inning
            clock=status_data.get("displayClock", ""),
            start_time=start_time,
            venue=competition.get("venue", {}).get("fullName"),
            spread=spread, over_under=over_under
        )
    
    async def get_live_games(self) -> List[BaseGame]:
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            games = [self._parse_game(e) for e in response.json().get("events", []) 
                     if self._parse_game(e).status == GameStatus.IN_PROGRESS]
            logger.info(f"Fetched {len(games)} live MLB games")
            return games
        except Exception as e:
            logger.error(f"Error fetching MLB games: {e}")
            return []
    
    async def get_games_today(self) -> List[BaseGame]:
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            games = [self._parse_game(e) for e in response.json().get("events", [])]
            logger.info(f"Fetched {len(games)} MLB games for today")
            return games
        except Exception as e:
            logger.error(f"Error fetching MLB games: {e}")
            return []
    
    async def detect_scoring_events(self, previous_games: Dict[int, BaseGame], current_games: List[BaseGame]) -> List[BaseScoringEvent]:
        events = []
        for game in current_games:
            prev = previous_games.get(game.id)
            if prev is None:
                self._seen_scores[game.id] = {"home": game.home_score, "away": game.away_score}
                continue
            
            for is_home, team, prev_score, curr_score in [
                (True, game.home_team, prev.home_score, game.home_score),
                (False, game.away_team, prev.away_score, game.away_score)
            ]:
                if curr_score > prev_score:
                    runs = curr_score - prev_score
                    event_id = f"mlb-{game.id}-{'home' if is_home else 'away'}-{curr_score}-{game.period}"
                    if event_id not in self._seen_events:
                        self._seen_events.add(event_id)
                        events.append(BaseScoringEvent(
                            id=event_id, game_id=game.id, sport="mlb",
                            timestamp=datetime.utcnow(), period=game.period, clock=game.clock,
                            scoring_team_id=team.id, scoring_team_name=team.name,
                            is_home_team=is_home, points_scored=runs, scoring_type="runs",
                            home_score=game.home_score, away_score=game.away_score
                        ))
                        logger.info(f"MLB RUNS! {team.name} scores {runs}! {game.home_score}-{game.away_score}")
        return events
    
    def clear_cache(self):
        self._seen_events.clear()
        self._seen_scores.clear()

mlb_provider = MLBDataProvider()
