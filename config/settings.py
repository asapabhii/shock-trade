"""
Application settings and configuration management.
Loads from environment variables with sensible defaults.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }
    
    # API-Football (RapidAPI) - Legacy, limited free tier
    rapidapi_key: str = Field(default="", description="RapidAPI key for API-Football")
    rapidapi_host: str = Field(default="api-football-v1.p.rapidapi.com")
    
    # Football-Data.org - Free, 10 req/min, no daily limit
    football_data_api_key: str = Field(default="", description="Football-Data.org API key")
    
    # Kalshi Demo API (RSA Key Authentication)
    kalshi_api_key: str = Field(default="", description="Kalshi API key")
    kalshi_private_key_path: str = Field(default="kalshi_private_key.pem", description="Path to RSA private key")
    kalshi_base_url: str = Field(default="https://demo-api.kalshi.co")
    
    # Trading Configuration
    bankroll: float = Field(default=10000.0, description="Total demo bankroll")
    max_per_trade_pct: float = Field(default=0.5, description="Max % of bankroll per trade")
    underdog_threshold: float = Field(default=0.5, description="Probability threshold for underdog")
    daily_loss_limit: float = Field(default=500.0, description="Max daily loss before stopping")
    per_match_max_exposure: float = Field(default=200.0, description="Max exposure per match")
    take_profit_pct: float = Field(default=0.15, description="Take profit at 15% gain")
    stop_loss_pct: float = Field(default=0.10, description="Stop loss at 10% loss")
    
    # Risk Management
    max_consecutive_errors: int = Field(default=5, description="Circuit breaker threshold")
    max_latency_ms: int = Field(default=5000, description="Max acceptable latency in ms")
    min_liquidity: float = Field(default=100.0, description="Minimum liquidity required")
    
    # Application Settings
    log_level: str = Field(default="INFO")
    database_url: str = Field(default="sqlite+aiosqlite:///./goal_trader.db")
    
    # Polling intervals (seconds)
    goal_poll_interval: int = Field(default=30, description="Seconds between live score polls")
    market_cache_ttl: int = Field(default=300, description="Market cache TTL in seconds")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
