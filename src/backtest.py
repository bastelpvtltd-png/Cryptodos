# ══════════════════════════════════════════════════════════════════
# src/backtest.py
# Main orchestrator — loops through date range, coins, signals.
# Calls all other modules. No logic here, just coordination.
# ══════════════════════════════════════════════════════════════════

import time
import pandas as pd

from src.config     import (
    START_DATE, END_DATE, WATCH_LIST, BLOCKED_COINS,
    STARTING_BALANCE, DATA_LIMIT, MIN_SCORE, MIN_RR,
    MAX_SIGNALS_PER_COIN, COOLDOWN_BARS, LK_OFFSET_SEC,
    SCORE_ALLOC_PCT, MIN_TRADE_USD,
)
from src.balance    import BalanceManager
from src.data       import download_data, get_htf_trend, date_to_ms, ms_to_lk, get_date_range
from src.indicators import compute_indicators
from src.patterns   import find_key_levels
from src.scoring    import score_signal, calculate_levels, check_outcome, calc_pnl_usd
from src.chart      import build_chart
from src.telegram   import send_alert, send_chart
from src.reports    import send_daily_summary, send_final_summary


# ── Per-signal message builder ────────────────────────────────────
def _build_signal_msg(
    coin, direction, score, htf_trend, rr,
    entry, sl, tp1, tp2,
    alloc_usd, alloc_pct, bal_before, new_bal, pnl_usd,
    outcome, result_pct, candles,
    sig_lk, result_lk, reasons,
    is_win, is_be,
) -> str:
    rl = (
        f"✅ WIN  +{result_pct:.2f}% (+${pnl_usd:.2f})"  if is_win  else
        f"🟡 BE   {result_pct:+.2f}% (+${pnl_usd:.2f})"  if is_be   else
        f"🔵 OPEN {result_pct:+.2f}% (${pnl_usd:+.2f})"  if outcome == "STILL_OPEN" else
        f"❌ LOSS {result_pct:.2f}% (-${abs(pnl_usd):.2f})"
    )
    time_ln = (
        "⏳ Still open (72h)" if outcome == "STILL_OPEN"
        else f"⏰ {result_lk} ({candles}h)"
    )
    alloc_pct_of_bal = (alloc_usd / bal_before * 100) if bal_before > 0 else 0
    em = "✅" if is_win else "🟡" if is_be else "🔵" if outcome == "STILL_OPEN" else "❌"

    return (
        f"{'📈' if direction=='LONG' else '📉'} *{direction} {coin}* {em}\n"
        f"📅 {sig_lk}\n"
        f"Score `{score}` | HTF `{htf_trend}` | RR `1:{rr:.1f}`\n\n"
        f"💵 Entry `${entry:.4f}` | SL `${sl:.4f}`\n"
        f"🎯 TP1 `${tp1:.4f}` | TP2 `${tp2:.4f}`\n\n"
        f"━━ 💰 ALLOCATION ━━\n"
        f"Score {score} → {alloc_pct:.0f}% of available\n"
        f"Allocated : `${alloc_usd:.2f}` ({alloc_pct_of_bal:.1f}% of balance)\n\n"
        f"{rl}\n{time_ln}\n\n"
        f"━━ 📊 BALANCE UPDATE ━━\n"
        f"Before : `${bal_before:.2f}`\n"
        f"P&L    : `${pnl_usd:+.2f}`\n"
        f"*After  : `${new_bal:.2f}`* 💵\n\n"
        f"_{' | '.join(reasons[:5])}_"
    )


