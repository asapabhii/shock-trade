"""
NFL Live Scores Provider using ESPN API.

ESPN provides free, unofficial access to live NFL scores.
No API key required.
"""
import httpx
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from loguru import logger

from core.models import NFLGame, NFLTeam, NFLGameStatus, NFLScoringEvent


class NFLScoresProvider:
    """
    Fetches live NFL game data from ESPN API.
    
    ESPN API is unofficial but reliable and free.
    """
    
    def __init__(self):
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_scores: Dict[int, Dict[str, int]] = {}  # game_id -> {home: score, away: score}
        self._seen_events: set = set()  # Track seen scoring events
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _parse_game_status(self, status_data: Dict[str, Any]) -> NFLGameStatus:
        """Convert ESPN status to our enum."""
        status_type = status_data.get("type", {}).get("name", "")
        state = status_data.get("type", {}).get("state", "")
        
        if state == "pre":
            return NFLGameStatus.SCHEDULED
        elif state == "in":
            period = status_data.get("period", 1)
            if period == 1:
                return NFLGameStatus.FIRST_QUARTER
            elif period == 2:
                return NFLGameStatus.SECOND_QUARTER
            elif period == 3:
                return NFLGameStatus.THIRD_QUARTER
            elif period == 4:
                return NFLGameStatus.FOURTH_QUARTER
            elif period >= 5:
                return NFLGameStatus.OVERTIME
            return NFLGameStatus.IN_PROGRESS
        elif state == "post":
            return NFLGameStatus.FINAL
        elif status_type == "STATUS_HALFTIME":
            return NFLGameStatus.HALFTIME
        elif status_type == "STATUS_POSTPONED":
            return NFLGameStatus.POSTPONED
        elif status_type == "STATUS_CANCELED":
            return NFLGameStatus.CANCELLED
        
        return NFLGameStatus.SCHEDULED
    
    def _parse_game(self, event_data: Dict[str, Any]) -> NFLGame:
        """Parse ESPN event data into NFLGame model."""
        competition = event_data.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        home_team_data = None
        away_team_data = None
        
        for comp in competitors:
            if comp.get("homeAway") == "home":
                home_team_data = comp
            else:
                away_team_data = comp
        
        # Parse teams
        home_team = NFLTeam(
            id=int(home_team_data["team"]["id"]),
            name=home_team_data["team"]["displayName"],
            abbreviation=home_team_data["team"]["abbreviation"],
            logo=home_team_data["team"].get("logo")
        ) if home_team_data else NFLTeam(id=0, name="Unknown", abbreviation="UNK")
        
        away_team = NFLTeam(
            id=int(away_team_data["team"]["id"]),
            name=away_team_data["team"]["displayName"],
            abbreviation=away_team_data["team"]["abbreviation"],
            logo=away_team_data["team"].get("logo")
        ) if away_team_data else NFLTeam(id=0, name="Unknown", abbreviation="UNK")
        
        # Parse scores
        home_score = int(home_team_data.get("score", 0)) if home_team_data else 0
        away_score = int(away_team_data.get("score", 0)) if away_team_data else 0
        
        # Parse status
        status_data = event_data.get("status", {})
        status = self._parse_game_status(status_data)
        
        # Parse time info
        clock = status_data.get("displayClock", "0:00")
        quarter = status_data.get("period", 0)
        
        # Parse kickoff time
        kickoff_str = event_data.get("date", "")
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except:
            kickoff = datetime.utcnow()
        
        # Get odds/spread if available
        odds_data = competition.get("odds", [{}])
        spread = None
        over_under = None
        if odds_data:
            odds = odds_data[0] if odds_data else {}
            spread = odds.get("spread")
            over_under = odds.get("overUnder")
        
        return NFLGame(
            id=int(event_data["id"]),
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            status=status,
            quarter=quarter,
            clock=clock,
            kickoff=kickoff,
            venue=competition.get("venue", {}).get("fullName"),
            spread=float(spread) if spread else None,
            over_under=float(over_under) if over_under else None,
            week=event_data.get("week", {}).get("number")
        )

    async def get_live_games(self) -> List[NFLGame]:
        """
        Fetch all currently live NFL games.
        
        Returns:
            List of NFLGame objects for live games.
        """
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/scoreboard")
            response.raise_for_status()
            data = response.json()
            
            games = []
            for event in data.get("events", []):
                game = self._parse_game(event)
                # Include games that are in progress or about to start
                if game.status not in (NFLGameStatus.FINAL, NFLGameStatus.CANCELLED, NFLGameStatus.POSTPONED):
                    games.append(game)
            
            logger.info(f"Fetched {len(games)} live/upcoming NFL games")
            return games
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching NFL games: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching NFL games: {e}")
            return []
    
    async def get_all_games_today(self) -> List[NFLGame]:
        """
        Fetch all NFL games for today (including finished).
        
        Returns:
            List of NFLGame objects.
        """
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
    
    async def get_games_by_week(self, season: int, week: int, season_type: int = 2) -> List[NFLGame]:
        """
        Fetch NFL games for a specific week.
        
        Args:
            season: Year (e.g., 2024)
            week: Week number (1-18 for regular season)
            season_type: 1=preseason, 2=regular, 3=postseason
            
        Returns:
            List of NFLGame objects.
        """
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.base_url}/scoreboard",
                params={
                    "seasontype": season_type,
                    "week": week,
                    "dates": season
                }
            )
            response.raise_for_status()
            data = response.json()
            
            games = [self._parse_game(event) for event in data.get("events", [])]
            logger.info(f"Fetched {len(games)} NFL games for week {week}")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching NFL games for week {week}: {e}")
            return []
    
    async def detect_scoring_events(
        self,
        previous_games: Dict[int, NFLGame],
        current_games: List[NFLGame]
    ) -> List[NFLScoringEvent]:
        """
        Compare previous and current game states to detect new scoring.
        
        Args:
            previous_games: Dict of game_id -> NFLGame from last poll.
            current_games: List of current NFLGame objects.
            
        Returns:
            List of newly detected NFLScoringEvent objects.
        """
        scoring_events = []
        
        for game in current_games:
            prev = previous_games.get(game.id)
            
            if prev is None:
                # New game we haven't seen - initialize tracking
                self._seen_scores[game.id] = {
                    "home": game.home_score,
                    "away": game.away_score
                }
                continue
            
            # Check for home team scoring
            if game.home_score > prev.home_score:
                points_scored = game.home_score - prev.home_score
                event_id = f"{game.id}-home-{game.home_score}-{game.quarter}-{game.clock}"
                
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    
                    # Determine scoring type based on points
                    scoring_type = self._determine_scoring_type(points_scored)
                    
                    event = NFLScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        timestamp=datetime.utcnow(),
                        quarter=game.quarter,
                        clock=game.clock,
                        scoring_team_id=game.home_team.id,
                        scoring_team_name=game.home_team.name,
                        is_home_team=True,
                        points_scored=points_scored,
                        scoring_type=scoring_type,
                        home_score=game.home_score,
                        away_score=game.away_score
                    )
                    scoring_events.append(event)
                    logger.info(
                        f"SCORE! {game.home_team.name} {scoring_type} (+{points_scored}) "
                        f"{game.home_score}-{game.away_score} Q{game.quarter} {game.clock}"
                    )
            
            # Check for away team scoring
            if game.away_score > prev.away_score:
                points_scored = game.away_score - prev.away_score
                event_id = f"{game.id}-away-{game.away_score}-{game.quarter}-{game.clock}"
                
                if event_id not in self._seen_events:
                    self._seen_events.add(event_id)
                    
                    scoring_type = self._determine_scoring_type(points_scored)
                    
                    event = NFLScoringEvent(
                        id=event_id,
                        game_id=game.id,
                        timestamp=datetime.utcnow(),
                        quarter=game.quarter,
                        clock=game.clock,
                        scoring_team_id=game.away_team.id,
                        scoring_team_name=game.away_team.name,
                        is_home_team=False,
                        points_scored=points_scored,
                        scoring_type=scoring_type,
                        home_score=game.home_score,
                        away_score=game.away_score
                    )
                    scoring_events.append(event)
                    logger.info(
                        f"SCORE! {game.away_team.name} {scoring_type} (+{points_scored}) "
                        f"{game.home_score}-{game.away_score} Q{game.quarter} {game.clock}"
                    )
        
        return scoring_events
    
    def _determine_scoring_type(self, points: int) -> str:
        """Determine the type of scoring play based on points."""
        if points == 6:
            return "touchdown"
        elif points == 7:
            return "touchdown_pat"  # TD + extra point
        elif points == 8:
            return "touchdown_2pt"  # TD + 2-point conversion
        elif points == 3:
            return "field_goal"
        elif points == 2:
            return "safety"
        elif points == 1:
            return "extra_point"
        else:
            return "score"
    
    def clear_seen_events(self):
        """Clear the seen events cache."""
        self._seen_events.clear()
        self._seen_scores.clear()


# Singleton instance
nfl_scores_provider = NFLScoresProvider()
