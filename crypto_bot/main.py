"""
╔══════════════════════════════════════════════════════════════╗
║           CRYPTO BACKTEST BOT v5 — MAIN ENTRY               ║
║  Run this file to start the backtest.                        ║
║  All config is in src/config.py                              ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python main.py

Requirements:
    pip install -r requirements.txt
"""

from src.backtest import run_backtest

if __name__ == "__main__":
    run_backtest()
