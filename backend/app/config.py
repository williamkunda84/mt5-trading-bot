from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/forexbot"

    # MetaAPI (cloud MT5 bridge - works on Railway/Linux)
    metaapi_token: Optional[str] = None
    metaapi_account_id: Optional[str] = None

    # Direct MT5 (Windows only, fallback)
    mt5_login: Optional[int] = None
    mt5_password: Optional[str] = None
    mt5_server: Optional[str] = None

    # Bot defaults
    default_symbols: str = "EURUSD,GBPUSD,USDJPY,XAUUSD"
    default_risk_percent: float = 1.5      # % of balance per trade
    default_max_trades: int = 5
    default_timeframe: str = "H1"

    # AI / Analysis
    ai_confidence_threshold: float = 0.65  # min score to place trade
    ai_lookback_bars: int = 200

    # Server
    cors_origins: str = "*"
    secret_key: str = "change-me-in-production"

    # Mode: "live" | "demo" | "simulate"
    trading_mode: str = "simulate"

    class Config:
        env_file = ".env"


settings = Settings()
