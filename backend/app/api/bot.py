from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.models import BotConfig
from app.services.trading_bot import start_bot, stop_bot, get_bot_state

router = APIRouter(prefix="/bot", tags=["bot"])


class BotConfigUpdate(BaseModel):
    symbols: Optional[str] = None
    risk_percent: Optional[float] = None
    max_open_trades: Optional[int] = None
    timeframe: Optional[str] = None
    strategy: Optional[str] = None


@router.get("/status")
async def bot_status(db: Session = Depends(get_db)):
    config = db.query(BotConfig).first()
    state = get_bot_state()
    return {
        "is_running": config.is_running if config else False,
        "config": _serialize_config(config),
        "runtime": state,
    }


@router.post("/start")
async def bot_start(db: Session = Depends(get_db)):
    start_bot(db)
    return {"status": "started"}


@router.post("/stop")
async def bot_stop(db: Session = Depends(get_db)):
    stop_bot(db)
    return {"status": "stopped"}


@router.put("/config")
async def update_config(body: BotConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(BotConfig).first()
    if not config:
        config = BotConfig()
        db.add(config)

    if body.symbols is not None:
        config.symbols = body.symbols
    if body.risk_percent is not None:
        config.risk_percent = body.risk_percent
    if body.max_open_trades is not None:
        config.max_open_trades = body.max_open_trades
    if body.timeframe is not None:
        config.timeframe = body.timeframe
    if body.strategy is not None:
        config.strategy = body.strategy

    db.commit()
    return _serialize_config(config)


@router.get("/signals")
async def get_signals():
    state = get_bot_state()
    return state.get("last_signals", {})


def _serialize_config(config: Optional[BotConfig]) -> dict:
    if not config:
        return {}
    return {
        "id": config.id,
        "is_running": config.is_running,
        "symbols": config.symbols,
        "risk_percent": config.risk_percent,
        "max_open_trades": config.max_open_trades,
        "timeframe": config.timeframe,
        "strategy": config.strategy,
    }
