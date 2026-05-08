"""
Technical indicator calculations using pandas + ta library.
All functions accept a list of Bar objects and return a dict of indicator values.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd

try:
    import ta
    HAS_TA = True
except ImportError:
    HAS_TA = False


def bars_to_df(bars) -> pd.DataFrame:
    df = pd.DataFrame([{
        "time": b.time, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume,
    } for b in bars])
    df.set_index("time", inplace=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])
    return df


def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(closes: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(closes: pd.Series, period=20, std_dev=2):
    sma = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def calc_atr(df: pd.DataFrame, period=14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_stochastic(df: pd.DataFrame, k_period=14, d_period=3):
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
    d = k.rolling(d_period).mean()
    return k, d


def calc_support_resistance(df: pd.DataFrame, lookback=50) -> dict:
    """Find significant S/R levels using local extrema."""
    recent = df.tail(lookback)
    highs = recent["high"].values
    lows = recent["low"].values

    resistance_levels = []
    support_levels = []

    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resistance_levels.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            support_levels.append(lows[i])

    current_price = recent["close"].iloc[-1]
    nearest_resistance = min(
        [r for r in resistance_levels if r > current_price],
        default=current_price * 1.002
    )
    nearest_support = max(
        [s for s in support_levels if s < current_price],
        default=current_price * 0.998
    )

    return {
        "resistance": round(nearest_resistance, 5),
        "support": round(nearest_support, 5),
        "all_resistance": sorted(set(round(r, 5) for r in resistance_levels))[-3:],
        "all_support": sorted(set(round(s, 5) for s in support_levels))[:3],
    }


def full_analysis(bars) -> dict:
    """
    Run full indicator suite on bar data.
    Returns a flat dict with all indicator values (last bar).
    """
    if len(bars) < 30:
        return {}

    df = bars_to_df(bars)
    closes = df["close"]

    rsi = calc_rsi(closes)
    macd_line, signal_line, macd_hist = calc_macd(closes)
    bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
    atr = calc_atr(df)
    stoch_k, stoch_d = calc_stochastic(df)
    ema20 = closes.ewm(span=20, adjust=False).mean()
    ema50 = closes.ewm(span=50, adjust=False).mean()
    ema200 = closes.ewm(span=200, adjust=False).mean()
    sr = calc_support_resistance(df)

    price = closes.iloc[-1]

    return {
        "price": round(price, 5),
        "rsi": round(rsi.iloc[-1], 2) if not math.isnan(rsi.iloc[-1]) else 50.0,
        "rsi_prev": round(rsi.iloc[-2], 2) if len(rsi) > 1 else 50.0,
        "macd": round(macd_line.iloc[-1], 6),
        "macd_signal": round(signal_line.iloc[-1], 6),
        "macd_hist": round(macd_hist.iloc[-1], 6),
        "macd_hist_prev": round(macd_hist.iloc[-2], 6) if len(macd_hist) > 1 else 0,
        "bb_upper": round(bb_upper.iloc[-1], 5),
        "bb_mid": round(bb_mid.iloc[-1], 5),
        "bb_lower": round(bb_lower.iloc[-1], 5),
        "bb_width": round((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] * 100, 4),
        "atr": round(atr.iloc[-1], 5),
        "stoch_k": round(stoch_k.iloc[-1], 2),
        "stoch_d": round(stoch_d.iloc[-1], 2),
        "ema20": round(ema20.iloc[-1], 5),
        "ema50": round(ema50.iloc[-1], 5),
        "ema200": round(ema200.iloc[-1], 5),
        "above_ema20": price > ema20.iloc[-1],
        "above_ema50": price > ema50.iloc[-1],
        "above_ema200": price > ema200.iloc[-1],
        "ema20_above_50": ema20.iloc[-1] > ema50.iloc[-1],
        "ema50_above_200": ema50.iloc[-1] > ema200.iloc[-1],
        **sr,
        "candles": [
            {
                "time": b.time.isoformat(),
                "open": b.open, "high": b.high,
                "low": b.low, "close": b.close, "volume": b.volume,
            }
            for b in bars[-100:]
        ],
    }
