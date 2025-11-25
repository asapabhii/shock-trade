"""
Script to run the API server with the trading bot.

Usage:
    python scripts/run_server.py [--port 8000] [--no-bot]
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from loguru import logger
from config import settings


def main():
    """Run the API server."""
    parser = argparse.ArgumentParser(description="Goal Trader API Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>"
    )
    
    logger.info("=" * 50)
    logger.info("Goal Trader API Server")
    logger.info("=" * 50)
    logger.info(f"Starting server on http://{args.host}:{args.port}")
    logger.info(f"API docs available at http://localhost:{args.port}/docs")
    logger.info("=" * 50)
    
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
