# ══════════════════════════════════════════════════════════════════
# src/indicators.py
# Technical indicator calculations.
# All indicators computed on a DataFrame and returned as new columns.
# ══════════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators and append as columns.

    Added columns:
        EMA8, EMA21, EMA55, EMA200
        RSI, RSI_DIV_BULL, RSI_DIV_BEAR
        MACD, MACDS, MACD_HIST
        BB_MA, BB_STD, BB_UP, BB_LO, BB_PCT, BB_WIDTH
        VOL_MA20, OBV
        ATR
        STOCHRSI
        PLUS_DI, MINUS_DI, ADX
        ST_DIR, ST_VAL  (Supertrend)
        VWAP
        ROC5
        TENKAN, KIJUN  (Ichimoku simplified)
    """
    d = df.copy()

    # ── EMAs ──────────────────────────────────────────────────────
    d["EMA8"]   = d["close"].ewm(span=8,   adjust=False).mean()
    d["EMA21"]  = d["close"].ewm(span=21,  adjust=False).mean()
    d["EMA55"]  = d["close"].ewm(span=55,  adjust=False).mean()
    d["EMA200"] = d["close"].ewm(span=200, adjust=False).mean()

    # ── RSI ───────────────────────────────────────────────────────
    delta = d["close"].diff()
    gain  = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    d["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # ── RSI Divergence ────────────────────────────────────────────
    d["RSI_DIV_BULL"] = False
    d["RSI_DIV_BEAR"] = False
    for i in range(5, len(d)):
        p_lows  = d["low"].iloc[i-5:i+1];  r_lows  = d["RSI"].iloc[i-5:i+1]
        p_highs = d["high"].iloc[i-5:i+1]; r_highs = d["RSI"].iloc[i-5:i+1]
        if (p_lows.iloc[-1] < p_lows.min() * 1.001
                and r_lows.iloc[-1] > r_lows.iloc[:-1].min() * 1.01):
            d.at[d.index[i], "RSI_DIV_BULL"] = True
        if (p_highs.iloc[-1] > p_highs.max() * 0.999
                and r_highs.iloc[-1] < r_highs.iloc[:-1].max() * 0.99):
            d.at[d.index[i], "RSI_DIV_BEAR"] = True

    # ── MACD ──────────────────────────────────────────────────────
    e12 = d["close"].ewm(span=12, adjust=False).mean()
    e26 = d["close"].ewm(span=26, adjust=False).mean()
    d["MACD"]      = e12 - e26
    d["MACDS"]     = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD_HIST"] = d["MACD"] - d["MACDS"]

    # ── Bollinger Bands ───────────────────────────────────────────
    d["BB_MA"]    = d["close"].rolling(20).mean()
    d["BB_STD"]   = d["close"].rolling(20).std()
    d["BB_UP"]    = d["BB_MA"] + 2 * d["BB_STD"]
    d["BB_LO"]    = d["BB_MA"] - 2 * d["BB_STD"]
    d["BB_PCT"]   = (d["close"] - d["BB_LO"]) / (d["BB_UP"] - d["BB_LO"] + 1e-9)
    d["BB_WIDTH"] = (d["BB_UP"] - d["BB_LO"]) / (d["BB_MA"] + 1e-9)

    # ── Volume ────────────────────────────────────────────────────
    d["VOL_MA20"] = d["volume"].rolling(20).mean()
    sign          = d["close"].diff().apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
    d["OBV"]      = (d["volume"] * sign).cumsum()

    # ── ATR ───────────────────────────────────────────────────────
    hl  = d["high"] - d["low"]
    hpc = (d["high"] - d["close"].shift(1)).abs()
    lpc = (d["low"]  - d["close"].shift(1)).abs()
    d["ATR"] = pd.concat([hl, hpc, lpc], axis=1).max(axis=1).rolling(14).mean()

    # ── StochRSI ──────────────────────────────────────────────────
    rsi_min   = d["RSI"].rolling(14).min()
    rsi_max   = d["RSI"].rolling(14).max()
    d["STOCHRSI"] = (d["RSI"] - rsi_min) / ((rsi_max - rsi_min) + 1e-9)

    # ── ADX + DI ──────────────────────────────────────────────────
    pdm = d["high"].diff().clip(lower=0)
    mdm = (-d["low"].diff()).clip(lower=0)
    pdm = pdm.where(pdm > mdm, 0)
    mdm = mdm.where(mdm > pdm, 0)
    d["PLUS_DI"]  = 100 * (pdm.rolling(14).mean() / (d["ATR"] + 1e-9))
    d["MINUS_DI"] = 100 * (mdm.rolling(14).mean() / (d["ATR"] + 1e-9))
    dx = (
        100
        * (d["PLUS_DI"] - d["MINUS_DI"]).abs()
        / (d["PLUS_DI"] + d["MINUS_DI"] + 1e-9)
    )
    d["ADX"] = dx.rolling(14).mean()

    # ── Supertrend (multiplier=3, period=14) ──────────────────────
    hl2 = (d["high"] + d["low"]) / 2
    ub  = hl2 + 3.0 * d["ATR"]
    lb  = hl2 - 3.0 * d["ATR"]
    st_dir = [1]   * len(d)
    st_val = [0.0] * len(d)
    for i in range(1, len(d)):
        fub = (ub.iloc[i] if ub.iloc[i] < ub.iloc[i-1]
               or d["close"].iloc[i-1] > ub.iloc[i-1] else ub.iloc[i-1])
        flb = (lb.iloc[i] if lb.iloc[i] > lb.iloc[i-1]
               or d["close"].iloc[i-1] < lb.iloc[i-1] else lb.iloc[i-1])
        if st_val[i-1] == ub.iloc[i-1]:
            st_dir[i] = -1 if d["close"].iloc[i] <= fub else 1
            st_val[i] = fub if d["close"].iloc[i] <= fub else flb
        else:
            st_dir[i] = 1 if d["close"].iloc[i] >= flb else -1
            st_val[i] = flb if d["close"].iloc[i] >= flb else fub
    d["ST_DIR"] = st_dir
    d["ST_VAL"] = st_val

    # ── VWAP (rolling 24-bar) ─────────────────────────────────────
    typ   = (d["high"] + d["low"] + d["close"]) / 3
    d["VWAP"] = (
        (typ * d["volume"]).rolling(24).sum()
        / d["volume"].rolling(24).sum()
    )

    # ── Momentum ──────────────────────────────────────────────────
    d["ROC5"] = d["close"].pct_change(5) * 100

    # ── Ichimoku (Tenkan + Kijun) ─────────────────────────────────
    d["TENKAN"] = (d["high"].rolling(9).max()  + d["low"].rolling(9).min())  / 2
    d["KIJUN"]  = (d["high"].rolling(26).max() + d["low"].rolling(26).min()) / 2

    return d
