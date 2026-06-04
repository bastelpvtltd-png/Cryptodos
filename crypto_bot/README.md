# 🤖 Crypto Backtest Bot v5

Historical crypto signal backtest bot with **dynamic balance management**.
No Binance API needed — uses public klines data only.
Results sent to **Telegram** with charts.

---

## 📁 Project Structure

```
crypto_bot/
│
├── main.py               ← Run this to start
├── requirements.txt      ← Python dependencies
├── .gitignore
│
├── src/
│   ├── config.py         ← ⭐ ALL SETTINGS HERE (date range, balance, etc.)
│   ├── balance.py        ← Simulated balance manager
│   ├── data.py           ← Binance data downloader + HTF trend
│   ├── indicators.py     ← EMA, RSI, MACD, BB, ATR, ADX, Supertrend...
│   ├── patterns.py       ← Candlestick patterns + S/R key levels
│   ├── scoring.py        ← Signal scoring engine (hard gates + soft score)
│   ├── chart.py          ← Dark-mode candlestick chart builder
│   ├── telegram.py       ← Telegram alert + chart sender
│   ├── reports.py        ← Daily + final summary report
│   └── backtest.py       ← Main orchestrator
│
├── charts/               ← Auto-created, chart PNGs saved here
├── logs/                 ← Auto-created, for future log files
└── data/                 ← Auto-created, for future data cache
```

---

## ⚙️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `src/config.py`

Only edit this file:

```python
# Telegram
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID   = "your_chat_id"

# Date range
START_DATE = "2026-05-15"
END_DATE   = "2026-05-20"

# Starting balance
STARTING_BALANCE = 100.0
```

### 3. Run

```bash
python main.py
```

---

## 💰 How Balance Works

Each signal gets allocated a % of your **available balance** based on its score:

| Score | Allocation (of available) |
|-------|--------------------------|
| 6     | 5%                       |
| 7     | 8%                       |
| 8     | 12%                      |
| 9     | 18%                      |
| 10    | 22%                      |

- **Max per trade**: 25% of total balance
- **Min trade size**: $2
- **Max concurrent**: 5 open trades
- Balance updates after **every trade close** → next trade uses updated balance

---

## 📊 What You Get on Telegram

**Per signal:**
- Direction, coin, score, R:R
- Entry / TP1 / TP2 / SL prices
- Amount allocated (USD + % of balance)
- Outcome (WIN / LOSS / BE / OPEN)
- Balance before → after update
- Candlestick chart with levels

**Per day:**
- All trades with allocation + P&L
- Day start / end balance

**Final report:**
- Daily breakdown table (Date | Sig | W | L | P/L | Balance)
- Total P&L, ROI %, Win Rate
- Avg allocation, Avg R:R, Expectancy
- Best / Worst trade

---

## 🔍 Signal Filters (Hard Gates)

1. **HTF Trend** — 4H + 1D EMA20/50 must align (BULL for LONG, BEAR for SHORT)
2. **ADX ≥ 18** — Market must be trending, not ranging
3. **Supertrend** — Must point in trade direction
4. **Score ≥ 6** — Total score from all soft conditions
5. **R:R ≥ 1.8** — Minimum risk-reward ratio
6. **Skip 00:00–06:00 UTC** — Low volume Asian dead session

---

## 🚀 Deploy Online (GitHub + Cloud)

### Push to GitHub:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/crypto-bot.git
git push -u origin main
```

### Run on cloud (e.g. VPS / Railway / Render):
```bash
# Clone
git clone https://github.com/yourusername/crypto-bot.git
cd crypto-bot

# Install
pip install -r requirements.txt

# Run
python main.py
```

> ⚠️ Never commit your Telegram token to GitHub.
> Use environment variables or a `.env` file (already in `.gitignore`).

---

## 📝 Notes

- Binance public API is used — no account or API key needed
- Outcome is simulated from historical data (72 bar lookahead)
- TP1 hit → SL moves to breakeven → waits for TP2
- Charts saved to `charts/` folder automatically
"# Cryptodos" 
