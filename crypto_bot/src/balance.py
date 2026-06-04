# ══════════════════════════════════════════════════════════════════
# src/balance.py
# Simulated balance tracker — no real money, no Binance API.
# Tracks open/closed trades, running balance, win/loss counts.
# ══════════════════════════════════════════════════════════════════

from src.config import SCORE_ALLOC_PCT, MAX_ALLOC_PCT, MIN_TRADE_USD, MAX_OPEN_TRADES


class BalanceManager:
    """
    Simulates a trading account.

    - balance      : current total USD (changes after each closed trade)
    - open_trades  : list of trades currently 'open' (allocated but not yet closed)
    - available()  : balance minus locked-in open trades
    - get_allocation(score) : how much USD to risk based on score + available balance
    """

    def __init__(self, starting: float):
        self.balance       = starting
        self.starting      = starting
        self.open_trades   = []       # [{"trade_id": ..., "allocated_usd": ...}]
        self.closed_trades = []
        self.wins          = 0
        self.losses        = 0
        self.bes           = 0        # breakevens

    # ── Available balance (total minus locked in open trades) ──────
    def available(self) -> float:
        locked = sum(t["allocated_usd"] for t in self.open_trades)
        return max(0.0, self.balance - locked)

    # ── Calculate USD allocation for a given score ─────────────────
    def get_allocation(self, score: int) -> tuple[float, float]:
        """
        Returns (alloc_usd, alloc_pct_used).
        alloc_pct_used = the SCORE_ALLOC_PCT value (e.g. 8.0 for score 7).
        Actual USD = min(available * pct, total_balance * MAX_ALLOC_PCT).
        """
        pct     = SCORE_ALLOC_PCT.get(min(max(score, 6), 10), 5.0)
        avail   = self.available()
        max_usd = self.balance * MAX_ALLOC_PCT
        alloc   = min(avail * (pct / 100.0), max_usd)
        return round(alloc, 4), pct

    # ── Register a new open trade ──────────────────────────────────
    def open_trade(self, trade: dict):
        """trade must have keys: trade_id, allocated_usd"""
        self.open_trades.append(trade)

    # ── Close a trade and update balance ──────────────────────────
    def close_trade(self, trade_id: str, pnl_usd: float, outcome: str) -> tuple[float, float]:
        """
        Removes trade from open_trades, applies pnl_usd to balance.
        Returns (balance_before, balance_after).
        """
        for i, t in enumerate(self.open_trades):
            if t["trade_id"] == trade_id:
                self.open_trades.pop(i)
                break

        old_balance    = self.balance
        self.balance   = round(self.balance + pnl_usd, 4)

        if outcome in ("TP2_HIT",) or (outcome == "STILL_OPEN" and pnl_usd > 0):
            self.wins   += 1
        elif outcome == "BREAKEVEN":
            self.bes    += 1
        else:
            self.losses += 1

        return old_balance, self.balance

    # ── Can we open another trade? ─────────────────────────────────
    def can_open(self) -> bool:
        return (
            len(self.open_trades) < MAX_OPEN_TRADES
            and self.available() >= MIN_TRADE_USD
        )

    # ── Summary dict (used in reports) ────────────────────────────
    def summary(self) -> dict:
        total = self.wins + self.losses + self.bes
        return {
            "starting"  : self.starting,
            "balance"   : self.balance,
            "pnl"       : round(self.balance - self.starting, 4),
            "roi_pct"   : round((self.balance - self.starting) / self.starting * 100, 2),
            "wins"      : self.wins,
            "losses"    : self.losses,
            "bes"       : self.bes,
            "total"     : total,
            "win_rate"  : round(self.wins / total * 100, 1) if total > 0 else 0.0,
        }
