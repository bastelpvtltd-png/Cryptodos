# ══════════════════════════════════════════════════════════════════
# src/telegram.py
# Send text alerts and chart images to a Telegram bot.
# ══════════════════════════════════════════════════════════════════

import time
import requests
from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_alert(message: str) -> None:
    """
    Send a Markdown-formatted text message to Telegram.
    Automatically splits messages longer than 4000 characters.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
        try:
            r = requests.post(
                url,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"},
                timeout=10,
            )
            # Fallback: plain text if Markdown parse fails
            if r.status_code != 200:
                requests.post(
                    url,
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk},
                    timeout=10,
                )
        except Exception as e:
            print(f"  ⚠️  Telegram alert error: {e}")
        time.sleep(0.3)


def send_chart(photo_path: str, caption: str) -> bool:
    """
    Send a chart image with a caption to Telegram.

    Returns True if successful, False otherwise.
    """
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    caption = caption[:1020]   # Telegram caption limit

    try:
        with open(photo_path, "rb") as photo:
            r = requests.post(
                url,
                data={
                    "chat_id"    : TELEGRAM_CHAT_ID,
                    "caption"    : caption,
                    "parse_mode" : "Markdown",
                },
                files={"photo": photo},
                timeout=15,
            )
        return r.status_code == 200
    except Exception as e:
        print(f"  ⚠️  Telegram chart send error: {e}")
        return False
