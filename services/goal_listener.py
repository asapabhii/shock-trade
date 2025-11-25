"""
Goal Listener - Monitors live matches for goal events.

Polls the live scores API and detects new goals by comparing
current state with previous state.
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional, List, Awaitable
from loguru import logger

from config import settings
from core.models import GoalEvent, Match
from core.state import state_manager
from data_providers.live_scores import live_scores_provider


class GoalListener:
    """
    Listens for goal events in live football matches.
    
    Uses polling to detect score changes and emits goal events
    to registered callbacks.
    """
    
    def __init__(self):
        self.poll_interval = settings.goal_poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[GoalEvent, Match], Awaitable[None]]] = []
    
    def on_goal(
        self,
        callback: Callable[[GoalEvent, Match], Awaitable[None]]
    ) -> None:
        """
        Register a callback for goal events.
        
        Args:
            callback: Async function that takes (GoalEvent, Match).
        """
        self._callbacks.append(callback)
        logger.info(f"Registered goal callback: {callback.__name__}")
    
    async def _notify_callbacks(self, goal: GoalEvent, match: Match) -> None:
        """Notify all registered callbacks of a goal."""
        for callback in self._callbacks:
            try:
                await callback(goal, match)
            except Exception as e:
                logger.error(f"Error in goal callback {callback.__name__}: {e}")
    
    async def _poll_loop(self) -> None:
        """Main polling loop."""
        logger.info(f"Goal listener started (polling every {self.poll_interval}s)")
        
        while self._running:
            try:
                # Get previous state
                previous_matches = state_manager.get_previous_matches()
                
                # Fetch current live matches
                current_matches = await live_scores_provider.get_live_matches()
                
                # Update state
                state_manager.update_matches(current_matches)
                
                # Detect new goals
                if previous_matches:
                    new_goals = await live_scores_provider.detect_new_goals(
                        previous_matches,
                        current_matches
                    )
                    
                    for goal in new_goals:
                        # Skip if already processed
                        if state_manager.is_goal_processed(goal.id):
                            continue
                        
                        # Get current match state
                        match = state_manager.get_match(goal.match_id)
                        if match:
                            logger.info(
                                f"🎯 New goal detected: {goal.scoring_team_name} "
                                f"({goal.home_score}-{goal.away_score}) "
                                f"in {match.display_name}"
                            )
                            
                            # Mark as processed
                            state_manager.mark_goal_processed(goal)
                            
                            # Notify callbacks
                            await self._notify_callbacks(goal, match)
                
                logger.debug(f"Polled {len(current_matches)} live matches")
                
            except Exception as e:
                logger.error(f"Error in goal listener poll: {e}")
            
            # Wait for next poll
            await asyncio.sleep(self.poll_interval)
    
    async def start(self) -> None:
        """Start the goal listener."""
        if self._running:
            logger.warning("Goal listener already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Goal listener started")
    
    async def stop(self) -> None:
        """Stop the goal listener."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("Goal listener stopped")
    
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running
    
    async def poll_once(self) -> List[GoalEvent]:
        """
        Perform a single poll and return any new goals.
        
        Useful for testing or manual triggering.
        """
        previous_matches = state_manager.get_previous_matches()
        current_matches = await live_scores_provider.get_live_matches()
        state_manager.update_matches(current_matches)
        
        if not previous_matches:
            return []
        
        return await live_scores_provider.detect_new_goals(
            previous_matches,
            current_matches
        )


# Singleton instance
goal_listener = GoalListener()
