from fastapi import APIRouter, Query
from app.services.mt5_connector import get_mt5
from app.core.indicators import full_analysis
from app.core.strategy import composite_score, get_direction, forecast_growth

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/{symbol}")
async def analyze_symbol(
    symbol: str,
    timeframe: str = Query("H1"),
    bars: int = Query(200, ge=50, le=500),
):
    mt5 = await get_mt5()
    ohlcv = await mt5.get_ohlcv(symbol, timeframe, bars)
    ind = full_analysis(ohlcv)
    score, sub_scores = composite_score(ind)
    direction = get_direction(score)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "score": round(score, 4),
        "direction": direction,
        "sub_scores": {k: round(v, 4) for k, v in sub_scores.items()},
        "indicators": {k: v for k, v in ind.items() if k != "candles"},
        "candles": ind.get("candles", []),
    }


@router.get("/{symbol}/price")
async def get_price(symbol: str):
    mt5 = await get_mt5()
    info = await mt5.get_symbol_info(symbol)
    return {
        "symbol": info.symbol,
        "bid": info.bid,
        "ask": info.ask,
        "spread": info.spread,
        "digits": info.digits,
    }


@router.get("/forecast/growth")
async def growth_forecast(days: int = Query(30, ge=7, le=90)):
    """
    Returns a growth forecast based on wallet snapshot history.
    Falls back to simulated equity series if DB is empty.
    """
    from app.database import SessionLocal
    from app.models import WalletSnapshot

    db = SessionLocal()
    try:
        snaps = db.query(WalletSnapshot).order_by(WalletSnapshot.date.asc()).all()
        equity_series = [s.equity for s in snaps]
    finally:
        db.close()

    if len(equity_series) < 5:
        # Generate a realistic demo equity curve
        import numpy as np
        rng = np.random.default_rng(42)
        equity_series = list(10000 * np.cumprod(1 + rng.normal(0.003, 0.012, 30)))

    return forecast_growth(equity_series, days_ahead=days)


@router.get("/multi/scan")
async def multi_symbol_scan(
    symbols: str = Query("EURUSD,GBPUSD,USDJPY,XAUUSD"),
    timeframe: str = Query("H1"),
):
    """Quick scan across multiple symbols, returns signals without full candle data."""
    mt5 = await get_mt5()
    results = []
    for sym in symbols.split(","):
        sym = sym.strip()
        if not sym:
            continue
        try:
            ohlcv = await mt5.get_ohlcv(sym, timeframe, 100)
            ind = full_analysis(ohlcv)
            score, sub_scores = composite_score(ind)
            direction = get_direction(score)
            info = await mt5.get_symbol_info(sym)
            results.append({
                "symbol": sym,
                "bid": info.bid,
                "ask": info.ask,
                "score": round(score, 4),
                "direction": direction,
                "rsi": ind.get("rsi"),
                "macd_hist": ind.get("macd_hist"),
                "above_ema200": ind.get("above_ema200"),
            })
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)})
    return results
