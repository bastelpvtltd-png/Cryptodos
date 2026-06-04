# ══════════════════════════════════════════════════════════════════
# src/scoring.py
# Signal scoring engine v5.
# Hard gates: HTF alignment, ADX >= 18, Supertrend direction.
# Each passing gate adds points; soft conditions add more.
# Returns (score, reasons_list).
# ══════════════════════════════════════════════════════════════════

import pandas as pd
from src.config   import SKIP_UTC_START, SKIP_UTC_END, MIN_SCORE
from src.patterns import detect_patterns, find_key_levels, get_market_structure


def score_signal(
    df: pd.DataFrame,
    i: int,
    direction: str,
    htf_trend: str,
    htf_strength: int,
    key_levels: list[float],
) -> tuple[int, list[str]]:
    """
    Score a potential signal at bar index i.

    Args:
        df          : DataFrame with all indicators computed
        i           : bar index to evaluate
        direction   : "LONG" or "SHORT"
        htf_trend   : "BULL", "BEAR", or "NEUTRAL"
        htf_strength: 0-3 from get_htf_trend()
        key_levels  : output of find_key_levels()

    Returns:
        (score, reasons) — score=0 means signal rejected
    """
    c    = df.iloc[i]
    prev = df.iloc[i - 1] if i > 0 else df.iloc[i]
    score   = 0
    reasons = []

    # ── Dead session filter (00-06 UTC) ───────────────────────────
    utc_h = (int(df.iloc[i]["Open_time"]) // 1000 // 3600) % 24
    if SKIP_UTC_START <= utc_h < SKIP_UTC_END:
        return 0, ["Dead session (00-06 UTC)"]

    # ═══════════════════════════════════
    # HARD GATE 1: HTF Trend Alignment
    # ═══════════════════════════════════
    if direction == "LONG" and htf_trend == "BULL":
        score += htf_strength; reasons.append(f"HTF BULL +{htf_strength}")
    elif direction == "SHORT" and htf_trend == "BEAR":
        score += htf_strength; reasons.append(f"HTF BEAR +{htf_strength}")
    else:
        return 0, ["HTF counter-trend — skip"]

    # ═══════════════════════════════════
    # HARD GATE 2: ADX >= 18
    # ═══════════════════════════════════
    adx = float(c.get("ADX", 0) or 0)
    if adx < 18:
        return 0, [f"ADX {adx:.1f} — flat market"]
    if   adx >= 30: score += 3; reasons.append(f"ADX {adx:.1f} very strong")
    elif adx >= 25: score += 2; reasons.append(f"ADX {adx:.1f} strong")
    else:           score += 1; reasons.append(f"ADX {adx:.1f} trending")

    # ═══════════════════════════════════
    # HARD GATE 3: Supertrend aligned
    # ═══════════════════════════════════
    st = int(c.get("ST_DIR", 0) or 0)
    if direction == "LONG"  and st != 1:  return 0, ["Supertrend bearish"]
    if direction == "SHORT" and st != -1: return 0, ["Supertrend bullish"]
    score += 1; reasons.append("Supertrend ✓")

    cl      = float(c["close"])
    prev_cl = float(prev["close"])
    e8      = float(c["EMA8"]);  e21 = float(c["EMA21"])
    e55     = float(c["EMA55"]); e200= float(c["EMA200"])

    # ── EMA Stack ────────────────────────────────────────────────
    if direction == "LONG":
        if   cl > e8 > e21 > e55 > e200: score += 4; reasons.append("EMA perfect bull stack")
        elif cl > e21 > e55 > e200:       score += 3; reasons.append("EMA full bull 21>55>200")
        elif cl > e21 > e55:              score += 2; reasons.append("EMA 21>55 bull")
        elif cl > e21:                    score += 1; reasons.append("Above EMA21")
        elif cl < e55:                    score -= 1
        if prev_cl < e8 and cl > e8:      score += 1; reasons.append("EMA8 reclaim ↑")
    else:
        if   cl < e8 < e21 < e55 < e200: score += 4; reasons.append("EMA perfect bear stack")
        elif cl < e21 < e55 < e200:       score += 3; reasons.append("EMA full bear 21<55<200")
        elif cl < e21 < e55:              score += 2; reasons.append("EMA 21<55 bear")
        elif cl < e21:                    score += 1; reasons.append("Below EMA21")
        elif cl > e55:                    score -= 1
        if prev_cl > e8 and cl < e8:      score += 1; reasons.append("EMA8 reclaim ↓")

    # ── Ichimoku Tenkan/Kijun ─────────────────────────────────────
    tenkan   = float(c.get("TENKAN", 0) or 0)
    kijun    = float(c.get("KIJUN",  0) or 0)
    p_tenkan = float(prev.get("TENKAN", 0) or 0)
    p_kijun  = float(prev.get("KIJUN",  0) or 0)
    if tenkan > 0 and kijun > 0:
        if direction == "LONG" and tenkan > kijun and cl > kijun:
            if p_tenkan <= p_kijun: score += 2; reasons.append("Ichimoku TK cross ↑")
            else:                   score += 1; reasons.append("Ichimoku bull TK")
        elif direction == "SHORT" and tenkan < kijun and cl < kijun:
            if p_tenkan >= p_kijun: score += 2; reasons.append("Ichimoku TK cross ↓")
            else:                   score += 1; reasons.append("Ichimoku bear TK")

    # ── DI direction ──────────────────────────────────────────────
    pdi = float(c.get("PLUS_DI",  0) or 0)
    mdi = float(c.get("MINUS_DI", 0) or 0)
    if direction == "LONG"  and pdi > mdi: score += 1; reasons.append(f"+DI{pdi:.0f}>{mdi:.0f}")
    elif direction == "SHORT" and mdi > pdi: score += 1; reasons.append(f"-DI{mdi:.0f}>{pdi:.0f}")

    # ── Market Structure ──────────────────────────────────────────
    ms = get_market_structure(df.iloc[:i+1], lookback=25)
    if direction == "LONG"  and ms == "BULL": score += 1; reasons.append("Structure HH+HL")
    elif direction == "SHORT" and ms == "BEAR": score += 1; reasons.append("Structure LH+LL")

    # ── VWAP ──────────────────────────────────────────────────────
    vwap = float(c.get("VWAP", 0) or 0)
    if vwap > 0:
        if direction == "LONG"  and cl > vwap: score += 1; reasons.append("Above VWAP")
        elif direction == "SHORT" and cl < vwap: score += 1; reasons.append("Below VWAP")
        vg = abs(cl - vwap) / vwap
        if vg > 0.005 and (
            (direction == "LONG" and cl > vwap)
            or (direction == "SHORT" and cl < vwap)
        ):
            score += 1; reasons.append(f"VWAP gap {vg*100:.1f}%")

    # ── RSI + Divergence ──────────────────────────────────────────
    rsi = float(c["RSI"])
    if direction == "LONG":
        if rsi > 80: return 0, [f"RSI {rsi:.0f} extreme OB"]
        if rsi > 72: score -= 1
        if   40 <= rsi <= 65: score += 2; reasons.append(f"RSI {rsi:.0f} ideal")
        elif 30 <= rsi < 40:  score += 2; reasons.append(f"RSI {rsi:.0f} OS bounce")
        elif rsi < 30:        score += 1; reasons.append(f"RSI {rsi:.0f} deep OS")
        if bool(c.get("RSI_DIV_BULL", False)): score += 2; reasons.append("RSI bull div ⚡")
    else:
        if rsi < 20: return 0, [f"RSI {rsi:.0f} extreme OS"]
        if rsi < 28: score -= 1
        if   35 <= rsi <= 60: score += 2; reasons.append(f"RSI {rsi:.0f} ideal")
        elif 60 < rsi <= 70:  score += 2; reasons.append(f"RSI {rsi:.0f} OB reject")
        elif rsi > 70:        score += 1; reasons.append(f"RSI {rsi:.0f} deep OB")
        if bool(c.get("RSI_DIV_BEAR", False)): score += 2; reasons.append("RSI bear div ⚡")

    # ── MACD ──────────────────────────────────────────────────────
    macd   = float(c.get("MACD", 0) or 0)
    macds  = float(c.get("MACDS", 0) or 0)
    hist   = float(c.get("MACD_HIST", 0) or 0)
    p_hist = float(prev.get("MACD_HIST", 0) or 0)
    pmacd  = float(prev.get("MACD",  0) or 0)
    pmacds = float(prev.get("MACDS", 0) or 0)
    if direction == "LONG":
        if macd > macds and pmacd <= pmacds: score += 2; reasons.append("MACD cross ↑")
        elif macd > macds:                   score += 1; reasons.append("MACD bull")
        if hist > 0 and hist > p_hist:       score += 1; reasons.append("MACD hist ↑")
    else:
        if macd < macds and pmacd >= pmacds: score += 2; reasons.append("MACD cross ↓")
        elif macd < macds:                   score += 1; reasons.append("MACD bear")
        if hist < 0 and hist < p_hist:       score += 1; reasons.append("MACD hist ↓")

    # ── Bollinger Bands ───────────────────────────────────────────
    bbma  = float(c.get("BB_MA",    cl)  or cl)
    bbup  = float(c.get("BB_UP",    cl)  or cl)
    bblo  = float(c.get("BB_LO",    cl)  or cl)
    bbpct = float(c.get("BB_PCT",  0.5) or 0.5)
    bbw   = float(c.get("BB_WIDTH", 0)  or 0)
    if bbma > 0 and bbw < 0.012:
        return 0, ["BB squeeze — low volatility"]
    prev_bbw = float(prev.get("BB_WIDTH", bbw) or bbw)
    if direction == "LONG":
        if   cl <= bblo * 1.005: score += 2; reasons.append("BB lower bounce")
        elif bbpct < 0.3:        score += 1; reasons.append("BB lower half")
        if bbw > prev_bbw * 1.1: score += 1; reasons.append("BB expanding")
    else:
        if   cl >= bbup * 0.995: score += 2; reasons.append("BB upper reject")
        elif bbpct > 0.7:        score += 1; reasons.append("BB upper half")
        if bbw > prev_bbw * 1.1: score += 1; reasons.append("BB expanding")

    # ── OBV trend ─────────────────────────────────────────────────
    if i >= 5:
        obv_now  = float(c.get("OBV", 0) or 0)
        obv_prev = float(df.iloc[i-5].get("OBV", obv_now) or obv_now)
        if direction == "LONG"  and obv_now > obv_prev: score += 1; reasons.append("OBV rising")
        elif direction == "SHORT" and obv_now < obv_prev: score += 1; reasons.append("OBV falling")

    # ── Volume spike ──────────────────────────────────────────────
    vm = float(c.get("VOL_MA20", 0) or 0)
    vr = c["volume"] / vm if vm > 0 else 1.0
    if   vr > 2.0: score += 3; reasons.append(f"Vol {vr:.1f}x HUGE spike")
    elif vr > 1.5: score += 2; reasons.append(f"Vol {vr:.1f}x spike")
    elif vr > 1.2: score += 1; reasons.append(f"Vol {vr:.1f}x above avg")

    # ── Key S/R levels ────────────────────────────────────────────
    for lvl in key_levels:
        dp = abs(cl - lvl) / (cl + 1e-9)
        if   dp < 0.006:  score += 3; reasons.append(f"At Key S/R ${lvl:.4f}"); break
        elif dp < 0.012:  score += 2; reasons.append(f"Near Key S/R ${lvl:.4f}"); break
        elif dp < 0.02:   score += 1; reasons.append(f"Close S/R ${lvl:.4f}"); break

    # ── Candlestick patterns ──────────────────────────────────────
    pats = detect_patterns(df, i)
    if direction == "LONG":
        if   "BULL_ENGULF"    in pats: score += 3; reasons.append("Bullish Engulfing 🕯")
        elif "MORNING_STAR"   in pats: score += 3; reasons.append("Morning Star 🌟")
        elif "THREE_SOLDIERS" in pats: score += 2; reasons.append("Three White Soldiers")
        elif "BULL_PIN"       in pats: score += 2; reasons.append("Bullish Pin Bar")
        if "INSIDE_BAR" in pats and cl > float(prev["high"]):
            score += 1; reasons.append("Inside Bar breakout ↑")
    else:
        if   "BEAR_ENGULF"  in pats: score += 3; reasons.append("Bearish Engulfing 🕯")
        elif "EVENING_STAR" in pats: score += 3; reasons.append("Evening Star 🌟")
        elif "THREE_CROWS"  in pats: score += 2; reasons.append("Three Black Crows")
        elif "BEAR_PIN"     in pats: score += 2; reasons.append("Bearish Pin Bar")
        if "INSIDE_BAR" in pats and cl < float(prev["low"]):
            score += 1; reasons.append("Inside Bar breakout ↓")

    # ── ROC momentum ─────────────────────────────────────────────
    roc5 = float(c.get("ROC5", 0) or 0)
    if direction == "LONG"  and roc5 > 1.5: score += 1; reasons.append(f"ROC5 {roc5:.1f}% bull")
    elif direction == "SHORT" and roc5 < -1.5: score += 1; reasons.append(f"ROC5 {roc5:.1f}% bear")

    # ── StochRSI extreme disqualifiers ────────────────────────────
    stoch = float(c.get("STOCHRSI", 0.5) or 0.5)
    if direction == "LONG"  and stoch > 0.92: return 0, ["StochRSI extreme OB"]
    if direction == "SHORT" and stoch < 0.08: return 0, ["StochRSI extreme OS"]

    return max(score, 0), reasons


# ── SL / TP calculation ───────────────────────────────────────────
def calculate_levels(
    df: pd.DataFrame, i: int, direction: str, entry: float
) -> tuple[float, float, float, float, float, float]:
    """
    Calculate SL, TP1, TP2 from ATR and recent swing.

    Returns: (sl, tp1, tp2, sl_pct, tp1_pct, rr)
    """
    c   = df.iloc[i]
    atr = float(c["ATR"]) if not pd.isna(c["ATR"]) else entry * 0.015
    lb  = max(0, i - 20)
    rl  = df["low"].iloc[lb:i]
    rh  = df["high"].iloc[lb:i]

    if direction == "LONG":
        atr_sl = entry - atr * 1.8
        sw_sl  = float(rl.min()) * 0.998 if len(rl) > 0 else atr_sl
        sl     = min(atr_sl, sw_sl)
        sl     = min(sl, entry * 0.985)
        sl     = max(sl, entry * 0.970)
        risk   = entry - sl
        tp1    = entry + risk * 2.0
        tp2    = entry + risk * 3.5
    else:
        atr_sl = entry + atr * 1.8
        sw_sl  = float(rh.max()) * 1.002 if len(rh) > 0 else atr_sl
        sl     = max(atr_sl, sw_sl)
        sl     = max(sl, entry * 1.015)
        sl     = min(sl, entry * 1.030)
        risk   = sl - entry
        tp1    = entry - risk * 2.0
        tp2    = entry - risk * 3.5

    sl_pct  = abs(entry - sl)  / entry * 100
    tp1_pct = abs(tp1 - entry) / entry * 100
    rr      = tp1_pct / sl_pct if sl_pct > 0 else 0

    return sl, tp1, tp2, sl_pct, tp1_pct, rr


# ── Outcome checker ───────────────────────────────────────────────
def check_outcome(
    df_full: pd.DataFrame,
    signal_idx: int,
    direction: str,
    entry: float,
    tp1: float,
    tp2: float,
    sl: float,
) -> tuple[str, float, int, int | None]:
    """
    Simulate trade outcome looking at next 72 bars.

    Returns: (outcome, result_pct, bars_held, close_time_ms)
    outcome: "TP2_HIT" | "SL_HIT" | "BREAKEVEN" | "STILL_OPEN" | "NO_DATA"
    """
    future   = df_full.iloc[signal_idx + 1 : signal_idx + 73]
    tp1_hit  = False

    for i, (_, row) in enumerate(future.iterrows()):
        h  = float(row["high"]); l = float(row["low"])
        ms = int(row["Open_time"])

        if direction == "LONG":
            if l <= sl:
                if tp1_hit:
                    return "BREAKEVEN", (tp1-entry)/entry*100*0.5 + (sl-entry)/entry*100*0.5, i+1, ms
                return "SL_HIT", (sl-entry)/entry*100, i+1, ms
            if not tp1_hit and h >= tp1:
                tp1_hit = True
            if tp1_hit and h >= tp2:
                return "TP2_HIT", ((tp1-entry)/entry*100)*0.5 + ((tp2-entry)/entry*100)*0.5, i+1, ms
        else:
            if h >= sl:
                if tp1_hit:
                    return "BREAKEVEN", (entry-tp1)/entry*100*0.5 + (entry-sl)/entry*100*0.5, i+1, ms
                return "SL_HIT", (entry-sl)/entry*100, i+1, ms
            if not tp1_hit and l <= tp1:
                tp1_hit = True
            if tp1_hit and l <= tp2:
                return "TP2_HIT", ((entry-tp1)/entry*100)*0.5 + ((entry-tp2)/entry*100)*0.5, i+1, ms

    if len(future) == 0:
        return "NO_DATA", 0.0, 0, None

    last = float(future.iloc[-1]["close"])
    lms  = int(future.iloc[-1]["Open_time"])
    pct  = (last-entry)/entry*100 if direction == "LONG" else (entry-last)/entry*100
    return "STILL_OPEN", pct, len(future), lms


# ── USD P&L from outcome ──────────────────────────────────────────
def calc_pnl_usd(
    outcome: str,
    result_pct: float,
    alloc_usd: float,
    entry: float,
    tp1: float,
    tp2: float,
    sl: float,
    direction: str,
) -> float:
    """Convert % outcome to actual USD P&L based on allocated amount."""
    if outcome == "TP2_HIT":
        tp1_pct = abs(tp1 - entry) / entry * 100
        tp2_pct = abs(tp2 - entry) / entry * 100
        return round(alloc_usd * ((tp1_pct / 100) * 0.5 + (tp2_pct / 100) * 0.5), 4)
    elif outcome == "SL_HIT":
        sl_pct = abs(sl - entry) / entry * 100
        return round(-alloc_usd * (sl_pct / 100), 4)
    elif outcome == "BREAKEVEN":
        tp1_pct = abs(tp1 - entry) / entry * 100
        return round(alloc_usd * (tp1_pct / 100) * 0.5, 4)
    else:   # STILL_OPEN / NO_DATA
        return round(alloc_usd * (result_pct / 100), 4)
