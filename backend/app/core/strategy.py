"""
Multi-signal AI trading strategy.

Combines 6 independent sub-signals into a composite score in [-1, +1]:
  +1 = strong buy  |  -1 = strong sell  |  0 = neutral

Sub-signals:
  1. Trend alignment   (EMA 20/50/200 stack)
  2. Momentum          (RSI)
  3. MACD              (line vs signal, histogram direction)
  4. Bollinger Bands   (price position + squeeze)
  5. Stochastic        (K/D cross)
  6. Support/Resistance (proximity to key levels)

Growth forecast uses linear regression on recent signal scores + equity curve.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

import numpy as np

from app.config import settings


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ─── Individual sub-signals ────────────────────────────────────────────────────

def signal_trend(ind: Dict[str, Any]) -> float:
    """EMA alignment: +1 full bull stack, -1 full bear stack."""
    score = 0.0
    if ind.get("above_ema20"): score += 0.2
    else: score -= 0.2
    if ind.get("above_ema50"): score += 0.3
    else: score -= 0.3
    if ind.get("above_ema200"): score += 0.3
    else: score -= 0.3
    if ind.get("ema20_above_50"): score += 0.1
    else: score -= 0.1
    if ind.get("ema50_above_200"): score += 0.1
    else: score -= 0.1
    return _clamp(score)


def signal_rsi(ind: Dict[str, Any]) -> float:
    """RSI momentum: oversold → buy bias, overbought → sell bias."""
    rsi = ind.get("rsi", 50.0)
    rsi_prev = ind.get("rsi_prev", 50.0)

    if rsi < 30:
        base = 0.8
    elif rsi < 40:
        base = 0.4
    elif rsi > 70:
        base = -0.8
    elif rsi > 60:
        base = -0.4
    else:
        base = 0.0

    # Trend within RSI
    momentum = (rsi - rsi_prev) / 10.0
    return _clamp(base + momentum * 0.2)


def signal_macd(ind: Dict[str, Any]) -> float:
    """MACD line vs signal cross + histogram turning point."""
    macd = ind.get("macd", 0)
    sig = ind.get("macd_signal", 0)
    hist = ind.get("macd_hist", 0)
    hist_prev = ind.get("macd_hist_prev", 0)

    cross_score = 0.5 if macd > sig else -0.5
    hist_score = 0.5 if hist > hist_prev else -0.5   # accelerating/decelerating
    zero_cross = 0.0
    if macd > 0 and sig > 0:
        zero_cross = 0.2
    elif macd < 0 and sig < 0:
        zero_cross = -0.2

    return _clamp(cross_score * 0.5 + hist_score * 0.3 + zero_cross * 0.2)


def signal_bollinger(ind: Dict[str, Any]) -> float:
    """
    Price position inside Bollinger Bands.
    Touch of lower band → buy; upper band → sell.
    Squeeze (narrow bands) dampens signal.
    """
    price = ind.get("price", 0)
    upper = ind.get("bb_upper", price)
    lower = ind.get("bb_lower", price)
    mid = ind.get("bb_mid", price)
    bb_width = ind.get("bb_width", 1.0)

    band_range = upper - lower
    if band_range == 0:
        return 0.0

    pos = (price - lower) / band_range  # 0=at lower, 1=at upper
    raw = -2 * pos + 1  # +1 at lower, -1 at upper, 0 at mid

    # Squeeze dampener
    squeeze = min(bb_width / 1.0, 1.0)
    return _clamp(raw * squeeze)


def signal_stochastic(ind: Dict[str, Any]) -> float:
    """Stochastic K/D cross in extreme zones."""
    k = ind.get("stoch_k", 50)
    d = ind.get("stoch_d", 50)

    if k < 20 and k > d:
        return 0.7   # oversold bullish cross
    if k > 80 and k < d:
        return -0.7  # overbought bearish cross
    if k < 20:
        return 0.4
    if k > 80:
        return -0.4
    return _clamp((50 - k) / 50)


def signal_sr(ind: Dict[str, Any]) -> float:
    """
    Support/Resistance proximity.
    Near support → buy; near resistance → sell.
    """
    price = ind.get("price", 0)
    support = ind.get("support", price * 0.999)
    resistance = ind.get("resistance", price * 1.001)

    if price == 0:
        return 0.0

    dist_sup = abs(price - support) / price
    dist_res = abs(price - resistance) / price

    if dist_sup < 0.001:      # within 0.1% of support
        return 0.6
    if dist_res < 0.001:      # within 0.1% of resistance
        return -0.6
    if dist_sup < 0.003:
        return 0.3
    if dist_res < 0.003:
        return -0.3
    return 0.0


# ─── Composite scoring ─────────────────────────────────────────────────────────

WEIGHTS = {
    "trend": 0.30,
    "rsi": 0.20,
    "macd": 0.20,
    "bollinger": 0.10,
    "stochastic": 0.10,
    "sr": 0.10,
}


def composite_score(ind: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    """
    Returns (composite_score, sub_scores_dict).
    composite_score ∈ [-1, +1]
    """
    sub = {
        "trend": signal_trend(ind),
        "rsi": signal_rsi(ind),
        "macd": signal_macd(ind),
        "bollinger": signal_bollinger(ind),
        "stochastic": signal_stochastic(ind),
        "sr": signal_sr(ind),
    }
    total = sum(sub[k] * WEIGHTS[k] for k in sub)
    return _clamp(total), sub


def get_direction(score: float, threshold: float = None) -> str:
    threshold = threshold or settings.ai_confidence_threshold
    abs_score = abs(score)
    if abs_score < threshold * 0.5:
        return "hold"
    if abs_score < threshold:
        return "watch"
    return "buy" if score > 0 else "sell"


# ─── Risk management ───────────────────────────────────────────────────────────

def calculate_position_size(balance: float, risk_pct: float,
                             sl_pips: float, pip_value: float = 10.0) -> float:
    """
    Returns lot size based on fixed fractional risk.
    pip_value: USD per pip per lot (default 10 for majors)
    """
    risk_amount = balance * (risk_pct / 100)
    if sl_pips <= 0:
        return 0.01
    lots = risk_amount / (sl_pips * pip_value)
    # Round to 2dp, clamp between 0.01 and 10
    lots = round(max(0.01, min(10.0, lots)), 2)
    return lots


def calculate_sl_tp(price: float, direction: str, atr: float,
                    atr_sl_multiplier: float = 1.5,
                    rr_ratio: float = 2.0,
                    digits: int = 5) -> Tuple[float, float]:
    """ATR-based SL/TP calculation."""
    sl_distance = atr * atr_sl_multiplier
    tp_distance = sl_distance * rr_ratio

    if direction == "buy":
        sl = round(price - sl_distance, digits)
        tp = round(price + tp_distance, digits)
    else:
        sl = round(price + sl_distance, digits)
        tp = round(price - tp_distance, digits)
    return sl, tp


# ─── Growth forecasting ────────────────────────────────────────────────────────

def forecast_growth(equity_history: list, days_ahead: int = 30) -> Dict[str, Any]:
    """
    Simple linear regression on equity curve to forecast growth.
    Returns projected balance, win probability, and confidence.
    """
    if len(equity_history) < 5:
        return {"error": "insufficient data", "forecast": [], "projected_return_pct": 0}

    y = np.array(equity_history, dtype=float)
    x = np.arange(len(y))

    # Linear regression
    coeffs = np.polyfit(x, y, 1)
    slope = coeffs[0]
    poly = np.poly1d(coeffs)

    # Residuals for volatility estimate
    y_pred = poly(x)
    residuals = y - y_pred
    vol = float(np.std(residuals))

    # Forecast points
    future_x = np.arange(len(y), len(y) + days_ahead)
    forecast_vals = poly(future_x)

    # Projected return
    current = float(y[-1])
    projected = float(forecast_vals[-1])
    proj_return = (projected - current) / current * 100 if current else 0

    # Confidence: inverse of coefficient of variation
    mean_val = float(np.mean(y))
    cv = vol / mean_val if mean_val else 1
    confidence = max(0.0, min(1.0, 1 - cv))

    return {
        "projected_balance": round(projected, 2),
        "projected_return_pct": round(proj_return, 2),
        "daily_drift": round(float(slope), 2),
        "volatility": round(vol, 2),
        "confidence": round(confidence, 3),
        "forecast": [
            {"day": i + 1, "balance": round(float(v), 2)}
            for i, v in enumerate(forecast_vals)
        ],
    }
