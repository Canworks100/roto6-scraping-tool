"""リクエスト間隔とリトライ付きの取得。"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger("loto6")


class FetchError(RuntimeError):
    """リトライ後も取得できなかった。"""


class HttpClient:
    def __init__(self, config: dict[str, Any]) -> None:
        rate = config["rate_limit"]
        site = config["site"]
        self.min_interval = float(rate["min_interval_sec"])
        self.max_interval = float(rate["max_interval_sec"])
        self.timeout = float(rate["timeout_sec"])
        self.max_retries = int(rate["max_retries"])
        self.backoff = float(rate["backoff_sec"])
        self.base_url = site["base_url"].rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": site["user_agent"],
                "Accept": "text/html,text/plain,*/*",
                "Accept-Language": "ja,en;q=0.8",
                "Referer": self.base_url + site["current_page"],
            }
        )

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return self.base_url + "/" + path.lstrip("/")

    def get(self, path: str) -> tuple[int, bytes]:
        """(status, body) を返す。404 は例外にしない。それ以外の失敗は FetchError。"""
        target = self.url(path)
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            try:
                response = self.session.get(target, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("通信失敗 %s (試行 %s/%s): %s", target, attempt, self.max_retries, exc)
                self._backoff(attempt)
                continue
            if response.status_code == 404:
                logger.info("該当なし %s", target)
                return 404, b""
            if response.status_code >= 400:
                last_error = FetchError(f"HTTP {response.status_code} {target}")
                logger.warning("HTTP %s %s (試行 %s/%s)", response.status_code, target, attempt, self.max_retries)
                self._backoff(attempt)
                continue
            return response.status_code, response.content
        raise FetchError(f"取得できませんでした: {target}") from last_error

    def _wait(self) -> None:
        # リクエストの直前に必ず 2〜3 秒の待ちを入れる。
        time.sleep(random.uniform(self.min_interval, self.max_interval))

    def _backoff(self, attempt: int) -> None:
        time.sleep(self.backoff * attempt)

    def close(self) -> None:
        self.session.close()
