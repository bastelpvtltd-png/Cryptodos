# ══════════════════════════════════════════════════════════════════
# src/chart.py
# Builds dark-mode candlestick charts with entry/TP/SL lines
# and balance change info. Saves to charts/ folder.
# ══════════════════════════════════════════════════════════════════

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf

from src.config import CHARTS_DIR

os.makedirs(CHARTS_DIR, exist_ok=True)

# Dark theme style
_DARK_STYLE = mpf.make_mpf_style(
    base_mpf_style="charles",
    rc={
        "axes.facecolor"  : "#0D1117",
        "figure.facecolor": "#0D1117",
        "axes.edgecolor"  : "#30363D",
        "text.color"      : "#E6EDF3",
        "axes.labelcolor" : "#E6EDF3",
        "xtick.color"     : "#8B949E",
        "ytick.color"     : "#8B949E",
        "grid.color"      : "#21262D",
        "grid.linestyle"  : "--",
        "grid.linewidth"  : 0.4,
    },
)


def build_chart(
    coin: str,
    df_raw: pd.DataFrame,
    signal_idx: int,
    entry: float,
    tp1: float,
    tp2: float,
    sl: float,
    direction: str,
    score: int,
    outcome: str,
    pnl_pct: float,
    reasons: list[str],
    alloc_usd: float,
    bal_before: float,
    bal_after: float,
) -> str | None:
    """
    Build a candlestick chart with entry/TP/SL levels and balance info.

    Returns:
        Path to saved PNG file, or None if chart creation fails.
    """
    try:
        end_idx   = signal_idx + 1
        start_idx = max(0, end_idx - 60)
        chart_df  = df_raw.iloc[start_idx:end_idx].copy()

        if len(chart_df) < 5:
            return None

        chart_df["datetime"] = pd.to_datetime(chart_df["Open_time"], unit="ms")
        chart_df = (
            chart_df
            .set_index("datetime")[["open", "high", "low", "close", "volume"]]
            .astype(float)
        )
        chart_df.index.name = "Date"
        n = len(chart_df)

        # Horizontal lines
        add_plots = [
            mpf.make_addplot([entry] * n, color="#2196F3", linestyle="--", width=2.0),
            mpf.make_addplot([tp1]   * n, color="#4CAF50", linestyle="-",  width=1.8),
            mpf.make_addplot([tp2]   * n, color="#1B5E20", linestyle="-",  width=1.5),
            mpf.make_addplot([sl]    * n, color="#F44336", linestyle="-",  width=1.8),
        ]

        # Outcome label + color
        if outcome == "TP2_HIT" or (outcome == "STILL_OPEN" and pnl_pct > 0):
            rc = "#4CAF50"; rl = f"WIN +{pnl_pct:.2f}%"
        elif outcome == "BREAKEVEN":
            rc = "#FF9800"; rl = f"BE {pnl_pct:+.2f}%"
        elif outcome == "STILL_OPEN":
            rc = "#2196F3"; rl = f"OPEN {pnl_pct:+.2f}%"
        else:
            rc = "#F44336"; rl = f"LOSS {pnl_pct:.2f}%"

        fname = os.path.join(CHARTS_DIR, f"{coin}_{direction}_{signal_idx}.png")
        fig, axes = mpf.plot(
            chart_df,
            type="candle",
            style=_DARK_STYLE,
            addplot=add_plots,
            volume=True,
            figsize=(14, 8),
            returnfig=True,
            tight_layout=True,
        )
        ax = axes[0]
        dc = "#4CAF50" if direction == "LONG" else "#F44336"

        ax.set_title(
            f"  {coin} 1H {direction}  Score:{score}  Alloc:${alloc_usd:.2f}",
            fontsize=13, fontweight="bold", color=dc, pad=10, loc="left",
        )

        # Outcome badge
        ax.text(
            0.99, 0.97, rl,
            transform=ax.transAxes, fontsize=12, fontweight="bold",
            color=rc, ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0D1117", edgecolor=rc, linewidth=2),
        )

        # Balance change box
        bal_color   = "#4CAF50" if bal_after >= bal_before else "#F44336"
        pnl_display = bal_after - bal_before
        ax.text(
            0.99, 0.08,
            f"${bal_before:.2f} → ${bal_after:.2f}  ({pnl_display:+.2f})",
            transform=ax.transAxes, fontsize=9, fontweight="bold",
            color=bal_color, ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0D1117",
                      edgecolor=bal_color, linewidth=1.5),
        )

        # Levels info
        ax.text(
            0.01, 0.04,
            f"E:${entry:.4f}  TP1:${tp1:.4f}  TP2:${tp2:.4f}  SL:${sl:.4f}  [Alloc:${alloc_usd:.2f}]",
            transform=ax.transAxes, fontsize=8, family="monospace",
            color="#E6EDF3", va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#161B22", edgecolor="#30363D"),
        )

        # Reasons
        ax.text(
            0.01, 0.97, " | ".join(reasons[:5]),
            transform=ax.transAxes, fontsize=8, color="#8B949E", va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#161B22",
                      edgecolor="#30363D", alpha=0.85),
        )

        # Price annotations
        for price, color, label in [
            (entry, "#2196F3", "E"),
            (tp1,   "#4CAF50", "T1"),
            (tp2,   "#1B5E20", "T2"),
            (sl,    "#F44336", "SL"),
        ]:
            ax.axhline(y=price, color=color,
                       linestyle="--" if price == entry else "-",
                       linewidth=1.1, alpha=0.7)
            ax.annotate(
                f" {label}", xy=(1.0, price),
                xycoords=("axes fraction", "data"),
                fontsize=8, color=color, fontweight="bold", va="center",
            )

        fig.savefig(fname, dpi=130, facecolor="#0D1117", bbox_inches="tight")
        plt.close(fig)

        return fname if os.path.exists(fname) and os.path.getsize(fname) > 1000 else None

    except Exception as e:
        print(f"  ⚠️  Chart error [{coin}]: {e}")
        return None
