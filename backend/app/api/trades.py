from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Trade
from app.services.mt5_connector import get_mt5
from app.core.strategy import calculate_sl_tp
import uuid

router = APIRouter(prefix="/trades", tags=["trades"])


class ManualTradeRequest(BaseModel):
    symbol: str
    order_type: str          # "buy" | "sell"
    volume: float = 0.01
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@router.get("")
async def list_trades(
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Trade)
    if status:
        q = q.filter(Trade.status == status)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    trades = q.order_by(Trade.opened_at.desc()).limit(limit).all()
    return [_serialize(t) for t in trades]


@router.get("/{trade_id}")
async def get_trade(trade_id: str, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    return _serialize(t)


@router.post("/manual")
async def place_manual_trade(body: ManualTradeRequest, db: Session = Depends(get_db)):
    mt5 = await get_mt5()
    sym_info = await mt5.get_symbol_info(body.symbol)
    price = sym_info.ask if body.order_type == "buy" else sym_info.bid

    sl = body.stop_loss
    tp = body.take_profit
    if not sl or not tp:
        bars = await mt5.get_ohlcv(body.symbol, "H1", 50)
        from app.core.indicators import full_analysis
        ind = full_analysis(bars)
        atr = ind.get("atr", sym_info.point * 100)
        sl, tp = calculate_sl_tp(price, body.order_type, atr, digits=sym_info.digits)

    result = await mt5.place_order(
        symbol=body.symbol,
        order_type=body.order_type,
        volume=body.volume,
        price=price,
        sl=sl or 0,
        tp=tp or 0,
        comment="manual",
    )

    trade = Trade(
        id=str(uuid.uuid4()),
        symbol=body.symbol,
        order_type=body.order_type,
        volume=body.volume,
        open_price=price,
        stop_loss=sl,
        take_profit=tp,
        status="open",
        strategy="manual",
        mt5_ticket=result.ticket,
    )
    db.add(trade)
    db.commit()
    return _serialize(trade)


@router.post("/{trade_id}/close")
async def close_trade(trade_id: str, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id, Trade.status == "open").first()
    if not t:
        raise HTTPException(404, "Open trade not found")

    mt5 = await get_mt5()
    if t.mt5_ticket:
        await mt5.close_order(t.mt5_ticket)

    sym_info = await mt5.get_symbol_info(t.symbol)
    close_price = sym_info.bid if t.order_type == "buy" else sym_info.ask
    point = sym_info.point
    pips = (
        (close_price - t.open_price) / point / 10
        if t.order_type == "buy"
        else (t.open_price - close_price) / point / 10
    )
    profit = round(pips * t.volume * 10, 2)

    t.status = "closed"
    t.close_price = close_price
    t.profit = profit
    t.pips = round(pips, 1)
    t.closed_at = datetime.now(tz=timezone.utc)
    t.notes = "manual_close"
    db.commit()
    return _serialize(t)


def _serialize(t: Trade) -> dict:
    return {
        "id": t.id,
        "symbol": t.symbol,
        "order_type": t.order_type,
        "volume": t.volume,
        "open_price": t.open_price,
        "close_price": t.close_price,
        "stop_loss": t.stop_loss,
        "take_profit": t.take_profit,
        "profit": t.profit,
        "pips": t.pips,
        "status": t.status,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "strategy": t.strategy,
        "signal_score": t.signal_score,
        "ai_signals": t.ai_signals,
        "mt5_ticket": t.mt5_ticket,
        "notes": t.notes,
    }
