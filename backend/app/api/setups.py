"""
Trade setup API.

GET  /api/setups               – list stored setups (filterable)
GET  /api/setups/scan          – live scan across all symbols + TFs, persist results
GET  /api/setups/alerts        – setups with eta_minutes 0–60 (alert candidates)
GET  /api/setups/{id}          – single setup detail
POST /api/setups/{id}/dismiss  – mark a setup as expired/dismissed
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

def _now():
    """Naive UTC datetime — compatible with both SQLite and PostgreSQL."""
    return datetime.utcnow()
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TradeSetup, BotConfig
from app.core.setups import detect_setups, scan_all
from app.services.mt5_connector import get_mt5

router = APIRouter(prefix="/setups", tags=["setups"])

# Symbols and timeframes to scan
SCAN_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY", "AUDUSD", "EURJPY"]
SCAN_TIMEFRAMES = ["M15", "H1", "H4"]

# In-memory cache of latest scan results (avoids repeated MT5 calls)
_scan_cache: List[dict] = []
_scan_at: Optional[datetime] = None
CACHE_TTL_SECONDS = 90


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize(s: TradeSetup) -> dict:
    return {
        "id": s.id,
        "symbol": s.symbol,
        "timeframe": s.timeframe,
        "direction": s.direction,
        "entry_price": s.entry_price,
        "stop_loss": s.stop_loss,
        "take_profit_1": s.take_profit_1,
        "take_profit_2": s.take_profit_2,
        "take_profit_3": s.take_profit_3,
        "confidence": s.confidence,
        "rr_ratio": s.rr_ratio,
        "strategies_confirmed": s.strategies_confirmed,
        "strategy_details": s.strategy_details,
        "status": s.status,
        "eta_minutes": s.eta_minutes,
        "alert_sent": s.alert_sent,
        "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "notes": s.notes,
    }


def _result_to_model(r, db: Session) -> TradeSetup:
    """Persist a TradeSetupResult → TradeSetup DB row (upsert by symbol+tf+dir)."""
    now = _now()

    # Deduplicate: if an identical setup (symbol+tf+direction+status!=expired) exists
    # in the last 2 hours, skip to avoid flooding.
    cutoff = now - timedelta(hours=2)
    existing = db.query(TradeSetup).filter(
        TradeSetup.symbol == r.symbol,
        TradeSetup.timeframe == r.timeframe,
        TradeSetup.direction == r.direction,
        TradeSetup.status != "expired",
        TradeSetup.detected_at >= cutoff,
    ).first()
    if existing:
        # Refresh eta + confidence but keep same row
        existing.eta_minutes = r.eta_minutes
        existing.confidence = r.confidence
        existing.strategy_details = r.strategy_details
        existing.strategies_confirmed = r.strategies_confirmed
        if r.eta_minutes == 0 and existing.status == "forming":
            existing.status = "confirmed"
            existing.confirmed_at = now
        db.commit()
        return existing

    setup = TradeSetup(
        id=r.id,
        symbol=r.symbol,
        timeframe=r.timeframe,
        direction=r.direction,
        entry_price=r.entry_price,
        stop_loss=r.stop_loss,
        take_profit_1=r.take_profit_1,
        take_profit_2=r.take_profit_2,
        take_profit_3=r.take_profit_3,
        confidence=r.confidence,
        rr_ratio=r.rr_ratio,
        strategies_confirmed=r.strategies_confirmed,
        strategy_details=r.strategy_details,
        status=r.status,
        eta_minutes=r.eta_minutes,
        alert_sent=False,
        detected_at=now,
        confirmed_at=now if r.eta_minutes == 0 else None,
        expires_at=now + timedelta(hours=4),
        notes=r.notes,
    )
    db.add(setup)
    db.commit()
    return setup


# ─── Background scanner (called by scheduler) ─────────────────────────────────

async def run_setup_scan(db: Session) -> List[dict]:
    """Full multi-symbol, multi-TF scan. Called by APScheduler every 60 s."""
    global _scan_cache, _scan_at

    mt5 = await get_mt5()
    bars_map: dict = {}
    digits_map: dict = {}

    for symbol in SCAN_SYMBOLS:
        bars_map[symbol] = {}
        try:
            info = await mt5.get_symbol_info(symbol)
            digits_map[symbol] = info.digits
        except Exception:
            digits_map[symbol] = 5
        for tf in SCAN_TIMEFRAMES:
            try:
                bars_map[symbol][tf] = await mt5.get_ohlcv(symbol, tf, 200)
            except Exception:
                pass

    results = scan_all(bars_map, digits_map)

    serialized = []
    for r in results:
        try:
            model = _result_to_model(r, db)
            serialized.append(_serialize(model))
        except Exception:
            pass

    # Expire old forming setups (naive datetime for SQLite compatibility)
    cutoff = datetime.utcnow() - timedelta(hours=4)
    db.query(TradeSetup).filter(
        TradeSetup.status == "forming",
        TradeSetup.detected_at < cutoff,
    ).update({"status": "expired"}, synchronize_session=False)
    db.commit()

    _scan_cache = serialized
    _scan_at = datetime.now(tz=timezone.utc)
    return serialized


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_setups(
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    min_confidence: float = Query(0.0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(TradeSetup)
    if status:
        q = q.filter(TradeSetup.status == status)
    else:
        q = q.filter(TradeSetup.status.in_(["forming", "confirmed"]))
    if symbol:
        q = q.filter(TradeSetup.symbol == symbol)
    if direction:
        q = q.filter(TradeSetup.direction == direction)
    if min_confidence:
        q = q.filter(TradeSetup.confidence >= min_confidence)
    setups = q.order_by(TradeSetup.detected_at.desc()).limit(limit).all()
    return [_serialize(s) for s in setups]


@router.get("/scan")
async def live_scan(
    background_tasks: BackgroundTasks,
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Trigger a live scan; returns cached results if fresh enough."""
    global _scan_cache, _scan_at
    now = _now()

    if force or _scan_at is None or (now - _scan_at).total_seconds() > CACHE_TTL_SECONDS:
        results = await run_setup_scan(db)
    else:
        results = _scan_cache

    return {
        "scanned_at": _scan_at.isoformat() if _scan_at else None,
        "count": len(results),
        "setups": results,
    }


@router.get("/alerts")
async def get_alerts(
    db: Session = Depends(get_db),
):
    """Setups forming within the next 60 minutes (alert candidates)."""
    now = _now()
    cutoff = now - timedelta(hours=2)

    # Confirmed setups (eta=0) + forming setups with eta <= 60
    setups = db.query(TradeSetup).filter(
        TradeSetup.status.in_(["forming", "confirmed"]),
        TradeSetup.detected_at >= cutoff,
    ).order_by(TradeSetup.confidence.desc()).all()

    alerts = []
    for s in setups:
        is_alert = s.status == "confirmed" or (s.eta_minutes is not None and s.eta_minutes <= 60)
        if is_alert and s.confidence >= 55:
            alerts.append(_serialize(s))

    return alerts


@router.get("/{setup_id}")
async def get_setup(setup_id: str, db: Session = Depends(get_db)):
    s = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if not s:
        from fastapi import HTTPException
        raise HTTPException(404, "Setup not found")
    return _serialize(s)


@router.post("/{setup_id}/dismiss")
async def dismiss_setup(setup_id: str, db: Session = Depends(get_db)):
    s = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if s:
        s.status = "expired"
        db.commit()
    return {"ok": True}