# ── Single day processor ──────────────────────────────────────────
def process_day(date_str: str, active_coins: list[str], bm: BalanceManager) -> list[dict]:
    """
    Scan all coins for signals on a given date.
    For each qualifying signal, simulate the trade and update balance.
    Returns list of trade result dicts.
    """
    print(f"\n{'─'*55}")
    print(f"  📅 {date_str}  |  Balance: ${bm.balance:.2f}  Available: ${bm.available():.2f}")
    print(f"{'─'*55}")

    start_ms = date_to_ms(date_str, end_of_day=False)
    end_ms   = date_to_ms(date_str, end_of_day=True)
    day_results: list[dict] = []

    for coin in active_coins:

        # Stop scanning if no capacity/balance left
        if not bm.can_open():
            print("  ⛔ Max open trades or insufficient balance — skipping remaining coins")
            break

        print(f"  📥 {coin}...")

        # ── HTF trend check ────────────────────────────────────────
        htf_trend, htf_strength = get_htf_trend(coin, end_ms=end_ms)
        if htf_trend == "NEUTRAL":
            print(f"     Neutral HTF — skip")
            continue

        # ── Download 1H data (include 72h future for outcome check) ──
        df_full = download_data(
            coin, interval="1h", limit=DATA_LIMIT,
            end_ms=end_ms + 72 * 3_600_000,
        )
        if df_full is None or len(df_full) < 100:
            continue

        df_ind   = compute_indicators(df_full)
        key_lvls = find_key_levels(df_ind)

        # ── Filter candles within today's window ──────────────────
        mask    = (df_full["Open_time"] >= start_ms) & (df_full["Open_time"] <= end_ms)
        targets = df_full.index[mask].tolist()
        if not targets:
            print(f"     No candles on {date_str}")
            continue

        last_sig   = {"LONG": -99, "SHORT": -99}
        coin_count = 0
        directions = ["LONG"] if htf_trend == "BULL" else ["SHORT"]

        for i in targets:
            if i < 100:
                continue
            if coin_count >= MAX_SIGNALS_PER_COIN:
                break
            if not bm.can_open():
                break

            c = df_ind.iloc[i]
            required = ["ATR", "EMA200", "STOCHRSI", "ADX"]
            if any(pd.isna(c.get(k, float("nan"))) for k in required):
                continue

            for direction in directions:
                # Cooldown check
                if i - last_sig[direction] < COOLDOWN_BARS:
                    continue

                # ── Score the signal ───────────────────────────────
                score, reasons = score_signal(
                    df_ind, i, direction, htf_trend, htf_strength, key_lvls
                )
                if score < MIN_SCORE:
                    continue

                # ── Calculate levels ───────────────────────────────
                entry = float(c["close"])
                sl, tp1, tp2, sl_pct, tp1_pct, rr = calculate_levels(
                    df_ind, i, direction, entry
                )
                if rr < MIN_RR:
                    continue

                # ── Dynamic allocation from current balance ────────
                alloc_usd, alloc_pct = bm.get_allocation(score)
                if alloc_usd < MIN_TRADE_USD:
                    print(f"     ⚠️  Balance too low (${bm.available():.2f}) — skip {coin}")
                    send_alert(
                        f"⚠️ *{coin} {direction} SKIPPED*\n"
                        f"Score `{score}` | Available `${bm.available():.2f}`\n"
                        f"_Balance too low (min ${MIN_TRADE_USD:.0f})_"
                    )
                    continue

                # ── Check historical outcome ───────────────────────
                outcome, result_pct, candles, result_ms = check_outcome(
                    df_full, i, direction, entry, tp1, tp2, sl
                )

                # ── USD P&L ────────────────────────────────────────
                pnl_usd = calc_pnl_usd(
                    outcome, result_pct, alloc_usd, entry, tp1, tp2, sl, direction
                )

                # ── Update simulated balance ───────────────────────
                trade_id = f"{coin}_{direction}_{i}"
                bm.open_trade({"trade_id": trade_id, "allocated_usd": alloc_usd})
                bal_before, new_bal = bm.close_trade(trade_id, pnl_usd, outcome)

                last_sig[direction] = i
                coin_count += 1

                # ── Build labels ───────────────────────────────────
                sig_lk    = ms_to_lk(int(df_full.iloc[i]["Open_time"]))
                result_lk = ms_to_lk(result_ms)
                is_win    = outcome == "TP2_HIT" or (outcome == "STILL_OPEN" and pnl_usd > 0)
                is_be     = outcome == "BREAKEVEN"

                # ── Send Telegram message + chart ──────────────────
                msg = _build_signal_msg(
                    coin, direction, score, htf_trend, rr,
                    entry, sl, tp1, tp2,
                    alloc_usd, alloc_pct, bal_before, new_bal, pnl_usd,
                    outcome, result_pct, candles,
                    sig_lk, result_lk, reasons,
                    is_win, is_be,
                )

                chart_path = build_chart(
                    coin, df_ind, i, entry, tp1, tp2, sl,
                    direction, score, outcome, result_pct, reasons,
                    alloc_usd, bal_before, new_bal,
                )

                if chart_path:
                    sent = send_chart(chart_path, msg)
                    if not sent:
                        send_alert(msg)
                else:
                    send_alert(msg)

                # ── Record result ──────────────────────────────────
                day_results.append({
                    "date"      : date_str,
                    "coin"      : coin,
                    "direction" : direction,
                    "htf"       : htf_trend,
                    "sig_time"  : sig_lk,
                    "result_time": result_lk,
                    "score"     : score,
                    "alloc_usd" : alloc_usd,
                    "alloc_pct" : alloc_pct,
                    "bal_before": bal_before,
                    "bal_after" : new_bal,
                    "entry"     : entry,
                    "outcome"   : outcome,
                    "result_pct": result_pct,
                    "pnl_usd"   : pnl_usd,
                    "candles"   : candles,
                    "rr"        : rr,
                    "reasons"   : reasons,
                    "is_win"    : is_win,
                    "is_be"     : is_be,
                })

                em_print = "✅" if is_win else "🟡" if is_be else "🔵" if outcome == "STILL_OPEN" else "❌"
                print(
                    f"     {em_print} {direction} alloc=${alloc_usd:.2f} "
                    f"→ {outcome} ${pnl_usd:+.2f} | Bal:${new_bal:.2f}"
                )
                time.sleep(0.8)

        time.sleep(0.4)

    return day_results


