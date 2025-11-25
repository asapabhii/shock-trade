"""
CLI script to run the trading bot standalone.

Usage:
    python scripts/run_bot.py [--no-trade]
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config import settings
from services.goal_listener import goal_listener
from services.trade_service import trade_service
from exchanges.kalshi_client import kalshi_client
from database import init_db


async def main(no_trade: bool = False):
    """Main entry point for the trading bot."""
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
    
    logger.info("=" * 50)
    logger.info("Goal Trader Bot Starting")
    logger.info("=" * 50)
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Check API keys
    if not settings.rapidapi_key:
        logger.warning("⚠️  RAPIDAPI_KEY not set - live scores will not work")
    
    if not settings.kalshi_api_key:
        logger.warning("⚠️  KALSHI_API_KEY not set - trading will not work")
    else:
        # Login to Kalshi
        logger.info("Logging into Kalshi...")
        success = await kalshi_client.login()
        if success:
            logger.info("✅ Kalshi login successful")
        else:
            logger.warning("⚠️  Kalshi login failed - trading may not work")
    
    # Configure trading
    if no_trade:
        trade_service.disable()
        logger.info("Trading DISABLED (--no-trade flag)")
    else:
        trade_service.enable()
        logger.info("Trading ENABLED")
    
    # Register goal callback
    goal_listener.on_goal(trade_service.process_goal)
    
    # Start goal listener
    logger.info(f"Starting goal listener (poll interval: {settings.goal_poll_interval}s)")
    await goal_listener.start()
    
    logger.info("=" * 50)
    logger.info("Bot is running. Press Ctrl+C to stop.")
    logger.info("=" * 50)
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(60)
            
            # Periodic status log
            from core.state import state_manager
            metrics = state_manager.get_metrics()
            matches = state_manager.get_live_matches()
            
            logger.info(
                f"Status: {len(matches)} live matches | "
                f"{metrics.total_trades} trades | "
                f"P/L: ${metrics.total_pnl:.2f}"
            )
            
            # Check exit conditions for open positions
            await trade_service.check_exit_conditions()
            
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down...")
        await goal_listener.stop()
        await kalshi_client.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goal Trader Bot")
    parser.add_argument(
        "--no-trade",
        action="store_true",
        help="Run in observation mode without executing trades"
    )
    args = parser.parse_args()
    
    try:
        asyncio.run(main(no_trade=args.no_trade))
    except KeyboardInterrupt:
        print("\nShutdown requested...")
