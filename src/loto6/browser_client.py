"""Chrome CDP経由でみずほ銀行のページ/CSVを取得する。"""

from __future__ import annotations

import json
import logging
import random
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from loto6.client import FetchError

logger = logging.getLogger("loto6")

CHROME = Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
PROFILE = Path("/mnt/c/Users/can25/AppData/Local/loto6-collect-chrome")
PROFILE_WIN = r"C:\Users\can25\AppData\Local\loto6-collect-chrome"
DEBUG_PORT = 9224


class BrowserClient:
    """Akamai対策として、実ChromeのリクエストAPIで取得する。"""

    def __init__(self, config: dict[str, Any]) -> None:
        rate = config["rate_limit"]
        site = config["site"]
        self.min_interval = float(rate["min_interval_sec"])
        self.max_interval = float(rate["max_interval_sec"])
        self.max_retries = int(rate["max_retries"])
        self.backoff = float(rate["backoff_sec"])
        self.base_url = site["base_url"].rstrip("/")
        self.current_page = site["current_page"]
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._open()

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return self.base_url + "/" + path.lstrip("/")

    def get(self, path: str) -> tuple[int, bytes]:
        target = self.url(path)
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            try:
                self._ensure_context()
                response = self._context.request.get(target, timeout=60000)
            except Exception as exc:  # noqa: BLE001 - CDP切断を含めてリトライ
                last_error = exc
                logger.warning("通信失敗 %s (試行 %s/%s): %s", target, attempt, self.max_retries, exc)
                self._reconnect()
                self._backoff(attempt)
                continue
            status = response.status
            body = response.body()
            if status == 404:
                logger.info("該当なし %s", target)
                return 404, b""
            if status >= 400:
                last_error = FetchError(f"HTTP {status} {target}")
                logger.warning("HTTP %s %s (試行 %s/%s)", status, target, attempt, self.max_retries)
                self._backoff(attempt)
                continue
            return status, body
        raise FetchError(f"取得できませんでした: {target}") from last_error

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    def _open(self) -> None:
        endpoint = _ensure_chrome(self.base_url + self.current_page)
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(endpoint)
        self._ensure_context()
        self._page.goto(self.base_url + self.current_page, wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(800)

    def _ensure_context(self) -> None:
        if self._browser is None:
            raise FetchError("Chromeに接続できません")
        if not self._browser.contexts:
            self._context = self._browser.new_context()
        else:
            self._context = self._browser.contexts[0]
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def _reconnect(self) -> None:
        self.close()
        time.sleep(1)
        self._open()

    def _wait(self) -> None:
        time.sleep(random.uniform(self.min_interval, self.max_interval))

    def _backoff(self, attempt: int) -> None:
        time.sleep(self.backoff * attempt)


def _ensure_chrome(start_url: str) -> str:
    endpoint = _debug_endpoint()
    if endpoint:
        return endpoint
    if not CHROME.exists():
        raise RuntimeError("Chromeが見つからないため、収集できません。")
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(CHROME),
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={PROFILE_WIN}",
            "--no-first-run",
            "--new-window",
            start_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        endpoint = _debug_endpoint()
        if endpoint:
            return endpoint
        time.sleep(0.25)
    raise RuntimeError("Chromeのデバッグ接続を開けませんでした。")


def _debug_endpoint() -> str | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if payload.get("webSocketDebuggerUrl"):
        return f"http://127.0.0.1:{DEBUG_PORT}"
    return None
