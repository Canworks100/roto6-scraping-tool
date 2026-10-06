"""ログイン済みの宝くじ公式サイトから購入履歴を読む。パスワードは受け取らない。"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from loto6.ledger import Ledger
from loto6.purchase_import import fallback_date, list_has_loto6, parse_detail_page

HISTORY_URL = "https://www.takarakuji-official.jp/mypage/history/"
MYPAGE_URL = "https://www.takarakuji-official.jp/mypage/"
DEBUG_PORT = 9223
CHROME = Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
PROFILE = Path("/mnt/c/Users/can25/AppData/Local/loto6-chrome-profile")
PROFILE_WIN = r"C:\Users\can25\AppData\Local\loto6-chrome-profile"
WAIT_SECONDS = 180


class ImportBusy(RuntimeError):
    """取り込みがすでに動いている。"""


class OfficialImport:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state = {"status": "idle", "message": "", "added": 0, "skipped": 0}

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)

    def start(self, ledger: Ledger) -> dict:
        with self._lock:
            if self.state["status"] == "running":
                raise ImportBusy("取り込み中です")
            self.state = {
                "status": "running",
                "message": "Chromeで宝くじ公式サイトを開いています。ログインしてください。",
                "added": 0,
                "skipped": 0,
            }
        threading.Thread(target=self._run, args=(ledger,), daemon=True).start()
        return self.snapshot()

    def _set(self, **values: object) -> None:
        with self._lock:
            self.state.update(values)

    def _run(self, ledger: Ledger) -> None:
        try:
            added, skipped = _import_history(ledger, self._set)
            if added == 0 and skipped == 0:
                self._set(
                    status="error",
                    message="ロト6の購入詳細が見つかりませんでした。ログインして「購入履歴」の「購入済み」を表示し、もう一度押してください。",
                )
                return
            self._set(
                status="done",
                added=added,
                skipped=skipped,
                message=f"{added}件を記録しました。取り込み済みは{skipped}件です。",
            )
        except Exception as exc:
            self._set(status="error", message=str(exc), added=0, skipped=0)


def _import_history(ledger: Ledger, update) -> tuple[int, int]:
    endpoint = _ensure_chrome()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(endpoint)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        if "takarakuji-official.jp" not in (page.url or ""):
            page.goto(HISTORY_URL, wait_until="domcontentloaded")
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            text = page.inner_text("body")
            if "ログイン" in (page.title() or "") and "購入履歴" not in (page.title() or ""):
                update(message="公式サイトのログイン画面です。メールアドレスとパスワードはそちらに入力してください。")
                page.wait_for_timeout(2000)
                continue
            if "/mypage/history/detail" in (page.url or ""):
                items = parse_detail_page(text)
                if items:
                    return _save(ledger, items)
            if list_has_loto6(text) or "購入履歴" in (page.title() or ""):
                update(message="購入履歴の詳細を開いて、ロト6の申込数字を取り込んでいます…")
                return _import_from_list(page, ledger, update)
            if "mypage" in (page.url or ""):
                _click_text(page, "購入履歴")
                page.wait_for_timeout(800)
            else:
                page.goto(HISTORY_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
    return 0, 0


def _import_from_list(page, ledger: Ledger, update) -> tuple[int, int]:
    _open_history_list(page)
    added = skipped = 0
    detail_count = page.locator("text=詳細を見る").count()
    if detail_count == 0:
        items = parse_detail_page(page.inner_text("body"))
        if items:
            return _save(ledger, items)
        return added, skipped

    for index in range(detail_count):
        update(message=f"詳細を取り込んでいます（{index + 1}/{detail_count}）…")
        _open_history_list(page)
        links = page.locator("text=詳細を見る")
        if links.count() <= index:
            break
        row_text = _row_text(links.nth(index))
        if row_text and "ロト6" not in row_text and "ロト６" not in row_text:
            continue
        links.nth(index).click(timeout=5000)
        for _ in range(25):
            if "/mypage/history/detail" in (page.url or ""):
                break
            page.wait_for_timeout(200)
        page.wait_for_timeout(500)
        items = parse_detail_page(page.inner_text("body"))
        if items:
            a, s = _save(ledger, items)
            added += a
            skipped += s
    return added, skipped


def _open_history_list(page) -> None:
    page.goto(HISTORY_URL, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(500)
    _click_text(page, "購入済み")
    page.wait_for_timeout(800)


def _row_text(locator) -> str:
    try:
        return locator.evaluate(
            """el => {
              let node = el;
              for (let i = 0; i < 8 && node; i++) {
                const t = (node.innerText || '').replace(/\\s+/g, ' ');
                if (t.includes('ロト') || t.includes('第')) return t.slice(0, 240);
                node = node.parentElement;
              }
              return '';
            }"""
        )
    except Exception:
        return ""


def _click_text(page, label: str) -> bool:
    locator = page.get_by_text(label, exact=True)
    try:
        if locator.count() == 0:
            locator = page.get_by_text(label)
        if locator.count() == 0:
            return False
        locator.first.click(timeout=1500)
        return True
    except Exception:
        return False


def _save(ledger: Ledger, items: list[dict]) -> tuple[int, int]:
    added = 0
    skipped = 0
    for item in items:
        numbers = item["numbers"]
        if ledger.has_same(item["draw_no"], numbers):
            skipped += 1
            continue
        purchased_on = item["purchased_on"]
        if not purchased_on:
            detail = ledger.draw_detail(item["draw_no"])
            purchased_on = fallback_date(detail["draw_date"] if detail else None)
        ledger.add_ticket(
            {
                "draw_no": item["draw_no"],
                "numbers": numbers,
                "ticket_count": item["ticket_count"],
                "unit_price": 200,
                "purchased_on": purchased_on,
                "note": "宝くじ公式サイト",
                "prize_override": None,
            }
        )
        added += 1
    return added, skipped


def _ensure_chrome() -> str:
    endpoint = _debug_endpoint()
    if endpoint:
        return endpoint
    if not CHROME.exists():
        raise RuntimeError("Chromeが見つからないため、公式サイトを開けません。")
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(CHROME),
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={PROFILE_WIN}",
            "--no-first-run",
            "--new-window",
            HISTORY_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        endpoint = _debug_endpoint()
        if endpoint:
            return endpoint
        time.sleep(0.25)
    raise RuntimeError("Chromeの購入履歴画面を開けませんでした。")


def _debug_endpoint() -> str | None:
    for host in ("127.0.0.1",):
        url = f"http://{host}:{DEBUG_PORT}/json/version"
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            continue
        if payload.get("webSocketDebuggerUrl"):
            return f"http://{host}:{DEBUG_PORT}"
    return None
