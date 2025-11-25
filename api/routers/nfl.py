"""
NFL API router - Live NFL game data and scoring events.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from core.models import NFLGame, NFLScoringEvent, NFLGameStatus
from core.state import state_manager
from data_providers.nfl_scores import nfl_scores_provider

router = APIRouter()


class NFLTeamResponse(BaseModel):
    """NFL team response model."""
    id: int
    name: str
    abbreviation: str
    logo: Optional[str] = None


class NFLGameResponse(BaseModel):
    """NFL game response model."""
    id: int
    home_team: NFLTeamResponse
    away_team: NFLTeamResponse
    home_score: int
    away_score: int
    status: str
    quarter: int
    clock: str
    kickoff: datetime
    venue: Optional[str] = None
    spread: Optional[float] = None
    over_under: Optional[float] = None
    week: Optional[int] = None
    has_open_position: bool = False


class NFLScoringEventResponse(BaseModel):
    """NFL scoring event response model."""
    id: str
    game_id: int
    timestamp: datetime
    quarter: int
    clock: str
    scoring_team: str
    is_home_team: bool
    points_scored: int
    scoring_type: str
    score: str


@router.get("/games/live", response_model=List[NFLGameResponse])
async def get_live_nfl_games():
    """Get all currently live NFL games."""
    games = state_manager.get_live_nfl_games()
    open_positions = state_manager.get_open_positions()
    position_game_ids = {p.match_id for p in open_positions}
    
    return [
        NFLGameResponse(
            id=g.id,
            home_team=NFLTeamResponse(
                id=g.home_team.id,
                name=g.home_team.name,
                abbreviation=g.home_team.abbreviation,
                logo=g.home_team.logo
            ),
            away_team=NFLTeamResponse(
                id=g.away_team.id,
                name=g.away_team.name,
                abbreviation=g.away_team.abbreviation,
                logo=g.away_team.logo
            ),
            home_score=g.home_score,
            away_score=g.away_score,
            status=g.status.value,
            quarter=g.quarter,
            clock=g.clock,
            kickoff=g.kickoff,
            venue=g.venue,
            spread=g.spread,
            over_under=g.over_under,
            week=g.week,
            has_open_position=g.id in position_game_ids
        )
        for g in games
    ]


@router.get("/games/all", response_model=List[NFLGameResponse])
async def get_all_nfl_games():
    """Get all tracked NFL games."""
    games = state_manager.get_all_nfl_games()
    open_positions = state_manager.get_open_positions()
    position_game_ids = {p.match_id for p in open_positions}
    
    return [
        NFLGameResponse(
            id=g.id,
            home_team=NFLTeamResponse(
                id=g.home_team.id,
                name=g.home_team.name,
                abbreviation=g.home_team.abbreviation,
                logo=g.home_team.logo
            ),
            away_team=NFLTeamResponse(
                id=g.away_team.id,
                name=g.away_team.name,
                abbreviation=g.away_team.abbreviation,
                logo=g.away_team.logo
            ),
            home_score=g.home_score,
            away_score=g.away_score,
            status=g.status.value,
            quarter=g.quarter,
            clock=g.clock,
            kickoff=g.kickoff,
            venue=g.venue,
            spread=g.spread,
            over_under=g.over_under,
            week=g.week,
            has_open_position=g.id in position_game_ids
        )
        for g in games
    ]


@router.get("/scores", response_model=List[NFLScoringEventResponse])
async def get_recent_scores(limit: int = 20):
    """Get recent NFL scoring events."""
    events = state_manager.get_nfl_score_history(limit)
    
    return [
        NFLScoringEventResponse(
            id=e.id,
            game_id=e.game_id,
            timestamp=e.timestamp,
            quarter=e.quarter,
            clock=e.clock,
            scoring_team=e.scoring_team_name,
            is_home_team=e.is_home_team,
            points_scored=e.points_scored,
            scoring_type=e.scoring_type,
            score=f"{e.home_score}-{e.away_score}"
        )
        for e in reversed(events)
    ]


@router.post("/refresh")
async def refresh_nfl_games():
    """Manually refresh NFL games."""
    games = await nfl_scores_provider.get_live_games()
    state_manager.update_nfl_games(games)
    
    return {
        "status": "success",
        "games_count": len(games),
        "live_count": len([g for g in games if g.is_live])
    }


@router.get("/games/{game_id}")
async def get_nfl_game(game_id: int):
    """Get a specific NFL game by ID."""
    game = state_manager.get_nfl_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    mapping = state_manager.get_nfl_mapping(game_id)
    
    return {
        "game": NFLGameResponse(
            id=game.id,
            home_team=NFLTeamResponse(
                id=game.home_team.id,
                name=game.home_team.name,
                abbreviation=game.home_team.abbreviation,
                logo=game.home_team.logo
            ),
            away_team=NFLTeamResponse(
                id=game.away_team.id,
                name=game.away_team.name,
                abbreviation=game.away_team.abbreviation,
                logo=game.away_team.logo
            ),
            home_score=game.home_score,
            away_score=game.away_score,
            status=game.status.value,
            quarter=game.quarter,
            clock=game.clock,
            kickoff=game.kickoff,
            venue=game.venue,
            spread=game.spread,
            over_under=game.over_under,
            week=game.week
        ),
        "markets": [
            {
                "id": m.id,
                "title": m.title,
                "yes_price": m.yes_price,
                "no_price": m.no_price
            }
            for m in (mapping.markets if mapping else [])
        ],
        "pre_score_probs": {
            "home": mapping.pre_score_home_prob if mapping else None,
            "away": mapping.pre_score_away_prob if mapping else None
        }
    }


@router.get("/markets")
async def search_nfl_markets(search: str = ""):
    """Search for NFL-related markets on Kalshi."""
    from core.nfl_mapper import nfl_market_mapper
    
    markets = await nfl_market_mapper.search_nfl_markets(search)
    
    return {
        "count": len(markets),
        "markets": [
            {
                "id": m.id,
                "title": m.title,
                "subtitle": m.subtitle,
                "yes_price": m.yes_price,
                "no_price": m.no_price,
                "status": m.status
            }
            for m in markets
        ]
    }
