"""
FastAPI application - Main entry point for the API server.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from database import init_db
from api.routers import matches, trades, positions, metrics, config, system, backtest, nfl, sports


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Shock Trade API...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Shock Trade API...")


app = FastAPI(
    title="Shock Trade API",
    description="Multi-sport scoring-reaction trading bot API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local development
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://shocktrade.asapabhi.me",  # Production domain
        "https://*.vercel.app",  # Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sports.router, prefix="/api/sports", tags=["All Sports"])
app.include_router(nfl.router, prefix="/api/nfl", tags=["NFL"])
app.include_router(matches.router, prefix="/api/matches", tags=["Soccer Matches"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(positions.router, prefix="/api/positions", tags=["Positions"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(config.router, prefix="/api/config", tags=["Configuration"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Shock Trade API",
        "version": "2.0.0",
        "status": "running",
        "sports": ["nfl", "nba", "mlb", "nhl", "soccer"],
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
