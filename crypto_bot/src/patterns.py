# ══════════════════════════════════════════════════════════════════
# src/patterns.py
# Candlestick pattern detection + key S/R level finder.
# ══════════════════════════════════════════════════════════════════

import pandas as pd


def detect_patterns(df: pd.DataFrame, i: int) -> list[str]:
    """
    Detect candlestick patterns at bar index i.

    Detected patterns:
        BULL_ENGULF, BEAR_ENGULF
        BULL_PIN,    BEAR_PIN
        MORNING_STAR, EVENING_STAR
        THREE_SOLDIERS, THREE_CROWS
        INSIDE_BAR
        DOJI

    Returns list of pattern name strings (may be empty).
    """
    c   = df.iloc[i]
    p   = df.iloc[i - 1]
    p2  = df.iloc[i - 2] if i >= 2 else p
    pats = []

    tr   = c["high"] - c["low"]
    if tr < 1e-9:
        return pats

    body = abs(c["close"] - c["open"])
    uw   = c["high"] - max(c["open"], c["close"])
    lw   = min(c["open"], c["close"]) - c["low"]

    # ── Bullish Engulfing ──────────────────────────────────────────
    if (
        p["close"] < p["open"]
        and c["close"] > c["open"]
        and c["open"]  < min(p["open"], p["close"])
        and c["close"] > max(p["open"], p["close"])
    ):
        pats.append("BULL_ENGULF")

    # ── Bearish Engulfing ──────────────────────────────────────────
    if (
        p["close"] > p["open"]
        and c["close"] < c["open"]
        and c["open"]  > max(p["open"], p["close"])
        and c["close"] < min(p["open"], p["close"])
    ):
        pats.append("BEAR_ENGULF")

    # ── Pin Bars ───────────────────────────────────────────────────
    if lw > tr * 0.55 and body < tr * 0.35 and uw < tr * 0.2:
        pats.append("BULL_PIN")
    if uw > tr * 0.55 and body < tr * 0.35 and lw < tr * 0.2:
        pats.append("BEAR_PIN")

    # ── Morning Star ───────────────────────────────────────────────
    if (
        p2["close"] < p2["open"]
        and abs(p["close"] - p["open"]) < (p["high"] - p["low"]) * 0.3
        and c["close"] > c["open"]
        and c["close"] > (p2["open"] + p2["close"]) / 2
    ):
        pats.append("MORNING_STAR")

    # ── Evening Star ───────────────────────────────────────────────
    if (
        p2["close"] > p2["open"]
        and abs(p["close"] - p["open"]) < (p["high"] - p["low"]) * 0.3
        and c["close"] < c["open"]
        and c["close"] < (p2["open"] + p2["close"]) / 2
    ):
        pats.append("EVENING_STAR")

    # ── Three White Soldiers / Three Black Crows ───────────────────
    if i >= 3:
        if (
            all(df.iloc[k]["close"] > df.iloc[k]["open"] for k in range(i - 2, i + 1))
            and df.iloc[i - 1]["open"] > df.iloc[i - 2]["close"] * 0.995
        ):
            pats.append("THREE_SOLDIERS")
        if (
            all(df.iloc[k]["close"] < df.iloc[k]["open"] for k in range(i - 2, i + 1))
            and df.iloc[i - 1]["open"] < df.iloc[i - 2]["close"] * 1.005
        ):
            pats.append("THREE_CROWS")

    # ── Inside Bar ────────────────────────────────────────────────
    if c["high"] <= p["high"] and c["low"] >= p["low"]:
        pats.append("INSIDE_BAR")

    # ── Doji ──────────────────────────────────────────────────────
    if body < tr * 0.1:
        pats.append("DOJI")

    return pats


def find_key_levels(df: pd.DataFrame, lookback: int = 100) -> list[float]:
    """
    Find key support/resistance levels from recent price action.
    Clusters nearby levels within 0.5% of each other.

    Returns list of price levels (floats).
    """
    levels = []
    src = df.tail(lookback).reset_index(drop=True)

    for i in range(2, len(src) - 2):
        h = src["high"].iloc[i]
        l = src["low"].iloc[i]
        if h == src["high"].iloc[i-2:i+3].max():
            levels.append(h)
        if l == src["low"].iloc[i-2:i+3].min():
            levels.append(l)

    levels.sort()
    zones = []
    i = 0
    while i < len(levels):
        cluster = [levels[i]]
        j = i + 1
        while j < len(levels) and (levels[j] - levels[i]) / (levels[i] + 1e-9) < 0.005:
            cluster.append(levels[j])
            j += 1
        if len(cluster) >= 2:
            zones.append(sum(cluster) / len(cluster))
        i = j if j > i else i + 1

    return zones


def get_market_structure(df: pd.DataFrame, lookback: int = 30) -> str:
    """
    Determine local market structure from swing highs/lows.

    Returns: "BULL" | "BEAR" | "NEUTRAL"
    """
    highs = df["high"].iloc[-lookback:].values
    lows  = df["low"].iloc[-lookback:].values
    sh, sl = [], []

    for i in range(2, len(highs) - 2):
        if highs[i] == max(highs[i-2], highs[i-1], highs[i], highs[i+1], highs[i+2]):
            sh.append(highs[i])
        if lows[i] == min(lows[i-2], lows[i-1], lows[i], lows[i+1], lows[i+2]):
            sl.append(lows[i])

    if len(sh) < 2 or len(sl) < 2:
        return "NEUTRAL"
    if sh[-1] > sh[-2] and sl[-1] > sl[-2]:
        return "BULL"
    if sh[-1] < sh[-2] and sl[-1] < sl[-2]:
        return "BEAR"
    return "NEUTRAL"
