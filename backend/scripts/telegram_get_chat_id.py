"""Find your Telegram chat id so alerts know where to go.

Steps:
  1. Create a bot: message @BotFather, send /newbot, copy the token it gives you.
  2. Put the token in backend/.env as TELEGRAM_BOT_TOKEN=...
  3. Open your new bot in Telegram and send it any message (e.g. "hi").
  4. Run this:  python scripts/telegram_get_chat_id.py
  5. Copy the chat id it prints into .env as TELEGRAM_CHAT_ID=...

You can also pass the token directly:
     python scripts/telegram_get_chat_id.py --token 123456:ABC...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=settings.TELEGRAM_BOT_TOKEN)
    args = parser.parse_args()

    if not args.token:
        print("No bot token. Set TELEGRAM_BOT_TOKEN in .env or pass --token.")
        return 1

    url = f"https://api.telegram.org/bot{args.token}/getUpdates"
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")
        return 1

    updates = resp.json().get("result", [])
    if not updates:
        print("No messages yet. Send your bot a message in Telegram, then re-run.")
        return 1

    seen = {}
    for u in updates:
        chat = (u.get("message") or u.get("edited_message") or {}).get("chat", {})
        if chat.get("id"):
            seen[chat["id"]] = chat.get("username") or chat.get("first_name") or "?"

    print("Found chat id(s):")
    for cid, who in seen.items():
        print(f"  {cid}   ({who})")
    print("\nPut the id into backend/.env:  TELEGRAM_CHAT_ID=<id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
