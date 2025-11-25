"""
NFL Score Listener - Monitors live NFL games for scoring events.

Polls the ESPN API and detects new scores by comparing
current state with previous state.
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional, List, Dict, Awaitable
from loguru import logger

from config import settings
from core.models import NFLScoringEvent, NFLGame
from core.state import state_manager
from data_providers.nfl_scores import nfl_scores_provider


class NFLScoreListener:
    """
    Listens for scoring events in live NFL games.
    
    Uses polling to detect score changes and emits scoring events
    to registered callbacks.
    """
    
    def __init__(self):
        self.poll_interval = settings.goal_poll_interval  # Reuse same setting
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[NFLScoringEvent, NFLGame], Awaitable[None]]] = []
        self._previous_games: Dict[int, NFLGame] = {}
    
    def on_score(
        self,
        callback: Callable[[NFLScoringEvent, NFLGame], Awaitable[None]]
    ) -> None:
        """
        Register a callback for scoring events.
        
        Args:
            callback: Async function that takes (NFLScoringEvent, NFLGame).
        """
        self._callbacks.append(callback)
        logger.info(f"Registered NFL score callback: {callback.__name__}")
    
    async def _notify_callbacks(self, event: NFLScoringEvent, game: NFLGame) -> None:
        """Notify all registered callbacks of a scoring event."""
        for callback in self._callbacks:
            try:
                await callback(event, game)
            except Exception as e:
                logger.error(f"Error in score callback {callback.__name__}: {e}")
    
    async def _poll_loop(self) -> None:
        """Main polling loop."""
        logger.info(f"NFL Score listener started (polling every {self.poll_interval}s)")
        
        while self._running:
            try:
                # Fetch current live games
                current_games = await nfl_scores_provider.get_live_games()
                
                # Update state manager with NFL games
                state_manager.update_nfl_games(current_games)
                
                # Detect new scoring events
                if self._previous_games:
                    scoring_events = await nfl_scores_provider.detect_scoring_events(
                        self._previous_games,
                        current_games
                    )
                    
                    for event in scoring_events:
                        # Skip if already processed
                        if state_manager.is_nfl_score_processed(event.id):
                            continue
                        
                        # Get current game state
                        game = state_manager.get_nfl_game(event.game_id)
                        if game:
                            logger.info(
                                f"New NFL score detected: {event.scoring_team_name} "
                                f"{event.scoring_type} (+{event.points_scored}) "
                                f"in {game.display_name}"
                            )
                            
                            # Mark as processed
                            state_manager.mark_nfl_score_processed(event)
                            
                            # Notify callbacks
                            await self._notify_callbacks(event, game)
                
                # Update previous state
                self._previous_games = {g.id: g for g in current_games}
                
                live_count = len([g for g in current_games if g.is_live])
                logger.debug(f"Polled {len(current_games)} NFL games ({live_count} live)")
                
            except Exception as e:
                logger.error(f"Error in NFL score listener poll: {e}")
            
            # Wait for next poll
            await asyncio.sleep(self.poll_interval)
    
    async def start(self) -> None:
        """Start the score listener."""
        if self._running:
            logger.warning("NFL Score listener already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("NFL Score listener started")
    
    async def stop(self) -> None:
        """Stop the score listener."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("NFL Score listener stopped")
    
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running
    
    async def poll_once(self) -> List[NFLScoringEvent]:
        """
        Perform a single poll and return any new scoring events.
        
        Useful for testing or manual triggering.
        """
        current_games = await nfl_scores_provider.get_live_games()
        state_manager.update_nfl_games(current_games)
        
        if not self._previous_games:
            self._previous_games = {g.id: g for g in current_games}
            return []
        
        events = await nfl_scores_provider.detect_scoring_events(
            self._previous_games,
            current_games
        )
        
        self._previous_games = {g.id: g for g in current_games}
        return events
    
    def get_live_games(self) -> List[NFLGame]:
        """Get currently tracked live games."""
        return list(self._previous_games.values())


# Singleton instance
nfl_score_listener = NFLScoreListener()
