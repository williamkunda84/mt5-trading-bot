from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/forexbot"

    # MetaAPI (cloud MT5 bridge - works on Railway/Linux)
    metaapi_token: Optional[str] = None
    metaapi_account_id: Optional[str] = None

    # Direct MT5 (Windows only)
    mt5_login: Optional[int] = None
    mt5_password: Optional[str] = None
    mt5_server: Optional[str] = None

    # Bot defaults
    default_symbols: str = "EURUSD,GBPUSD,USDJPY,XAUUSD"
    default_risk_percent: float = 1.5
    default_max_trades: int = 5
    default_timeframe: str = "H1"

    # AI / Analysis
    ai_confidence_threshold: float = 0.65
    ai_lookback_bars: int = 200

    # Server
    cors_origins: str = "*"
    secret_key: str = "change-me-in-production"

    # Mode: "direct" | "live" | "demo" | "simulate"
    trading_mode: str = "simulate"

    class Config:
        env_file = ".env"

    @field_validator("mt5_login", mode="before")
    @classmethod
    def parse_mt5_login(cls, v):
        return None if v == "" or v is None else int(v)

    @field_validator("mt5_password", "mt5_server", "metaapi_token", "metaapi_account_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        return None if v == "" else v


settings = Settings()
