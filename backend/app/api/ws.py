"""
WebSocket endpoint that streams live prices + bot signals every second.
"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.mt5_connector import get_mt5
from app.services.trading_bot import get_bot_state

log = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY"]


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
        log.warning("WS error: %s", e)
