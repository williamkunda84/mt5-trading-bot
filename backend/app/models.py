from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    order_type = Column(String(10), nullable=False)   # "buy" | "sell"
    volume = Column(Float, nullable=False)
    open_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    pips = Column(Float, nullable=True)
    status = Column(String(20), default="open", index=True)  # open | closed | cancelled
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    strategy = Column(String(100), nullable=True)
    signal_score = Column(Float, nullable=True)
    ai_signals = Column(JSON, nullable=True)      # snapshot of analysis at entry
    mt5_ticket = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)


class BotConfig(Base):
    __tablename__ = "bot_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_running = Column(Boolean, default=False)
    symbols = Column(String, default="EURUSD,GBPUSD,USDJPY,XAUUSD")
    risk_percent = Column(Float, default=1.5)
    max_open_trades = Column(Integer, default=5)
    timeframe = Column(String(10), default="H1")
    strategy = Column(String(50), default="multi_signal")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MarketSnapshot(Base):
    """Stores periodic OHLCV + indicator snapshots for trend analysis."""
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    rsi = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    ema20 = Column(Float)
    ema50 = Column(Float)
    ema200 = Column(Float)
    bb_upper = Column(Float)
    bb_lower = Column(Float)
    atr = Column(Float)
    signal_score = Column(Float)   # composite AI score -1..+1
    signal_direction = Column(String(10))  # buy | sell | hold


class WalletSnapshot(Base):
    """Daily wallet performance snapshots for growth charting."""
    __tablename__ = "wallet_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    free_margin = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)


class TradeSetup(Base):
    """
    Detected trade setup from the multi-strategy scanner.
    status: forming | confirmed | invalidated | expired
    """
    __tablename__ = "trade_setups"

    id = Column(String, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)       # buy | sell
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=False)
    take_profit_3 = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)           # 0–100
    rr_ratio = Column(Float, default=2.0)
    strategies_confirmed = Column(JSON)                  # ["EMA Confluence", ...]
    strategy_details = Column(JSON)                      # [{name, confidence, notes, eta_minutes}]
    status = Column(String(20), default="forming", index=True)
    eta_minutes = Column(Integer, nullable=True)         # None = already confirmed
    alert_sent = Column(Boolean, default=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
