"""
Base classes for multi-sport trading architecture.

All sports implement these interfaces for consistent behavior.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum


class GameStatus(str, Enum):
    """Universal game status across all sports."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    HALFTIME = "halftime"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class BaseTeam(BaseModel):
    """Base team model for all sports."""
    id: int
    name: str
    abbreviation: str = ""
    logo: Optional[str] = None


class BaseGame(BaseModel):
    """Base game model for all sports."""
    id: int
    sport: str
    home_team: BaseTeam
    away_team: BaseTeam
    home_score: int = 0
    away_score: int = 0
    status: GameStatus = GameStatus.SCHEDULED
    period: int = 0  # Quarter, half, inning, etc.
    clock: str = ""
    start_time: datetime
    venue: Optional[str] = None
    
    # Betting info
    spread: Optional[float] = None  # Negative = home favored
    over_under: Optional[float] = None
    home_odds: Optional[float] = None
    away_odds: Optional[float] = None
    
    @property
    def display_name(self) -> str:
        return f"{self.away_team.name} @ {self.home_team.name}"
    
    @property
    def is_live(self) -> bool:
        return self.status == GameStatus.IN_PROGRESS


class BaseScoringEvent(BaseModel):
    """Base scoring event for all sports."""
    model_config = {"frozen": True}
    
    id: str
    game_id: int
    sport: str
    timestamp: datetime
    period: int
    clock: str
    scoring_team_id: int
    scoring_team_name: str
    is_home_team: bool
    points_scored: int
    scoring_type: str  # touchdown, goal, basket, run, etc.
    home_score: int
    away_score: int
    
    @property
    def score_display(self) -> str:
        return f"{self.home_score}-{self.away_score}"


class BaseGameMarketMapping(BaseModel):
    """Maps a game to exchange markets."""
    game_id: int
    sport: str
    home_team_name: str
    away_team_name: str
    start_time: datetime
    markets: List[Any] = []
    pre_event_home_prob: Optional[float] = None
    pre_event_away_prob: Optional[float] = None
    spread: Optional[float] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class BaseDataProvider(ABC):
    """Abstract base class for sport data providers."""
    
    sport_name: str = "unknown"
    
    @abstractmethod
    async def get_live_games(self) -> List[BaseGame]:
        """Fetch all currently live games."""
        pass
    
    @abstractmethod
    async def get_games_today(self) -> List[BaseGame]:
        """Fetch all games scheduled for today."""
        pass
    
    @abstractmethod
    async def detect_scoring_events(
        self,
        previous_games: Dict[int, BaseGame],
        current_games: List[BaseGame]
    ) -> List[BaseScoringEvent]:
        """Detect new scoring events by comparing game states."""
        pass
    
    async def close(self):
        """Cleanup resources."""
        pass


class BaseDecisionEngine(ABC):
    """Abstract base class for sport-specific trading strategies."""
    
    sport_name: str = "unknown"
    min_points_for_signal: int = 1
    
    @abstractmethod
    def is_underdog(
        self,
        team_id: int,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, Optional[float], str]:
        """
        Determine if a team is the underdog.
        
        Returns: (is_underdog, spread_or_odds, reason)
        """
        pass
    
    @abstractmethod
    def should_trade(
        self,
        event: BaseScoringEvent,
        game: BaseGame,
        mapping: BaseGameMarketMapping
    ) -> Tuple[bool, str]:
        """
        Determine if this scoring event should trigger a trade.
        
        Returns: (should_trade, reason)
        """
        pass
    
    def check_time_remaining(self, game: BaseGame, event: BaseScoringEvent) -> Tuple[bool, str]:
        """Check if enough time remains. Override per sport."""
        return (True, "Time check passed")
    
    def check_score_differential(self, game: BaseGame, event: BaseScoringEvent) -> Tuple[bool, str]:
        """Check if game is competitive. Override per sport."""
        diff = abs(event.home_score - event.away_score)
        if diff > 30:
            return (False, f"Blowout ({diff} point differential)")
        return (True, f"Competitive game ({diff} point differential)")


class BaseSport:
    """Container for sport-specific components."""
    
    def __init__(
        self,
        name: str,
        data_provider: BaseDataProvider,
        decision_engine: BaseDecisionEngine
    ):
        self.name = name
        self.data_provider = data_provider
        self.decision_engine = decision_engine
        self.enabled = True
    
    def enable(self):
        self.enabled = True
    
    def disable(self):
        self.enabled = False
