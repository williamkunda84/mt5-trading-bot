"""
Multi-strategy trade setup detection engine.

Eight independent strategies vote on setups; a setup is created when ≥2 agree
on the same direction. Each setup carries entry, SL, TP1/TP2/TP3 and an
eta_minutes estimate (time until the setup fully confirms).

Strategies
──────────
1.  EMA Confluence     – price above/below aligned EMA stack with pullback
2.  RSI Divergence     – price vs RSI hidden/regular divergence
3.  MACD Crossover     – MACD/signal cross + histogram direction shift
4.  BB Squeeze         – volatility compression breakout
5.  S/R Bounce         – reaction at key support/resistance level
6.  ICT Session Play   – session-open momentum (London / NY / Tokyo)
7.  Fibonacci          – price at 38.2 / 50 / 61.8 % retracement
8.  Candlestick        – engulfing, pin bar, hammer/shooting star
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.indicators import bars_to_df, calc_rsi, calc_macd, calc_atr, calc_bollinger


# ─── Data types ────────────────────────────────────────────────────────────────

class StrategyVote:
    def __init__(self, name: str, direction: str, confidence: float,
                 notes: str = "", eta_minutes: Optional[int] = None):
        self.name = name
        self.direction = direction          # "buy" | "sell"
        self.confidence = confidence        # 0.0 – 1.0
        self.notes = notes
        self.eta_minutes = eta_minutes      # None = already confirmed


class TradeSetupResult:
    def __init__(self, **kw):
        self.id: str = kw.get("id", str(uuid.uuid4()))
        self.symbol: str = kw["symbol"]
        self.timeframe: str = kw["timeframe"]
        self.direction: str = kw["direction"]           # "buy" | "sell"
        self.entry_price: float = kw["entry_price"]
        self.stop_loss: float = kw["stop_loss"]
        self.take_profit_1: float = kw["take_profit_1"]
        self.take_profit_2: float = kw["take_profit_2"]
        self.take_profit_3: float = kw["take_profit_3"]
        self.confidence: float = kw["confidence"]       # 0 – 100
        self.strategies_confirmed: List[str] = kw["strategies_confirmed"]
        self.strategy_details: List[dict] = kw["strategy_details"]
        self.status: str = kw.get("status", "confirmed")
        self.eta_minutes: Optional[int] = kw.get("eta_minutes")
        self.rr_ratio: float = kw.get("rr_ratio", 2.0)
        self.notes: str = kw.get("notes", "")
        self.detected_at: str = datetime.now(tz=timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return self.__dict__


# ─── Session times (UTC) ───────────────────────────────────────────────────────

SESSION_OPENS = {
    "Tokyo":  (0, 0),
    "London": (8, 0),
    "NY":     (13, 0),
}


def _minutes_to_next_session() -> List[Tuple[str, int]]:
    now = datetime.now(tz=timezone.utc)
    results = []
    for name, (h, m) in SESSION_OPENS.items():
        session_today = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if session_today <= now:
            session_today += timedelta(days=1)
        delta = int((session_today - now).total_seconds() / 60)
        results.append((name, delta))
    return results


# ─── Timeframe helpers ─────────────────────────────────────────────────────────

TF_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}


def _tf_minutes(tf: str) -> int:
    return TF_MINUTES.get(tf, 60)


def _bar_remaining_minutes(tf: str) -> int:
    """Rough estimate of minutes left in the current bar."""
    now = datetime.now(tz=timezone.utc)
    bar_len = _tf_minutes(tf)
    elapsed = (now.minute % bar_len) + now.second / 60
    return max(1, int(bar_len - elapsed))


# ─── Price / ATR helpers ───────────────────────────────────────────────────────

def _sl_tp(price: float, direction: str, atr: float, digits: int,
           atr_sl: float = 1.5, rr1: float = 1.5, rr2: float = 2.5, rr3: float = 4.0):
    sl_dist = atr * atr_sl
    tp1_dist = sl_dist * rr1
    tp2_dist = sl_dist * rr2
    tp3_dist = sl_dist * rr3
    sign = 1 if direction == "buy" else -1
    r = lambda v: round(v, digits)
    return (
        r(price - sign * sl_dist),
        r(price + sign * tp1_dist),
        r(price + sign * tp2_dist),
        r(price + sign * tp3_dist),
    )


# ─── 1. EMA Confluence ────────────────────────────────────────────────────────

def _ema_confluence(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """
    Bullish: price > EMA20 > EMA50 > EMA200 and pulled back close to EMA20.
    Bearish: inverse stack, price bouncing up toward EMA20.
    """
    price = ind.get("price", 0)
    e20, e50, e200 = ind.get("ema20", 0), ind.get("ema50", 0), ind.get("ema200", 0)
    if not all([price, e20, e50, e200]):
        return None

    pullback_pct = abs(price - e20) / e20 * 100

    if e20 > e50 > e200 and price > e50:
        if pullback_pct < 0.5:            # within 0.5 % of EMA20
            conf = 0.80
            note = f"Full bull stack; price at EMA20 ({price:.5f}≈{e20:.5f})"
        elif pullback_pct < 1.0:
            conf = 0.60
            note = f"Bull stack; near EMA20 ({pullback_pct:.2f}% away)"
        else:
            return None
        return StrategyVote("EMA Confluence", "buy", conf, note,
                            eta_minutes=_bar_remaining_minutes(tf))

    if e20 < e50 < e200 and price < e50:
        if pullback_pct < 0.5:
            conf = 0.80
            note = f"Full bear stack; price at EMA20 ({price:.5f}≈{e20:.5f})"
        elif pullback_pct < 1.0:
            conf = 0.60
            note = f"Bear stack; near EMA20 ({pullback_pct:.2f}% away)"
        else:
            return None
        return StrategyVote("EMA Confluence", "sell", conf, note,
                            eta_minutes=_bar_remaining_minutes(tf))
    return None


# ─── 2. RSI Divergence ────────────────────────────────────────────────────────

def _rsi_divergence(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """Regular + hidden divergence over last 20 bars."""
    closes = df["close"]
    if len(closes) < 20:
        return None

    rsi = calc_rsi(closes).dropna()
    if len(rsi) < 20:
        return None

    prices = closes.iloc[-20:].values
    rsi_vals = rsi.iloc[-20:].values

    ph = prices[-1]
    rh = rsi_vals[-1]
    prev_ph = max(prices[:-3])
    prev_rh = max(rsi_vals[:-3])
    pl = prices[-1]
    rl = rsi_vals[-1]
    prev_pl = min(prices[:-3])
    prev_rl = min(rsi_vals[:-3])

    # Bearish divergence: price HH, RSI LH
    if ph > prev_ph and rh < prev_rh and rh > 55:
        conf = min(0.85, 0.55 + (ph - prev_ph) / prev_ph * 50)
        return StrategyVote("RSI Divergence", "sell", conf,
                            f"Bearish div: price HH {ph:.5f}>{prev_ph:.5f}, RSI LH {rh:.1f}<{prev_rh:.1f}",
                            eta_minutes=0)

    # Bullish divergence: price LL, RSI HL
    if pl < prev_pl and rl > prev_rl and rl < 45:
        conf = min(0.85, 0.55 + (prev_pl - pl) / prev_pl * 50)
        return StrategyVote("RSI Divergence", "buy", conf,
                            f"Bullish div: price LL {pl:.5f}<{prev_pl:.5f}, RSI HL {rl:.1f}>{prev_rl:.1f}",
                            eta_minutes=0)
    return None


# ─── 3. MACD Crossover ────────────────────────────────────────────────────────

def _macd_crossover(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """Fresh MACD/signal cross within last 3 bars, with RSI confirmation."""
    closes = df["close"]
    macd_line, sig_line, hist = calc_macd(closes)
    if len(hist) < 5:
        return None

    h = hist.iloc[-5:].values
    rsi = ind.get("rsi", 50)

    # Bull cross: histogram turned positive in last 2 bars
    if h[-1] > 0 and h[-2] <= 0 and 30 < rsi < 65:
        conf = 0.70 + min(0.15, abs(h[-1]) * 1000)
        return StrategyVote("MACD Crossover", "buy", min(conf, 0.85),
                            f"Bull cross; hist={h[-1]:.6f}, RSI={rsi:.1f}",
                            eta_minutes=0)

    # Bear cross
    if h[-1] < 0 and h[-2] >= 0 and 35 < rsi < 70:
        conf = 0.70 + min(0.15, abs(h[-1]) * 1000)
        return StrategyVote("MACD Crossover", "sell", min(conf, 0.85),
                            f"Bear cross; hist={h[-1]:.6f}, RSI={rsi:.1f}",
                            eta_minutes=0)

    # Imminent cross (about to cross next bar)
    if abs(h[-1]) < abs(h[-2]) * 0.3:
        direction = "buy" if h[-1] > 0 else "sell"
        if (direction == "buy" and 30 < rsi < 60) or (direction == "sell" and 40 < rsi < 70):
            return StrategyVote("MACD Crossover", direction, 0.55,
                                f"Imminent cross; hist shrinking {h[-2]:.6f}→{h[-1]:.6f}",
                                eta_minutes=_bar_remaining_minutes(tf))
    return None


# ─── 4. Bollinger Band Squeeze Breakout ───────────────────────────────────────

def _bb_squeeze(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """BB width at N-bar low = squeeze; price breaking out = setup."""
    closes = df["close"]
    upper, mid, lower = calc_bollinger(closes)
    bb_width = ((upper - lower) / mid).dropna()
    if len(bb_width) < 20:
        return None

    current_bw = bb_width.iloc[-1]
    min_20 = bb_width.iloc[-20:].min()
    avg_20 = bb_width.iloc[-20:].mean()

    price = ind.get("price", 0)
    atr = ind.get("atr", 0)

    # Squeeze: width near 20-bar low
    is_squeeze = current_bw <= min_20 * 1.15
    # Breakout: price outside bands
    above = price > upper.iloc[-1]
    below = price < lower.iloc[-1]

    if is_squeeze and above:
        conf = 0.75 + min(0.15, (current_bw / avg_20) * 0.1)
        return StrategyVote("BB Squeeze Breakout", "buy", conf,
                            f"Squeeze breakout UP; BBW={current_bw:.4f} (20-bar low={min_20:.4f})",
                            eta_minutes=0)
    if is_squeeze and below:
        conf = 0.75 + min(0.15, (current_bw / avg_20) * 0.1)
        return StrategyVote("BB Squeeze Breakout", "sell", conf,
                            f"Squeeze breakout DOWN; BBW={current_bw:.4f} (20-bar low={min_20:.4f})",
                            eta_minutes=0)
    # Pre-squeeze (might break out next bar)
    if is_squeeze and not above and not below:
        direction = "buy" if price > mid.iloc[-1] else "sell"
        return StrategyVote("BB Squeeze Breakout", direction, 0.50,
                            f"Squeeze building; BBW={current_bw:.4f}, awaiting breakout",
                            eta_minutes=_bar_remaining_minutes(tf))
    return None


# ─── 5. Support / Resistance Bounce ──────────────────────────────────────────

def _sr_bounce(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """Price at a key S/R level with a reversal signal."""
    price = ind.get("price", 0)
    support = ind.get("support", 0)
    resistance = ind.get("resistance", 0)
    rsi = ind.get("rsi", 50)
    if not price:
        return None

    tol = price * 0.0015        # 0.15 % tolerance

    if support and abs(price - support) <= tol:
        conf = 0.65 + (0.20 if rsi < 40 else 0.0)
        return StrategyVote("S/R Bounce", "buy", min(conf, 0.85),
                            f"Price at support {support:.5f} (Δ={abs(price-support):.5f}), RSI={rsi:.1f}",
                            eta_minutes=_bar_remaining_minutes(tf))

    if resistance and abs(price - resistance) <= tol:
        conf = 0.65 + (0.20 if rsi > 60 else 0.0)
        return StrategyVote("S/R Bounce", "sell", min(conf, 0.85),
                            f"Price at resistance {resistance:.5f} (Δ={abs(price-resistance):.5f}), RSI={rsi:.1f}",
                            eta_minutes=_bar_remaining_minutes(tf))
    return None


# ─── 6. ICT Session Play ──────────────────────────────────────────────────────

def _session_play(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """Setup at key level triggering within 60 min of a major session open."""
    sessions = _minutes_to_next_session()
    for session_name, eta in sessions:
        if 0 < eta <= 60:
            # Check if price is at a meaningful level
            price = ind.get("price", 0)
            support = ind.get("support", 0)
            resistance = ind.get("resistance", 0)
            rsi = ind.get("rsi", 50)
            atr = ind.get("atr", 0)

            if not price or not atr:
                continue

            near_support = support and abs(price - support) < atr * 2
            near_resistance = resistance and abs(price - resistance) < atr * 2
            trend_bull = ind.get("above_ema50", False)
            trend_bear = not ind.get("above_ema50", True)

            if near_support and trend_bull:
                return StrategyVote(
                    "ICT Session Play", "buy", 0.72,
                    f"{session_name} open in {eta}min; price near support {support:.5f} in bull trend",
                    eta_minutes=eta,
                )
            if near_resistance and trend_bear:
                return StrategyVote(
                    "ICT Session Play", "sell", 0.72,
                    f"{session_name} open in {eta}min; price near resistance {resistance:.5f} in bear trend",
                    eta_minutes=eta,
                )
    return None


# ─── 7. Fibonacci Retracement ─────────────────────────────────────────────────

def _fibonacci(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """Price at 38.2, 50, or 61.8% retracement of recent swing."""
    closes = df["close"]
    if len(closes) < 30:
        return None

    recent = closes.iloc[-30:]
    swing_high = float(recent.max())
    swing_low = float(recent.min())
    swing_range = swing_high - swing_low
    if swing_range < 1e-10:
        return None

    price = ind.get("price", 0)
    rsi = ind.get("rsi", 50)
    trend_bull = ind.get("above_ema50", False)
    atr = ind.get("atr", swing_range * 0.05)

    fib_levels = {
        "38.2%": swing_high - 0.382 * swing_range,
        "50.0%": swing_high - 0.500 * swing_range,
        "61.8%": swing_high - 0.618 * swing_range,
    }

    tol = atr * 0.8

    for label, level in fib_levels.items():
        if abs(price - level) <= tol:
            if trend_bull and rsi < 55:
                conf = {"38.2%": 0.60, "50.0%": 0.70, "61.8%": 0.78}[label]
                return StrategyVote("Fibonacci", "buy", conf,
                                    f"Price at {label} retracement ({level:.5f}); swing {swing_low:.5f}–{swing_high:.5f}",
                                    eta_minutes=_bar_remaining_minutes(tf))
            if not trend_bull and rsi > 45:
                conf = {"38.2%": 0.60, "50.0%": 0.70, "61.8%": 0.78}[label]
                return StrategyVote("Fibonacci", "sell", conf,
                                    f"Price at {label} retracement ({level:.5f}); swing {swing_low:.5f}–{swing_high:.5f}",
                                    eta_minutes=_bar_remaining_minutes(tf))
    return None


# ─── 8. Candlestick Pattern ───────────────────────────────────────────────────

def _candlestick_pattern(df: pd.DataFrame, ind: dict, tf: str) -> Optional[StrategyVote]:
    """Engulfing, pin bar, hammer / shooting star."""
    if len(df) < 3:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]
    o, h, l, c = last["open"], last["high"], last["low"], last["close"]
    po, ph, pl, pc = prev["open"], prev["high"], prev["low"], prev["close"]
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    total_range = h - l or 1e-10
    rsi = ind.get("rsi", 50)

    # Bullish engulfing
    if c > o and pc < po and c > po and o < pc:
        return StrategyVote("Candlestick Pattern", "buy", 0.75,
                            f"Bullish engulfing at {c:.5f}; RSI={rsi:.1f}",
                            eta_minutes=0)

    # Bearish engulfing
    if c < o and pc > po and c < po and o > pc:
        return StrategyVote("Candlestick Pattern", "sell", 0.75,
                            f"Bearish engulfing at {c:.5f}; RSI={rsi:.1f}",
                            eta_minutes=0)

    # Bullish pin bar / hammer (long lower wick, small body)
    if lower_wick > body * 2.5 and lower_wick > upper_wick * 2 and rsi < 55:
        return StrategyVote("Candlestick Pattern", "buy", 0.68,
                            f"Bullish pin bar; lower wick {lower_wick:.5f} vs body {body:.5f}",
                            eta_minutes=_bar_remaining_minutes(tf))

    # Bearish pin bar / shooting star (long upper wick, small body)
    if upper_wick > body * 2.5 and upper_wick > lower_wick * 2 and rsi > 45:
        return StrategyVote("Candlestick Pattern", "sell", 0.68,
                            f"Bearish pin bar; upper wick {upper_wick:.5f} vs body {body:.5f}",
                            eta_minutes=_bar_remaining_minutes(tf))

    # Doji at key level (indecision – upcoming)
    if body / total_range < 0.1:
        sr_nearby = (
            ind.get("support") and abs(ind["price"] - ind["support"]) < ind.get("atr", 1) * 1.5
            or ind.get("resistance") and abs(ind["price"] - ind["resistance"]) < ind.get("atr", 1) * 1.5
        )
        if sr_nearby:
            direction = "buy" if ind.get("above_ema50") else "sell"
            return StrategyVote("Candlestick Pattern", direction, 0.52,
                                f"Doji at key level; awaiting direction",
                                eta_minutes=_bar_remaining_minutes(tf))
    return None


# ─── Setup merger / aggregator ────────────────────────────────────────────────

DETECTORS = [
    _ema_confluence,
    _rsi_divergence,
    _macd_crossover,
    _bb_squeeze,
    _sr_bounce,
    _session_play,
    _fibonacci,
    _candlestick_pattern,
]

MIN_STRATEGIES = 2
MIN_CONFIDENCE = 0.55


def detect_setups(bars: list, symbol: str, timeframe: str,
                  digits: int = 5) -> List[TradeSetupResult]:
    """
    Run all detectors → group votes by direction → build confirmed setups.
    Returns list of TradeSetupResult (usually 0–2 per call).
    """
    if len(bars) < 30:
        return []

    from app.core.indicators import full_analysis, bars_to_df, calc_atr
    df = bars_to_df(bars)
    ind = full_analysis(bars)
    if not ind:
        return []

    price = ind.get("price", 0)
    atr = ind.get("atr", price * 0.001)

    votes: Dict[str, List[StrategyVote]] = {"buy": [], "sell": []}

    for detector in DETECTORS:
        try:
            vote = detector(df, ind, timeframe)
        except Exception:
            vote = None
        if vote and vote.confidence >= MIN_CONFIDENCE:
            votes[vote.direction].append(vote)

    results: List[TradeSetupResult] = []

    for direction, dir_votes in votes.items():
        if len(dir_votes) < MIN_STRATEGIES:
            continue

        # Weighted confidence average
        total_conf = sum(v.confidence for v in dir_votes) / len(dir_votes) * 100

        # eta_minutes = min of all ETAs (earliest the setup triggers)
        etas = [v.eta_minutes for v in dir_votes if v.eta_minutes is not None]
        eta = min(etas) if etas else 0

        # Determine status
        status = "confirmed" if eta == 0 else "forming"

        sl, tp1, tp2, tp3 = _sl_tp(price, direction, atr, digits)
        rr = abs(tp2 - price) / abs(sl - price) if abs(sl - price) > 0 else 2.0

        setup = TradeSetupResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry_price=round(price, digits),
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            confidence=round(total_conf, 1),
            strategies_confirmed=[v.name for v in dir_votes],
            strategy_details=[
                {
                    "name": v.name,
                    "confidence": round(v.confidence * 100, 1),
                    "notes": v.notes,
                    "eta_minutes": v.eta_minutes,
                }
                for v in dir_votes
            ],
            status=status,
            eta_minutes=eta,
            rr_ratio=round(rr, 2),
            notes=(f"{len(dir_votes)}/{len(DETECTORS)} strategies agree. "
                   f"{'Alert: setup forms in ' + str(eta) + 'min' if 0 < eta <= 60 else ''}"),
        )
        results.append(setup)

    return results


def scan_all(bars_map: Dict[str, Dict[str, list]], digits_map: Dict[str, int]
             ) -> List[TradeSetupResult]:
    """
    bars_map: { symbol: { timeframe: [Bar, ...] } }
    Returns deduplicated setups across all symbol/TF combos.
    """
    all_setups = []
    for symbol, tf_bars in bars_map.items():
        digits = digits_map.get(symbol, 5)
        for tf, bars in tf_bars.items():
            try:
                setups = detect_setups(bars, symbol, tf, digits)
                all_setups.extend(setups)
            except Exception:
                pass
    return all_setups
