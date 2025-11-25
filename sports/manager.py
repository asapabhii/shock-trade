"""
Sports Manager - Unified manager for all sports.

Handles registration, polling, and event routing for multiple sports.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Callable, Awaitable
from loguru import logger

from sports.base import BaseSport, BaseGame, BaseScoringEvent, BaseDataProvider, BaseDecisionEngine


class SportsManager:
    """
    Manages multiple sports for the trading bot.
    
    Handles:
    - Sport registration
    - Unified polling across all sports
    - Event routing to callbacks
    """
    
    def __init__(self):
        self._sports: Dict[str, BaseSport] = {}
        self._previous_games: Dict[str, Dict[int, BaseGame]] = {}
        self._callbacks: List[Callable[[BaseScoringEvent, BaseGame, str], Awaitable[None]]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.poll_interval = 30  # seconds
    
    def register_sport(
        self,
        name: str,
        provider: BaseDataProvider,
        decision_engine: BaseDecisionEngine
    ) -> None:
        """Register a sport for monitoring."""
        sport = BaseSport(name, provider, decision_engine)
        self._sports[name] = sport
        self._previous_games[name] = {}
        logger.info(f"Registered sport: {name}")
    
    def get_sport(self, name: str) -> Optional[BaseSport]:
        """Get a registered sport by name."""
        return self._sports.get(name)
    
    def get_all_sports(self) -> List[str]:
        """Get list of all registered sport names."""
        return list(self._sports.keys())
    
    def get_enabled_sports(self) -> List[str]:
        """Get list of enabled sport names."""
        return [name for name, sport in self._sports.items() if sport.enabled]
    
    def enable_sport(self, name: str) -> bool:
        """Enable a sport for monitoring."""
        sport = self._sports.get(name)
        if sport:
            sport.enable()
            logger.info(f"Enabled sport: {name}")
            return True
        return False
    
    def disable_sport(self, name: str) -> bool:
        """Disable a sport from monitoring."""
        sport = self._sports.get(name)
        if sport:
            sport.disable()
            logger.info(f"Disabled sport: {name}")
            return True
        return False
    
    def on_scoring_event(
        self,
        callback: Callable[[BaseScoringEvent, BaseGame, str], Awaitable[None]]
    ) -> None:
        """Register a callback for scoring events across all sports."""
        self._callbacks.append(callback)
        logger.info(f"Registered scoring callback: {callback.__name__}")
    
    async def _notify_callbacks(
        self,
        event: BaseScoringEvent,
        game: BaseGame,
        sport_name: str
    ) -> None:
        """Notify all callbacks of a scoring event."""
        for callback in self._callbacks:
            try:
                await callback(event, game, sport_name)
            except Exception as e:
                logger.error(f"Error in scoring callback: {e}")
    
    async def _poll_sport(self, sport: BaseSport) -> List[BaseScoringEvent]:
        """Poll a single sport for updates."""
        if not sport.enabled:
            return []
        
        try:
            # Get current games
            current_games = await sport.data_provider.get_live_games()
            
            # Get previous state
            previous = self._previous_games.get(sport.name, {})
            
            # Detect scoring events
            events = []
            if previous:
                events = await sport.data_provider.detect_scoring_events(
                    previous, current_games
                )
            
            # Update state
            self._previous_games[sport.name] = {g.id: g for g in current_games}
            
            return events
            
        except Exception as e:
            logger.error(f"Error polling {sport.name}: {e}")
            return []
    
    async def _poll_loop(self) -> None:
        """Main polling loop for all sports."""
        logger.info(f"Sports manager started (polling every {self.poll_interval}s)")
        
        while self._running:
            try:
                # Poll all enabled sports
                for sport_name, sport in self._sports.items():
                    if not sport.enabled:
                        continue
                    
                    events = await self._poll_sport(sport)
                    
                    # Process events
                    for event in events:
                        game = self._previous_games[sport_name].get(event.game_id)
                        if game:
                            await self._notify_callbacks(event, game, sport_name)
                
                # Log status
                enabled = self.get_enabled_sports()
                total_games = sum(
                    len(self._previous_games.get(s, {}))
                    for s in enabled
                )
                logger.debug(f"Polled {len(enabled)} sports, {total_games} games")
                
            except Exception as e:
                logger.error(f"Error in sports manager poll: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    async def start(self) -> None:
        """Start the sports manager."""
        if self._running:
            logger.warning("Sports manager already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Sports manager started")
    
    async def stop(self) -> None:
        """Stop the sports manager."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        # Close all providers
        for sport in self._sports.values():
            await sport.data_provider.close()
        
        logger.info("Sports manager stopped")
    
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running
    
    async def get_all_live_games(self) -> Dict[str, List[BaseGame]]:
        """Get all live games across all sports."""
        result = {}
        for sport_name, sport in self._sports.items():
            if sport.enabled:
                games = await sport.data_provider.get_live_games()
                result[sport_name] = games
        return result
    
    async def get_games_today(self, sport_name: str) -> List[BaseGame]:
        """Get today's games for a specific sport."""
        sport = self._sports.get(sport_name)
        if sport:
            return await sport.data_provider.get_games_today()
        return []
    
    def get_cached_games(self, sport_name: str) -> List[BaseGame]:
        """Get cached games for a sport (from last poll)."""
        return list(self._previous_games.get(sport_name, {}).values())


# Singleton instance
sports_manager = SportsManager()
