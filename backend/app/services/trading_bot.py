"""
Trading bot engine.

Runs as a background task (via APScheduler).
Each tick:
  1. Fetch OHLCV from MT5
  2. Run indicators + composite AI score
  3. If score exceeds threshold → place order with ATR SL/TP
  4. Monitor open trades → close on TP/SL breach in simulate mode
  5. Snapshot wallet to DB for growth charting
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.indicators import full_analysis
from app.core.strategy import (
    composite_score,
    get_direction,
    calculate_position_size,
    calculate_sl_tp,
)
from app.models import BotConfig, Trade, WalletSnapshot
from app.services.mt5_connector import get_mt5

log = logging.getLogger(__name__)

# Shared runtime state (in-process, no Redis needed for single-instance)
_bot_state: Dict = {
    "running": False,
    "last_tick": None,
    "last_signals": {},
    "tick_count": 0,
    "errors": [],
}


def get_bot_state() -> Dict:
    return dict(_bot_state)


async def tick(db: Session) -> None:
    """Single bot iteration across all configured symbols."""
    _bot_state["tick_count"] += 1
    _bot_state["last_tick"] = datetime.now(tz=timezone.utc).isoformat()

    config = db.query(BotConfig).first()
    if not config or not config.is_running:
        return

    mt5 = await get_mt5()
    account = await mt5.get_account_info()
    symbols = [s.strip() for s in config.symbols.split(",") if s.strip()]

    open_trade_count = db.query(Trade).filter(Trade.status == "open").count()

    for symbol in symbols:
        try:
            await _process_symbol(db, mt5, symbol, config, account, open_trade_count)
        except Exception as exc:
            err = f"{symbol}: {exc}"
            log.error("Bot tick error %s", err)
            _bot_state["errors"] = ([err] + _bot_state["errors"])[:20]

    # Snapshot wallet for growth chart (once per tick)
    await _snapshot_wallet(db, account)


async def _process_symbol(db, mt5, symbol: str, config, account, open_trade_count: int):
    bars = await mt5.get_ohlcv(symbol, config.timeframe, settings.ai_lookback_bars)
    if len(bars) < 50:
        return

    ind = full_analysis(bars)
    if not ind:
        return

    score, sub_scores = composite_score(ind)
    direction = get_direction(score, settings.ai_confidence_threshold)

    _bot_state["last_signals"][symbol] = {
        "score": round(score, 3),
        "direction": direction,
        "indicators": {k: v for k, v in ind.items() if k != "candles"},
        "sub_scores": sub_scores,
        "updated": datetime.now(tz=timezone.utc).isoformat(),
    }

    if direction in ("buy", "sell") and open_trade_count < config.max_open_trades:
        # Check we don't already have an open trade for this symbol+direction
        existing = db.query(Trade).filter(
            Trade.symbol == symbol,
            Trade.status == "open",
            Trade.order_type == direction,
        ).first()
        if not existing:
            await _place_trade(db, mt5, symbol, direction, score, ind, sub_scores, config, account)
            open_trade_count += 1

    # Monitor open simulate-mode trades for SL/TP hits
    await _monitor_open_trades(db, mt5, symbol, ind)


async def _place_trade(db, mt5, symbol: str, direction: str, score: float,
                       ind: Dict, sub_scores: Dict, config, account):
    sym_info = await mt5.get_symbol_info(symbol)
    price = sym_info.ask if direction == "buy" else sym_info.bid
    atr = ind.get("atr", sym_info.point * 100)

    sl, tp = calculate_sl_tp(price, direction, atr, digits=sym_info.digits)
    sl_pips = abs(price - sl) / sym_info.point / 10

    volume = calculate_position_size(account.balance, config.risk_percent, sl_pips)

    result = await mt5.place_order(
        symbol=symbol,
        order_type=direction,
        volume=volume,
        price=price,
        sl=sl,
        tp=tp,
        comment=f"ForexBot|score={score:.2f}",
    )

    trade = Trade(
        id=str(uuid.uuid4()),
        symbol=symbol,
        order_type=direction,
        volume=volume,
        open_price=price,
        stop_loss=sl,
        take_profit=tp,
        status="open",
        strategy=config.strategy,
        signal_score=round(score, 4),
        ai_signals={"score": score, "sub_scores": sub_scores,
                    "rsi": ind.get("rsi"), "macd": ind.get("macd"),
                    "direction": direction},
        mt5_ticket=result.ticket,
    )
    db.add(trade)
    db.commit()
    log.info("Opened trade %s %s %s @ %.5f (score=%.2f)", symbol, direction, volume, price, score)


async def _monitor_open_trades(db, mt5, symbol: str, ind: Dict):
    """Check if any open sim trades have hit SL or TP."""
    open_trades = db.query(Trade).filter(
        Trade.symbol == symbol,
        Trade.status == "open",
    ).all()

    current_price = ind.get("price", 0)
    if not current_price:
        return

    for trade in open_trades:
        hit_tp = hit_sl = False
        if trade.order_type == "buy":
            hit_tp = trade.take_profit and current_price >= trade.take_profit
            hit_sl = trade.stop_loss and current_price <= trade.stop_loss
        else:
            hit_tp = trade.take_profit and current_price <= trade.take_profit
            hit_sl = trade.stop_loss and current_price >= trade.stop_loss

        if hit_tp or hit_sl:
            close_price = trade.take_profit if hit_tp else trade.stop_loss
            pips = (
                (close_price - trade.open_price) / (10 ** -5)
                if trade.order_type == "buy"
                else (trade.open_price - close_price) / (10 ** -5)
            )
            profit = round(pips * trade.volume * 10 * 0.01, 2)

            trade.status = "closed"
            trade.close_price = close_price
            trade.profit = profit
            trade.pips = round(pips, 1)
            trade.closed_at = datetime.now(tz=timezone.utc)
            trade.notes = "tp_hit" if hit_tp else "sl_hit"
            db.commit()
            log.info(
                "Closed trade %s %s: %s | profit=%.2f pips=%.1f",
                symbol, trade.order_type, trade.notes, profit, pips
            )


async def _snapshot_wallet(db, account):
    trades = db.query(Trade).all()
    closed = [t for t in trades if t.status == "closed"]
    wins = [t for t in closed if (t.profit or 0) > 0]

    snap = WalletSnapshot(
        balance=account.balance,
        equity=account.equity,
        free_margin=account.free_margin,
        total_trades=len(closed),
        winning_trades=len(wins),
        losing_trades=len(closed) - len(wins),
        total_profit=round(sum(t.profit or 0 for t in closed), 2),
        win_rate=round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
    )
    db.add(snap)
    db.commit()


# ─── Bot lifecycle ─────────────────────────────────────────────────────────────

def start_bot(db: Session):
    config = db.query(BotConfig).first()
    if not config:
        config = BotConfig()
        db.add(config)
    config.is_running = True
    db.commit()
    _bot_state["running"] = True
    _bot_state["errors"] = []


def stop_bot(db: Session):
    config = db.query(BotConfig).first()
    if config:
        config.is_running = False
        db.commit()
    _bot_state["running"] = False
