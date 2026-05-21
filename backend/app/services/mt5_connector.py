"""
MT5 abstraction layer.

Modes:
  simulate   – built-in price simulator (no external deps, great for dev/demo)
  metaapi    – MetaAPI cloud bridge (works on Railway / any Linux host)
  direct     – native MetaTrader5 Python package (Windows only)
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx
import numpy as np

from app.config import settings


# ─── Data classes ──────────────────────────────────────────────────────────────

class AccountInfo:
    def __init__(self, balance: float, equity: float, margin: float, free_margin: float, currency: str = "USD"):
        self.balance = balance
        self.equity = equity
        self.margin = margin
        self.free_margin = free_margin
        self.currency = currency


class Bar:
    def __init__(self, time: datetime, open: float, high: float, low: float, close: float, volume: float):
        self.time = time
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


class OrderResult:
    def __init__(self, ticket: int, symbol: str, order_type: str, volume: float,
                 open_price: float, sl: float, tp: float):
        self.ticket = ticket
        self.symbol = symbol
        self.order_type = order_type
        self.volume = volume
        self.open_price = open_price
        self.sl = sl
        self.tp = tp
        self.success = True


class SymbolInfo:
    def __init__(self, symbol: str, bid: float, ask: float, digits: int, point: float,
                 contract_size: float = 100_000):
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.digits = digits
        self.point = point
        self.contract_size = contract_size
        self.spread = round((ask - bid) / point)


# ─── Base connector ────────────────────────────────────────────────────────────

class MT5Connector(ABC):
    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def get_account_info(self) -> AccountInfo: ...

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> SymbolInfo: ...

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Bar]: ...

    @abstractmethod
    async def place_order(self, symbol: str, order_type: str, volume: float,
                          price: float, sl: float, tp: float, comment: str = "") -> OrderResult: ...

    @abstractmethod
    async def close_order(self, ticket: int) -> bool: ...

    @abstractmethod
    async def get_open_orders(self) -> List[dict]: ...

    @abstractmethod
    async def disconnect(self): ...


# ─── Simulation connector ──────────────────────────────────────────────────────

class SimulatedConnector(MT5Connector):
    """
    Realistic price simulator using geometric Brownian motion.
    Generates OHLCV data and fake account so the full UI works without MT5.
    """

    BASE_PRICES = {
        "EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 149.50,
        "XAUUSD": 2020.00, "GBPJPY": 189.00, "EURJPY": 162.00,
        "AUDUSD": 0.6550, "USDCAD": 1.3650, "USDCHF": 0.9050,
        "NZDUSD": 0.6050,
    }

    DIGITS = {
        "USDJPY": 3, "GBPJPY": 3, "EURJPY": 3,
        "XAUUSD": 2,
    }

    def __init__(self):
        self._balance = 10_000.0
        self._equity = 10_000.0
        self._orders: List[dict] = []
        self._ticket_counter = 1000
        self._price_cache: Dict[str, List[Bar]] = {}

    async def connect(self) -> bool:
        return True

    async def get_account_info(self) -> AccountInfo:
        floating_pnl = sum(o.get("floating_pnl", 0) for o in self._orders)
        equity = self._balance + floating_pnl
        margin = sum(o.get("margin", 0) for o in self._orders)
        return AccountInfo(
            balance=round(self._balance, 2),
            equity=round(equity, 2),
            margin=round(margin, 2),
            free_margin=round(equity - margin, 2),
        )

    def _digits(self, symbol: str) -> int:
        return self.DIGITS.get(symbol, 5)

    def _point(self, symbol: str) -> float:
        d = self._digits(symbol)
        return 10 ** -d

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        bars = await self.get_ohlcv(symbol, "M1", 2)
        price = bars[-1].close if bars else self.BASE_PRICES.get(symbol, 1.0)
        spread_pips = 2
        point = self._point(symbol)
        bid = round(price, self._digits(symbol))
        ask = round(price + spread_pips * point, self._digits(symbol))
        return SymbolInfo(symbol=symbol, bid=bid, ask=ask,
                          digits=self._digits(symbol), point=point)

    async def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        base = self.BASE_PRICES.get(symbol, 1.0)
        digits = self._digits(symbol)

        # Volatility per bar (annualised ~10–15%, scaled to bar duration)
        tf_minutes = {"M1": 1, "M5": 5, "M15": 15, "M30": 30,
                      "H1": 60, "H4": 240, "D1": 1440}.get(timeframe, 60)
        annual_vol = 0.12 if "JPY" not in symbol and "XAU" not in symbol else (
            0.08 if "JPY" in symbol else 0.15)
        bar_vol = annual_vol * math.sqrt(tf_minutes / 525_600)

        now = datetime.now(tz=timezone.utc)
        minutes_back = count * tf_minutes
        start = now - timedelta(minutes=minutes_back)

        rng = np.random.default_rng(seed=int(symbol[:4].encode().hex(), 16) % (2**32))
        returns = rng.normal(0, bar_vol, count)
        prices = base * np.cumprod(1 + returns)

        bars: List[Bar] = []
        for i, close in enumerate(prices):
            t = start + timedelta(minutes=i * tf_minutes)
            hi = close * (1 + abs(rng.normal(0, bar_vol * 0.5)))
            lo = close * (1 - abs(rng.normal(0, bar_vol * 0.5)))
            op = prices[i - 1] if i > 0 else close
            bars.append(Bar(
                time=t, open=round(op, digits),
                high=round(hi, digits), low=round(lo, digits),
                close=round(close, digits),
                volume=float(rng.integers(100, 5000)),
            ))
        return bars

    async def place_order(self, symbol: str, order_type: str, volume: float,
                          price: float, sl: float, tp: float, comment: str = "") -> OrderResult:
        self._ticket_counter += 1
        margin = volume * 1000  # simplified margin calc
        order = {
            "ticket": self._ticket_counter,
            "symbol": symbol,
            "type": order_type,
            "volume": volume,
            "open_price": price,
            "sl": sl,
            "tp": tp,
            "opened_at": datetime.now(tz=timezone.utc).isoformat(),
            "floating_pnl": 0.0,
            "margin": margin,
            "comment": comment,
        }
        self._orders.append(order)
        return OrderResult(self._ticket_counter, symbol, order_type, volume, price, sl, tp)

    async def close_order(self, ticket: int) -> bool:
        for i, o in enumerate(self._orders):
            if o["ticket"] == ticket:
                info = await self.get_symbol_info(o["symbol"])
                close_price = info.bid if o["type"] == "buy" else info.ask
                point = self._point(o["symbol"])
                pip_value = o["volume"] * 10  # simplified
                pips = ((close_price - o["open_price"]) / point) if o["type"] == "buy" \
                    else ((o["open_price"] - close_price) / point)
                profit = pips * pip_value * 0.01
                self._balance += profit
                self._orders.pop(i)
                return True
        return False

    async def get_open_orders(self) -> List[dict]:
        # Refresh floating PnL
        for o in self._orders:
            info = await self.get_symbol_info(o["symbol"])
            point = self._point(o["symbol"])
            pip_value = o["volume"] * 10 * 0.01
            if o["type"] == "buy":
                pips = (info.bid - o["open_price"]) / point
            else:
                pips = (o["open_price"] - info.ask) / point
            o["floating_pnl"] = round(pips * pip_value, 2)
        return list(self._orders)

    async def disconnect(self):
        pass


# ─── MetaAPI connector (cloud, Railway-compatible) ────────────────────────────

class MetaApiConnector(MT5Connector):
    """
    Uses MetaAPI REST API (https://metaapi.cloud/).
    Works on any OS including Railway Linux containers.
    """

    BASE_URL = "https://mt-client-api-v1.london.agiliumtrade.ai"

    def __init__(self):
        self._token = settings.metaapi_token
        self._account_id = settings.metaapi_account_id
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            headers={"auth-token": self._token},
            timeout=30.0,
        )
        try:
            r = await self._client.get(
                f"{self.BASE_URL}/users/current/accounts/{self._account_id}"
            )
            return r.status_code == 200
        except Exception:
            return False

    def _headers(self):
        return {"auth-token": self._token, "Content-Type": "application/json"}

    async def get_account_info(self) -> AccountInfo:
        r = await self._client.get(
            f"{self.BASE_URL}/users/current/accounts/{self._account_id}/account-information",
        )
        d = r.json()
        return AccountInfo(
            balance=d.get("balance", 0),
            equity=d.get("equity", 0),
            margin=d.get("margin", 0),
            free_margin=d.get("freeMargin", 0),
            currency=d.get("currency", "USD"),
        )

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        r = await self._client.get(
            f"{self.BASE_URL}/users/current/accounts/{self._account_id}/symbols/{symbol}"
        )
        d = r.json()
        bid = d.get("bid", 0)
        ask = d.get("ask", 0)
        digits = d.get("digits", 5)
        point = 10 ** -digits
        return SymbolInfo(symbol=symbol, bid=bid, ask=ask, digits=digits, point=point)

    async def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        tf_map = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
                  "H1": "1h", "H4": "4h", "D1": "1d"}
        r = await self._client.get(
            f"{self.BASE_URL}/users/current/accounts/{self._account_id}"
            f"/historical-market-data/symbols/{symbol}/timeframes/{tf_map.get(timeframe, '1h')}/candles",
            params={"limit": count},
        )
        bars = []
        for c in r.json():
            bars.append(Bar(
                time=datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                open=c["open"], high=c["high"], low=c["low"],
                close=c["close"], volume=c.get("tickVolume", 0),
            ))
        return bars

    async def place_order(self, symbol: str, order_type: str, volume: float,
                          price: float, sl: float, tp: float, comment: str = "") -> OrderResult:
        payload = {
            "symbol": symbol,
            "actionType": "ORDER_TYPE_BUY" if order_type == "buy" else "ORDER_TYPE_SELL",
            "volume": volume,
            "stopLoss": sl,
            "takeProfit": tp,
            "comment": comment,
        }
        r = await self._client.post(
            f"{self.BASE_URL}/users/current/accounts/{self._account_id}/trade",
            json=payload,
        )
        d = r.json()
        ticket = d.get("orderId", random.randint(10000, 99999))
        return OrderResult(ticket, symbol, order_type, volume, price, sl, tp)

    async def close_order(self, ticket: int) -> bool:
        r = await self._client.post(
            f"{self.BASE_URL}/users/current/accounts/{self._account_id}/trade",
            json={"actionType": "POSITION_CLOSE_ID", "positionId": str(ticket)},
        )
        return r.status_code in (200, 201)

    async def get_open_orders(self) -> List[dict]:
        r = await self._client.get(
            f"{self.BASE_URL}/users/current/accounts/{self._account_id}/positions"
        )
        positions = r.json()
        return [
            {
                "ticket": p.get("id"),
                "symbol": p.get("symbol"),
                "type": "buy" if p.get("type") == "POSITION_TYPE_BUY" else "sell",
                "volume": p.get("volume"),
                "open_price": p.get("openPrice"),
                "sl": p.get("stopLoss"),
                "tp": p.get("takeProfit"),
                "floating_pnl": p.get("unrealizedProfit", 0),
                "opened_at": p.get("time"),
            }
            for p in (positions if isinstance(positions, list) else [])
        ]

    async def disconnect(self):
        if self._client:
            await self._client.aclose()


# ─── Factory ───────────────────────────────────────────────────────────────────

def get_connector() -> MT5Connector:
    mode = settings.trading_mode

    # Explicit direct mode — local MT5 terminal (Windows)
    if mode == "direct":
        try:
            from app.services.mt5_direct import DirectMT5Connector
            return DirectMT5Connector()
        except ImportError as e:
            raise RuntimeError(
                "TRADING_MODE=direct requires the MetaTrader5 package (Windows only). "
                f"Install it with: pip install MetaTrader5\nOriginal error: {e}"
            )

    # MetaAPI cloud bridge (live/demo on Linux/Railway)
    if mode in ("live", "demo") and settings.metaapi_token and settings.metaapi_account_id:
        return MetaApiConnector()

    # Fallback: direct MT5 if on Windows and no MetaAPI creds
    if mode in ("live", "demo"):
        try:
            from app.services.mt5_direct import DirectMT5Connector
            return DirectMT5Connector()
        except ImportError:
            pass

    return SimulatedConnector()


_connector: Optional[MT5Connector] = None


async def get_mt5() -> MT5Connector:
    global _connector
    if _connector is None:
        _connector = get_connector()
        await _connector.connect()
    return _connector