# ── Main entry ────────────────────────────────────────────────────
def run_backtest() -> list[dict]:
    """Run full backtest across all dates and coins."""
    date_range   = get_date_range(START_DATE, END_DATE)
    active_coins = [c for c in WATCH_LIST if c not in BLOCKED_COINS]
    bm           = BalanceManager(STARTING_BALANCE)

    print("=" * 60)
    print(f"  BACKTEST v5 | {START_DATE} → {END_DATE}")
    print(f"  {len(date_range)} days | Balance: ${STARTING_BALANCE:.2f}")
    print(f"  Score {MIN_SCORE}+ | R:R {MIN_RR}+ | No API needed")
    print("=" * 60)

    alloc_lines = "\n".join(
        f"Score {k} → `{v:.0f}%` of available"
        for k, v in SCORE_ALLOC_PCT.items()
    )

    send_alert(
        f"🔬 *BACKTEST v5 STARTED* 🇱🇰\n\n"
        f"📅 Range   : `{START_DATE}` → `{END_DATE}` ({len(date_range)} days)\n"
        f"💵 Balance : `${STARTING_BALANCE:.2f}` → dynamic per signal\n"
        f"📐 Score   : `{MIN_SCORE}+` | R:R `{MIN_RR}+`\n\n"
        f"━━ SCORE → ALLOCATION ━━\n"
        f"{alloc_lines}\n"
        f"_(max 25% of total balance per trade)_\n\n"
        f"✅ Each signal: shows alloc USD + balance before/after\n"
        f"✅ Final report: full account summary\n"
        f"🚫 Blocked: `{', '.join(BLOCKED_COINS)}`\n"
        f"🕐 Skip 00-06 UTC dead session\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    all_results: list[dict] = []

    for idx, date_str in enumerate(date_range):
        send_alert(
            f"📅 *Day {idx+1}/{len(date_range)} — {date_str}*\n"
            f"💵 Balance  : `${bm.balance:.2f}`\n"
            f"💰 Available: `${bm.available():.2f}`"
        )

        day_results = process_day(date_str, active_coins, bm)
        all_results.extend(day_results)

        send_daily_summary(date_str, day_results, bm)
        time.sleep(1.0)

    send_final_summary(all_results, bm, date_range)

    # Console summary
    wins   = [r for r in all_results if r["is_win"]]
    losses = [r for r in all_results if not r["is_win"] and not r["is_be"]]
    print(f"\n{'='*60}")
    print(f"  v5 Done | Signals:{len(all_results)} W:{len(wins)} L:{len(losses)}")
    print(
        f"  Balance: ${bm.starting:.2f} → ${bm.balance:.2f} "
        f"({(bm.balance-bm.starting)/bm.starting*100:+.1f}%)"
    )
    print(f"{'='*60}")

    return all_results
