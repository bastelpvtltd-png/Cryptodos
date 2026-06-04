# ══════════════════════════════════════════════════════════════════
# src/config.py — ALL SETTINGS HERE. MEKA VITHARAI WENAS KARANNA.
# ══════════════════════════════════════════════════════════════════

# ── TELEGRAM ──────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8905811864:AAEaEzjyirk1dJivfvtQWtumL3mXXCh5-SQ"
TELEGRAM_CHAT_ID   = "1450144996"

# ── DATE RANGE ── (YYYY-MM-DD format) ─────────────────────────────
START_DATE = "2026-05-15"   # <- WENAS KARANNA (start date)
END_DATE   = "2026-05-20"   # <- WENAS KARANNA (end date, inclusive)

# ── ACCOUNT ───────────────────────────────────────────────────────
STARTING_BALANCE = 100.0    # Simulated starting USD (Binance API NAHA)

# ── SCORE → ALLOCATION % of AVAILABLE BALANCE ─────────────────────
# Score 6 = 5%, Score 7 = 8%, Score 8 = 12%, Score 9 = 18%, Score 10 = 22%
SCORE_ALLOC_PCT = {6: 5.0, 7: 8.0, 8: 12.0, 9: 18.0, 10: 22.0}
MAX_ALLOC_PCT   = 0.25      # Never more than 25% of total balance per trade
MIN_TRADE_USD   = 2.0       # Minimum trade size USD

# ── COIN LIST ─────────────────────────────────────────────────────
BLOCKED_COINS = ["TRXUSDT", "DOGEUSDT"]
WATCH_LIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",  "XRPUSDT",
    "ADAUSDT", "LINKUSDT","AVAXUSDT","DOTUSDT",   "MATICUSDT",
    "LTCUSDT", "UNIUSDT", "NEARUSDT","APTUSDT",   "INJUSDT",
    "OPUSDT",  "ARBUSDT", "SUIUSDT", "TIAUSDT",   "FETUSDT",
]

# ── SIGNAL FILTERS ────────────────────────────────────────────────
DATA_LIMIT           = 700
MIN_SCORE            = 6
MAX_SIGNALS_PER_COIN = 3
COOLDOWN_BARS        = 4
MIN_RR               = 1.8
MAX_OPEN_TRADES      = 5    # Max concurrent simulated open trades

# ── TIME SETTINGS ─────────────────────────────────────────────────
LK_OFFSET_SEC  = 5 * 3600 + 30 * 60   # UTC+5:30
SKIP_UTC_START = 0                      # Skip signals between 00:00-06:00 UTC
SKIP_UTC_END   = 6                      # (low volume Asian session)

# ── PATHS ─────────────────────────────────────────────────────────
CHARTS_DIR = "charts"
LOGS_DIR   = "logs"
DATA_DIR   = "data"
