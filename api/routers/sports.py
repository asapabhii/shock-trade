"""
Unified Sports API router - All sports in one place.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from loguru import logger

router = APIRouter()


class TeamResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    logo: Optional[str] = None


class GameResponse(BaseModel):
    id: int
    sport: str
    home_team: TeamResponse
    away_team: TeamResponse
    home_score: int
    away_score: int
    status: str
    period: int
    clock: str
    start_time: datetime
    venue: Optional[str] = None
    spread: Optional[float] = None
    over_under: Optional[float] = None
    has_open_position: bool = False


class ScoringEventResponse(BaseModel):
    id: str
    game_id: int
    sport: str
    timestamp: datetime
    period: int
    clock: str
    scoring_team: str
    is_home_team: bool
    points_scored: int
    scoring_type: str
    score: str


class SportStatusResponse(BaseModel):
    name: str
    enabled: bool
    live_games: int
    total_games_today: int


def _get_providers():
    """Lazy import providers to avoid circular imports."""
    from sports.nfl import nfl_provider
    from sports.nba import nba_provider
    from sports.nhl import nhl_provider
    from sports.mlb import mlb_provider
    from sports.soccer import soccer_provider
    return {
        "nfl": nfl_provider,
        "nba": nba_provider,
        "nhl": nhl_provider,
        "mlb": mlb_provider,
        "soccer": soccer_provider
    }


def _game_to_response(game, has_position: bool = False) -> GameResponse:
    """Convert BaseGame to GameResponse."""
    return GameResponse(
        id=game.id,
        sport=game.sport,
        home_team=TeamResponse(
            id=game.home_team.id,
            name=game.home_team.name,
            abbreviation=game.home_team.abbreviation,
            logo=game.home_team.logo
        ),
        away_team=TeamResponse(
            id=game.away_team.id,
            name=game.away_team.name,
            abbreviation=game.away_team.abbreviation,
            logo=game.away_team.logo
        ),
        home_score=game.home_score,
        away_score=game.away_score,
        status=game.status.value,
        period=game.period,
        clock=game.clock,
        start_time=game.start_time,
        venue=game.venue,
        spread=game.spread,
        over_under=game.over_under,
        has_open_position=has_position
    )


@router.get("/status", response_model=List[SportStatusResponse])
async def get_all_sports_status():
    """Get status of all sports."""
    providers = _get_providers()
    result = []
    
    for name, provider in providers.items():
        try:
            games = await provider.get_games_today()
            live = [g for g in games if g.status.value == "in_progress"]
            result.append(SportStatusResponse(
                name=name,
                enabled=True,
                live_games=len(live),
                total_games_today=len(games)
            ))
        except Exception as e:
            logger.error(f"Error getting {name} status: {e}")
            result.append(SportStatusResponse(
                name=name, enabled=False, live_games=0, total_games_today=0
            ))
    
    return result


@router.get("/games/live", response_model=List[GameResponse])
async def get_all_live_games():
    """Get all live games across all sports."""
    providers = _get_providers()
    all_games = []
    
    from core.state import state_manager
    positions = state_manager.get_open_positions()
    position_ids = {p.match_id for p in positions}
    
    for name, provider in providers.items():
        try:
            games = await provider.get_live_games()
            for game in games:
                all_games.append(_game_to_response(game, game.id in position_ids))
        except Exception as e:
            logger.error(f"Error fetching {name} games: {e}")
    
    return all_games


@router.get("/games/today", response_model=List[GameResponse])
async def get_all_games_today():
    """Get all games today across all sports."""
    providers = _get_providers()
    all_games = []
    
    from core.state import state_manager
    positions = state_manager.get_open_positions()
    position_ids = {p.match_id for p in positions}
    
    for name, provider in providers.items():
        try:
            games = await provider.get_games_today()
            for game in games:
                all_games.append(_game_to_response(game, game.id in position_ids))
        except Exception as e:
            logger.error(f"Error fetching {name} games: {e}")
    
    return all_games


@router.get("/games/{sport}", response_model=List[GameResponse])
async def get_games_by_sport(sport: str):
    """Get games for a specific sport."""
    providers = _get_providers()
    
    if sport not in providers:
        raise HTTPException(status_code=404, detail=f"Sport '{sport}' not found")
    
    from core.state import state_manager
    positions = state_manager.get_open_positions()
    position_ids = {p.match_id for p in positions}
    
    try:
        games = await providers[sport].get_games_today()
        return [_game_to_response(g, g.id in position_ids) for g in games]
    except Exception as e:
        logger.error(f"Error fetching {sport} games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/recent", response_model=List[ScoringEventResponse])
async def get_recent_events(limit: int = 20):
    """Get recent scoring events across all sports."""
    from core.state import state_manager
    
    # Get NFL scores
    nfl_events = state_manager.get_nfl_score_history(limit)
    
    # Convert to response format
    events = []
    for e in nfl_events:
        events.append(ScoringEventResponse(
            id=e.id,
            game_id=e.game_id,
            sport="nfl",
            timestamp=e.timestamp,
            period=e.quarter,
            clock=e.clock,
            scoring_team=e.scoring_team_name,
            is_home_team=e.is_home_team,
            points_scored=e.points_scored,
            scoring_type=e.scoring_type,
            score=f"{e.home_score}-{e.away_score}"
        ))
    
    # Sort by timestamp descending
    events.sort(key=lambda x: x.timestamp, reverse=True)
    return events[:limit]


@router.post("/refresh/{sport}")
async def refresh_sport(sport: str):
    """Manually refresh games for a sport."""
    providers = _get_providers()
    
    if sport == "all":
        results = {}
        for name, provider in providers.items():
            try:
                games = await provider.get_games_today()
                results[name] = len(games)
            except Exception as e:
                results[name] = f"error: {str(e)}"
        return {"status": "success", "games": results}
    
    if sport not in providers:
        raise HTTPException(status_code=404, detail=f"Sport '{sport}' not found")
    
    try:
        games = await providers[sport].get_games_today()
        live = [g for g in games if g.status.value == "in_progress"]
        return {
            "status": "success",
            "sport": sport,
            "total_games": len(games),
            "live_games": len(live)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_sports_summary():
    """Get summary of all sports activity."""
    providers = _get_providers()
    
    summary = {
        "sports": {},
        "total_live": 0,
        "total_today": 0
    }
    
    for name, provider in providers.items():
        try:
            games = await provider.get_games_today()
            live = [g for g in games if g.status.value == "in_progress"]
            summary["sports"][name] = {
                "live": len(live),
                "today": len(games),
                "status": "active"
            }
            summary["total_live"] += len(live)
            summary["total_today"] += len(games)
        except Exception as e:
            summary["sports"][name] = {
                "live": 0,
                "today": 0,
                "status": f"error: {str(e)}"
            }
    
    return summary
