# ══════════════════════════════════════════════════════════════════
# src/data.py
# Binance public klines API — no API key needed.
# Downloads OHLCV data for a given symbol + interval.
# ══════════════════════════════════════════════════════════════════

import time
import calendar
import requests
import pandas as pd
from datetime import datetime, timedelta


# ── Date helpers ───────────────────────────────────────────────────
def date_to_ms(date_str: str, end_of_day: bool = False, lk_offset_sec: int = 19800) -> int:
    """Convert 'YYYY-MM-DD' string to milliseconds (LK timezone aware)."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    if end_of_day:
        utc_sec = calendar.timegm((d.year, d.month, d.day, 23, 59, 59)) - lk_offset_sec
    else:
        utc_sec = calendar.timegm((d.year, d.month, d.day, 0, 0, 0)) - lk_offset_sec
    return utc_sec * 1000


def ms_to_lk(ms, lk_offset_sec: int = 19800) -> str:
    """Convert milliseconds timestamp to LK time string."""
    if ms is None:
        return "Still Open"
    return datetime.utcfromtimestamp(ms / 1000 + lk_offset_sec).strftime("%d %b %Y %I:%M %p")


def get_date_range(start_str: str, end_str: str) -> list[str]:
    """Generate list of 'YYYY-MM-DD' strings from start to end inclusive."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    dates, cur = [], start
    while cur <= end:
        dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return dates


# ── Binance data downloader ────────────────────────────────────────
def download_data(
    symbol: str,
    interval: str = "1h",
    limit: int = 700,
    end_ms: int = None,
) -> pd.DataFrame | None:
    """
    Download OHLCV klines from Binance public API.
    No API key required.

    Args:
        symbol   : e.g. "BTCUSDT"
        interval : "1h", "4h", "1d" etc.
        limit    : number of candles (max 1000)
        end_ms   : optional endTime in milliseconds

    Returns:
        DataFrame with columns: Open_time, open, high, low, close, volume, Close_time
        or None if download fails.
    """
    try:
        url = (
            f"https://api.binance.com/api/v3/klines"
            f"?symbol={symbol}&interval={interval}&limit={limit}"
        )
        if end_ms:
            url += f"&endTime={end_ms}"

        r = requests.get(url, timeout=8)
        r.raise_for_status()

        df = pd.DataFrame(
            r.json(),
            columns=[
                "Open_time", "open", "high", "low", "close", "volume",
                "Close_time", "qav", "num_trades", "taker_base", "taker_quote", "ignore",
            ],
        )
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["Open_time"]  = df["Open_time"].astype(int)
        df["Close_time"] = df["Close_time"].astype(int)
        return df.reset_index(drop=True)

    except Exception as e:
        print(f"  ⚠️  Data error [{symbol} {interval}]: {e}")
        return None


# ── Higher-timeframe trend ─────────────────────────────────────────
def get_htf_trend(symbol: str, end_ms: int = None) -> tuple[str, int]:
    """
    Check 4H and 1D trend using EMA20 / EMA50.

    Returns:
        ("BULL"|"BEAR"|"NEUTRAL", strength 0-3)
    """
    scores = {"BULL": 0, "BEAR": 0}

    for tf, lim, weight in [("4h", 100, 2), ("1d", 50, 1)]:
        df = download_data(symbol, interval=tf, limit=lim, end_ms=end_ms)
        if df is None or len(df) < 50:
            continue

        close = df["close"]
        e20   = close.ewm(span=20, adjust=False).mean()
        e50   = close.ewm(span=50, adjust=False).mean()
        lc    = close.iloc[-1]

        if lc > e20.iloc[-1] > e50.iloc[-1]:
            scores["BULL"] += weight
        elif lc < e20.iloc[-1] < e50.iloc[-1]:
            scores["BEAR"] += weight

        time.sleep(0.08)

    if scores["BULL"] >= 2:
        return "BULL", min(scores["BULL"], 3)
    if scores["BEAR"] >= 2:
        return "BEAR", min(scores["BEAR"], 3)
    return "NEUTRAL", 0
