"""Telegram notifier — pushes alerts to a phone via the Bot API.

Free, no account-linking beyond creating a bot with @BotFather. The pipeline
calls send_alert() when the decision engine raises something worth shouting
about; we attach the trigger snapshot and the recorded clip.

It degrades gracefully: if the token/chat id aren't set in .env, every call is
a no-op (logged once) instead of an error, so the rest of the system keeps
working without Telegram configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.base = f"https://api.telegram.org/bot{self.token}"

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    # ---- low-level helpers ----------------------------------------------
    def _post(self, method: str, data: dict, files: dict | None = None) -> bool:
        try:
            r = httpx.post(f"{self.base}/{method}", data=data, files=files, timeout=30)
            r.raise_for_status()
            return True
        except (httpx.HTTPError, OSError) as exc:
            logger.error("Telegram %s failed: %s", method, exc)
            return False

    def send_message(self, text: str) -> bool:
        return self._post("sendMessage", {"chat_id": self.chat_id, "text": text})

    def send_photo(self, path: str, caption: str = "") -> bool:
        p = Path(path)
        if not p.exists():
            return False
        with p.open("rb") as f:
            return self._post(
                "sendPhoto",
                {"chat_id": self.chat_id, "caption": caption[:1024]},
                files={"photo": (p.name, f, "image/jpeg")},
            )

    def send_video(self, path: str, caption: str = "") -> bool:
        p = Path(path)
        if not p.exists():
            return False
        # Bot API caps uploads at ~50 MB; our short clips are well under that.
        if p.stat().st_size > 49 * 1024 * 1024:
            logger.warning("Clip %s too large for Telegram, skipping video", p.name)
            return False
        with p.open("rb") as f:
            return self._post(
                "sendVideo",
                {"chat_id": self.chat_id, "caption": caption[:1024]},
                files={"video": (p.name, f, "video/mp4")},
            )

    # ---- high-level ------------------------------------------------------
    def send_alert(
        self,
        *,
        alert_type: str,
        message: str,
        snapshot_path: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> bool:
        """Send a full alert: tagged text, the snapshot, then the clip."""
        if not self.enabled:
            logger.info("Telegram not configured (set TELEGRAM_* in .env) — skipping")
            return False

        header = {"emergency": "🚨 EMERGENCY", "suspicious": "⚠️ SUSPICIOUS"}.get(
            alert_type, "ℹ️ ALERT"
        )
        caption = f"{header}\n{message}"

        # Prefer photo-with-caption so the alert text rides along with the image.
        if snapshot_path and Path(snapshot_path).exists():
            ok = self.send_photo(snapshot_path, caption)
        else:
            ok = self.send_message(caption)

        if video_path and Path(video_path).exists():
            self.send_video(video_path, "Clip")
        return ok
