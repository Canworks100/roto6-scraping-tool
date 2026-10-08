"""収集失敗などの運用通知。Webhook URL は環境変数のみ（リポジトリに書かない）。"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("loto6")

ENV_WEBHOOK = "LOTO_ALERT_WEBHOOK"


def alert(text: str, *, channel_hint: str = "#vps-監視") -> bool:
    """Slack Incoming Webhook 等へ投稿する。未設定ならログのみで False。"""
    url = (os.environ.get(ENV_WEBHOOK) or "").strip()
    payload = {"text": f"[{channel_hint}] {text}"}
    if not url:
        logger.warning("通知スキップ（%s 未設定）: %s", ENV_WEBHOOK, text)
        return False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = 200 <= getattr(resp, "status", 200) < 300
            if not ok:
                logger.error("通知HTTP失敗 status=%s", getattr(resp, "status", "?"))
            return ok
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("通知送信失敗: %s", exc)
        return False
