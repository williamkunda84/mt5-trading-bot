"""
WebSocket endpoints.

/ws/live   – tick stream (prices, account, bot signals) every 1 s
/ws/alerts – setup alert stream; pushes new/updated setups as they arrive
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.mt5_connector import get_mt5
from app.services.trading_bot import get_bot_state

log = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY"]

# ─── Alert broadcaster ────────────────────────────────────────────────────────
# Shared set of connected alert subscribers; populated by /ws/alerts connections.
_alert_subscribers: Set[WebSocket] = set()


async def broadcast_setup_alert(setup: dict):
    """Called by the setup scanner when a high-confidence alert is detected."""
    dead = set()
    for ws in _alert_subscribers:
        try:
            await ws.send_text(json.dumps({"type": "setup_alert", "setup": setup}))
        except Exception:
            dead.add(ws)
    _alert_subscribers.difference_update(dead)


async def maybe_broadcast_alerts(db):
    """
    Check DB for unsent alerts with eta ≤ 60 and confidence ≥ 65.
    Called from the scheduler tick.
    """
    from app.models import TradeSetup
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=2)

    unsent = db.query(TradeSetup).filter(
        TradeSetup.status.in_(["forming", "confirmed"]),
        TradeSetup.alert_sent == False,
        TradeSetup.confidence >= 65,
        TradeSetup.detected_at >= cutoff,
    ).all()

    for s in unsent:
        is_alert = s.status == "confirmed" or (s.eta_minutes is not None and s.eta_minutes <= 60)
        if is_alert:
            payload = {
                "id": s.id,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "direction": s.direction,
                "entry_price": s.entry_price,
                "stop_loss": s.stop_loss,
                "take_profit_1": s.take_profit_1,
                "take_profit_2": s.take_profit_2,
                "confidence": s.confidence,
                "eta_minutes": s.eta_minutes,
                "strategies_confirmed": s.strategies_confirmed,
                "status": s.status,
                "detected_at": s.detected_at.isoformat() if s.detected_at else None,
            }
            await broadcast_setup_alert(payload)
            s.alert_sent = True
    db.commit()


# ─── /ws/live ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            mt5 = await get_mt5()
            prices = {}
            for sym in SYMBOLS:
                try:
                    info = await mt5.get_symbol_info(sym)
                    prices[sym] = {"bid": info.bid, "ask": info.ask, "spread": info.spread}
                except Exception:
                    pass

            account = await mt5.get_account_info()
            state = get_bot_state()

            payload = {
                "type": "tick",
                "prices": prices,
                "account": {
                    "balance": account.balance,
                    "equity": account.equity,
                    "free_margin": account.free_margin,
                },
                "bot_running": state.get("running", False),
                "signals": state.get("last_signals", {}),
                "tick": state.get("tick_count", 0),
            }
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("WS live error: %s", e)


# ─── /ws/alerts ───────────────────────────────────────────────────────────────

@router.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket):
    """
    Subscribe to setup alerts.
    Server pushes { type: "setup_alert", setup: {...} } whenever a new
    high-confidence setup with eta ≤ 60 min is detected.
    Client can send { type: "ping" } for keepalive.
    """
    await ws.accept()
    _alert_subscribers.add(ws)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30)
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive
                await ws.send_text(json.dumps({"type": "heartbeat",
                                               "ts": datetime.now(tz=timezone.utc).isoformat()}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("WS alerts error: %s", e)
    finally:
        _alert_subscribers.discard(ws)
