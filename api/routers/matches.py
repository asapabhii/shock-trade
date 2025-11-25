"""
Matches API router - Live match data and goal events.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from core.models import Match, GoalEvent, MatchStatus
from core.state import state_manager
from data_providers.live_scores import live_scores_provider

router = APIRouter()


class MatchResponse(BaseModel):
    """Match response model."""
    id: int
    league_name: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str
    minute: Optional[int]
    kickoff: datetime
    has_open_position: bool = False


class GoalEventResponse(BaseModel):
    """Goal event response model."""
    id: str
    match_id: int
    timestamp: datetime
    minute: int
    scoring_team: str
    is_home_team: bool
    score: str


@router.get("/live", response_model=List[MatchResponse])
async def get_live_matches():
    """Get all currently live matches."""
    matches = state_manager.get_live_matches()
    open_positions = state_manager.get_open_positions()
    position_match_ids = {p.match_id for p in open_positions}
    
    return [
        MatchResponse(
            id=m.id,
            league_name=m.league_name,
            home_team=m.home_team.name,
            away_team=m.away_team.name,
            home_score=m.home_score,
            away_score=m.away_score,
            status=m.status.value,
            minute=m.minute,
            kickoff=m.kickoff,
            has_open_position=m.id in position_match_ids
        )
        for m in matches
    ]


@router.get("/all", response_model=List[MatchResponse])
async def get_all_matches():
    """Get all tracked matches."""
    matches = state_manager.get_all_matches()
    open_positions = state_manager.get_open_positions()
    position_match_ids = {p.match_id for p in open_positions}
    
    return [
        MatchResponse(
            id=m.id,
            league_name=m.league_name,
            home_team=m.home_team.name,
            away_team=m.away_team.name,
            home_score=m.home_score,
            away_score=m.away_score,
            status=m.status.value,
            minute=m.minute,
            kickoff=m.kickoff,
            has_open_position=m.id in position_match_ids
        )
        for m in matches
    ]


@router.get("/goals", response_model=List[GoalEventResponse])
async def get_recent_goals(limit: int = 20):
    """Get recent goal events."""
    goals = state_manager.get_goal_history(limit)
    
    return [
        GoalEventResponse(
            id=g.id,
            match_id=g.match_id,
            timestamp=g.timestamp,
            minute=g.minute,
            scoring_team=g.scoring_team_name,
            is_home_team=g.is_home_team,
            score=f"{g.home_score}-{g.away_score}"
        )
        for g in reversed(goals)  # Most recent first
    ]


@router.post("/refresh")
async def refresh_matches():
    """Manually refresh live matches."""
    matches = await live_scores_provider.get_live_matches()
    state_manager.update_matches(matches)
    
    return {
        "status": "success",
        "matches_count": len(matches)
    }


@router.get("/{match_id}")
async def get_match(match_id: int):
    """Get a specific match by ID."""
    match = state_manager.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    mapping = state_manager.get_mapping(match_id)
    
    return {
        "match": MatchResponse(
            id=match.id,
            league_name=match.league_name,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            home_score=match.home_score,
            away_score=match.away_score,
            status=match.status.value,
            minute=match.minute,
            kickoff=match.kickoff
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
        "pre_goal_probs": {
            "home": mapping.pre_goal_home_prob if mapping else None,
            "away": mapping.pre_goal_away_prob if mapping else None
        }
    }
