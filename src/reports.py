# ══════════════════════════════════════════════════════════════════
# src/reports.py
# Daily summary and final 5-day account report generators.
# Sends formatted messages to Telegram.
# ══════════════════════════════════════════════════════════════════

import time
from src.balance  import BalanceManager
from src.telegram import send_alert
from src.config   import START_DATE, END_DATE, MIN_SCORE, STARTING_BALANCE


def send_daily_summary(date_str: str, day_results: list[dict], bm: BalanceManager) -> None:
    """
    Send end-of-day summary to Telegram.
    Shows all trades with allocation, P&L, and running balance.
    """
    if not day_results:
        send_alert(
            f"📅 *{date_str} — No signals found*\n"
            f"Balance: `${bm.balance:.2f}`"
        )
        return

    wins   = [r for r in day_results if r["is_win"]]
    bes    = [r for r in day_results if r["is_be"]]
    losses = [r for r in day_results if not r["is_win"] and not r["is_be"]]
    total  = len(day_results)

    win_rate  = len(wins) / total * 100 if total > 0 else 0
    day_pnl   = sum(r["pnl_usd"] for r in day_results)
    day_start = day_results[0]["bal_before"] if day_results else bm.balance
    grade     = "🟢" if day_pnl > 0 else "🔴" if day_pnl < 0 else "🟡"

    # Per-trade lines
    trade_lines = []
    for r in day_results:
        em = "✅" if r["is_win"] else "🟡" if r["is_be"] else "❌"
        trade_lines.append(
            f"{em} `{r['coin']}` {r['direction']} | "
            f"Alloc `${r['alloc_usd']:.2f}` → P&L `${r['pnl_usd']:+.2f}` | "
            f"Bal `${r['bal_after']:.2f}`"
        )

    send_alert(
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{grade} *DAILY REPORT — {date_str}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Trades: `{total}` | ✅`{len(wins)}` 🟡`{len(bes)}` ❌`{len(losses)}`\n"
        f"Win Rate : *{win_rate:.1f}%*\n"
        f"Day P/L  : *${day_pnl:+.2f}*\n\n"
        f"━━ 💵 ACCOUNT ━━\n"
        f"Day Start : `${day_start:.2f}`\n"
        f"Day End   : *`${bm.balance:.2f}`*\n\n"
        f"━━ TRADES ━━\n"
        + "\n".join(trade_lines)
    )


def send_final_summary(
    all_results: list[dict],
    bm: BalanceManager,
    date_range: list[str],
) -> None:
    """
    Send final multi-day account report to Telegram.
    Includes daily breakdown table + overall stats.
    """
    if not all_results:
        send_alert("⚠️ *No signals found in date range.*")
        return

    # ── Build daily stats ─────────────────────────────────────────
    daily = {
        d: {"sig": 0, "win": 0, "loss": 0, "be": 0,
            "pnl": 0.0, "start_bal": 0.0, "end_bal": 0.0}
        for d in date_range
    }
    for r in all_results:
        d = r["date"]
        if d not in daily:
            continue
        daily[d]["sig"] += 1
        daily[d]["pnl"] += r["pnl_usd"]
        if daily[d]["start_bal"] == 0:
            daily[d]["start_bal"] = r["bal_before"]
        daily[d]["end_bal"] = r["bal_after"]
        if r["is_win"]:       daily[d]["win"]  += 1
        elif r["is_be"]:      daily[d]["be"]   += 1
        else:                 daily[d]["loss"] += 1

    # ── Daily table ───────────────────────────────────────────────
    table = ["```"]
    table.append(f"{'Date':<12} {'Sig':>3} {'W':>2} {'L':>2} {'P/L':>8} {'Bal':>8}")
    table.append("─" * 42)
    prev_bal = STARTING_BALANCE
    for d in date_range:
        s  = daily[d]
        eb = s["end_bal"] if s["end_bal"] > 0 else prev_bal
        em = "🟢" if s["pnl"] > 0 else "🔴" if s["pnl"] < 0 else "⚪"
        table.append(
            f"{d:<12} {s['sig']:>3} {s['win']:>2} {s['loss']:>2} "
            f"${s['pnl']:>+7.2f} ${eb:>7.2f} {em}"
        )
        if eb > 0:
            prev_bal = eb
    table.append("─" * 42)
    t_sig = sum(v["sig"]  for v in daily.values())
    t_win = sum(v["win"]  for v in daily.values())
    t_los = sum(v["loss"] for v in daily.values())
    t_pnl = sum(v["pnl"]  for v in daily.values())
    table.append(
        f"{'TOTAL':<12} {t_sig:>3} {t_win:>2} {t_los:>2} "
        f"${t_pnl:>+7.2f} ${bm.balance:>7.2f}"
    )
    table.append("```")

    send_alert(
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *DAILY BREAKDOWN*\n"
        f"*{START_DATE} → {END_DATE}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(table)
    )
    time.sleep(0.5)

    # ── Overall stats ─────────────────────────────────────────────
    wins   = [r for r in all_results if r["is_win"]]
    bes    = [r for r in all_results if r["is_be"]]
    losses = [r for r in all_results if not r["is_win"] and not r["is_be"]]
    total  = len(all_results)

    win_rate   = len(wins) / total * 100 if total > 0 else 0
    avg_win    = sum(r["pnl_usd"] for r in wins)   / len(wins)   if wins   else 0
    avg_loss   = sum(r["pnl_usd"] for r in losses) / len(losses) if losses else 0
    avg_alloc  = sum(r["alloc_usd"] for r in all_results) / total if total > 0 else 0
    avg_rr     = sum(r["rr"]        for r in all_results) / total if total > 0 else 0
    roi        = (bm.balance - bm.starting) / bm.starting * 100
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    best  = max(all_results, key=lambda x: x["pnl_usd"])
    worst = min(all_results, key=lambda x: x["pnl_usd"])

    grade = (
        "🏆 LIVE READY"   if win_rate >= 55 and t_pnl > 0 else
        "⚠️ NEEDS TUNING" if win_rate >= 45                else
        "❌ NOT READY"
    )

    send_alert(
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 *FINAL ACCOUNT REPORT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 Start Balance : `${bm.starting:.2f}`\n"
        f"💰 *Final Balance : `${bm.balance:.2f}`*\n"
        f"📈 Total P/L     : *${t_pnl:+.2f}*\n"
        f"📊 ROI           : *{roi:+.2f}%*\n\n"
        f"━━ TRADE STATS ━━\n"
        f"Total Trades : `{total}`\n"
        f"✅ Wins       : `{len(wins)}`\n"
        f"🟡 Breakeven  : `{len(bes)}`\n"
        f"❌ Losses     : `{len(losses)}`\n\n"
        f"🏆 Win Rate   : *{win_rate:.1f}%*\n"
        f"📐 Avg R:R    : `1:{avg_rr:.1f}`\n"
        f"💵 Avg Alloc  : `${avg_alloc:.2f}` per trade\n"
        f"🎯 Expectancy : `${expectancy:.2f}` per trade\n\n"
        f"━━ P&L ━━\n"
        f"💚 Avg Win  : `+${avg_win:.2f}`\n"
        f"💔 Avg Loss : `-${abs(avg_loss):.2f}`\n\n"
        f"🥇 Best  : `{best['coin']}` *+${best['pnl_usd']:.2f}*\n"
        f"💀 Worst : `{worst['coin']}` *${worst['pnl_usd']:+.2f}*\n\n"
        f"*Verdict: {grade}*\n\n"
        f"_Backtest v5 • Dynamic Balance • Score {MIN_SCORE}+ • ADX 18+ • Supertrend_"
    )
