"""
Direct MetaTrader 5 connector using the native MetaTrader5 Python package.
Windows-only. Requires MT5 terminal to be installed and running.
Set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER in .env.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

import MetaTrader5 as mt5

from app.services.mt5_connector import (
    MT5Connector, AccountInfo, Bar, OrderResult, SymbolInfo,
)
from app.config import settings

log = logging.getLogger(__name__)

TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


class DirectMT5Connector(MT5Connector):
    """Thin async wrapper around the synchronous MetaTrader5 package."""

    async def connect(self) -> bool:
        ok = await asyncio.to_thread(self._connect_sync)
        if ok:
            log.info("Connected to MT5 terminal")
        else:
            log.error("MT5 connect failed: %s", mt5.last_error())
        return ok

    def _connect_sync(self) -> bool:
        if not mt5.initialize():
            return False
        login = settings.mt5_login
        password = settings.mt5_password
        server = settings.mt5_server
        if login and password and server:
            return mt5.login(login, password=password, server=server)
        # No credentials — use whatever account is already logged in the terminal
        info = mt5.account_info()
        return info is not None

    async def get_account_info(self) -> AccountInfo:
        info = await asyncio.to_thread(mt5.account_info)
        if info is None:
            raise RuntimeError(f"MT5 account_info failed: {mt5.last_error()}")
        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            currency=info.currency,
        )

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        tick = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
        info = await asyncio.to_thread(mt5.symbol_info, symbol)
        if tick is None or info is None:
            raise RuntimeError(f"MT5 symbol_info failed for {symbol}: {mt5.last_error()}")
        return SymbolInfo(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            digits=info.digits,
            point=info.point,
            contract_size=info.trade_contract_size,
        )

    async def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_H1)
        rates = await asyncio.to_thread(mt5.copy_rates_from_pos, symbol, tf, 0, count)
        if rates is None:
            raise RuntimeError(f"MT5 copy_rates failed for {symbol}/{timeframe}: {mt5.last_error()}")
        bars = []
        for r in rates:
            bars.append(Bar(
                time=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["tick_volume"]),
            ))
        return bars

    async def place_order(self, symbol: str, order_type: str, volume: float,
                          price: float, sl: float, tp: float, comment: str = "") -> OrderResult:
        action = mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL
        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   symbol,
            "volume":   volume,
            "type":     action,
            "price":    price,
            "sl":       sl,
            "tp":       tp,
            "comment":  comment,
            "type_time":mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            code = result.retcode if result else "none"
            raise RuntimeError(f"MT5 order_send failed: retcode={code}")
        return OrderResult(
            ticket=result.order,
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            open_price=result.price,
            sl=sl,
            tp=tp,
        )

    async def close_order(self, ticket: int) -> bool:
        pos = await asyncio.to_thread(mt5.positions_get, ticket=ticket)
        if not pos:
            return False
        p = pos[0]
        close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = await asyncio.to_thread(mt5.symbol_info_tick, p.symbol)
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   p.symbol,
            "volume":   p.volume,
            "type":     close_type,
            "position": ticket,
            "price":    price,
            "comment":  "close",
            "type_time":mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    async def get_open_orders(self) -> List[dict]:
        positions = await asyncio.to_thread(mt5.positions_get)
        if positions is None:
            return []
        return [
            {
                "ticket":     p.ticket,
                "symbol":     p.symbol,
                "order_type": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                "volume":     p.volume,
                "open_price": p.price_open,
                "sl":         p.sl,
                "tp":         p.tp,
                "profit":     p.profit,
            }
            for p in positions
        ]

    async def disconnect(self):
        await asyncio.to_thread(mt5.shutdown)
