"""ローカルで開くロト6アプリ。収支・傾向・過去履歴をタブで切り替える。"""

from __future__ import annotations

import json
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from loto6.analyze import analyze, to_payload
from loto6.config import load_config
from loto6.ledger import Ledger, LedgerError
from loto6.official import ImportBusy, OfficialImport
from loto6.scrape import years_ago

HTML_PATH = Path(__file__).with_name("web") / "index.html"
CHROME = Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
HOST = "127.0.0.1"
PORT_START = 8736


def run(db_path: Path, open_window: bool = True) -> int:
    ledger = Ledger(db_path)
    config = load_config()
    server = _listen(ledger, config, OfficialImport())
    port = server.server_address[1]
    url = f"http://{HOST}:{port}/"
    print(f"ロト6アプリ: {url}")
    print("終了するときは画面の「終了」か、この窓で Ctrl+C")
    if open_window:
        threading.Thread(target=_open_window, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        server.server_close()
        ledger.close()
    return 0


def _listen(ledger: Ledger, config: dict, importer: OfficialImport) -> HTTPServer:
    handler = _handler(ledger, config, importer)
    last_error: OSError | None = None
    for port in range(PORT_START, PORT_START + 10):
        try:
            return HTTPServer((HOST, port), handler)
        except OSError as exc:
            last_error = exc
    raise OSError(f"ポート {PORT_START} から10個が使えません") from last_error


def _open_window(url: str) -> None:
    if CHROME.exists():
        subprocess.Popen(
            [str(CHROME), f"--app={url}", "--window-size=1180,900"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    webbrowser.open(url)


def _handler(ledger: Ledger, config: dict, importer: OfficialImport) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/":
                self._bytes(200, HTML_PATH.read_text(encoding="utf-8").encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/summary":
                self._json(ledger.summary())
                return
            if path == "/api/tickets":
                self._json(ledger.list_tickets())
                return
            if path == "/api/draws":
                self._json(ledger.recent_draws())
                return
            if path == "/api/history":
                # limit=0 で全件
                limit = _int_query(query, "limit", 0, 0, 20000)
                offset = _int_query(query, "offset", 0, 0, 100000)
                self._json(ledger.history(limit=limit, offset=offset))
                return
            if path == "/api/history/search":
                try:
                    self._json(_history_search(ledger, query))
                except LedgerError as exc:
                    self._json({"error": str(exc)}, status=400)
                return
            if path == "/api/analysis":
                self._json(_analysis(ledger, config, query))
                return
            if path == "/api/import-status":
                self._json(importer.snapshot())
                return
            if path.startswith("/api/draws/"):
                detail = ledger.draw_detail(_draw_no(path))
                if detail is None:
                    self._json({"error": "この回はまだ取り込まれていません"}, status=404)
                    return
                self._json(detail)
                return
            self._json({"error": "見つかりません"}, status=404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/shutdown":
                self._json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path == "/api/import-official":
                try:
                    self._json(importer.start(ledger))
                except ImportBusy as exc:
                    self._json({"error": str(exc)}, status=409)
                return
            if path != "/api/tickets":
                self._json({"error": "見つかりません"}, status=404)
                return
            self._save(None)

        def do_PUT(self) -> None:
            path = urlparse(self.path).path
            if not path.startswith("/api/tickets/"):
                self._json({"error": "見つかりません"}, status=404)
                return
            self._save(_ticket_id(path))

        def do_DELETE(self) -> None:
            path = urlparse(self.path).path
            if not path.startswith("/api/tickets/"):
                self._json({"error": "見つかりません"}, status=404)
                return
            try:
                ledger.delete_ticket(_ticket_id(path))
            except (LedgerError, ValueError) as exc:
                self._json({"error": str(exc)}, status=400)
                return
            self._json({"ok": True})

        def _save(self, ticket_id: int | None) -> None:
            try:
                payload = _read_json(self)
                if ticket_id is None:
                    saved = ledger.add_ticket(payload)
                else:
                    saved = ledger.update_ticket(ticket_id, payload)
            except LedgerError as exc:
                self._json({"error": str(exc)}, status=400)
                return
            except (json.JSONDecodeError, ValueError):
                self._json({"error": "送信内容を読めません"}, status=400)
                return
            self._json(saved)

        def _json(self, payload: object, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._bytes(status, body, "application/json; charset=utf-8")

        def _bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if content_type.startswith("text/html"):
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _history_search(ledger: Ledger, query: dict[str, list[str]]) -> dict:
    raw_values = query.get("n") or query.get("numbers") or []
    numbers: list[int] = []
    for item in raw_values:
        for part in str(item).replace(" ", "").split(","):
            if not part:
                continue
            try:
                numbers.append(int(part))
            except ValueError as exc:
                raise LedgerError("数字は1〜43の整数") from exc
    limit = _int_query(query, "limit", 40, 1, 200)
    offset = _int_query(query, "offset", 0, 0, 100000)
    return ledger.search_numbers(numbers, limit=limit, offset=offset)


def _analysis(ledger: Ledger, config: dict, query: dict[str, list[str]]) -> dict:
    years = _int_query(query, "years", int(config["lottery"]["years"]), 1, 30)
    start = years_ago(years)
    rows = ledger.load_draws(start_date=start)
    if not rows:
        return {"error": "分析できる当せんデータがありません", "meta": {"draw_count": 0}}
    result = analyze(rows, config)
    payload = to_payload(result)
    payload["meta"]["years"] = years
    return payload


def _int_query(query: dict[str, list[str]], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = query.get(key, [str(default)])[0]
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length > 20_000:
        raise ValueError("too large")
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("object required")
    return data


def _draw_no(path: str) -> int:
    return int(path.rstrip("/").split("/")[-1])


def _ticket_id(path: str) -> int:
    return int(path.rstrip("/").split("/")[-1])


if __name__ == "__main__":
    from loto6.config import abs_path, load_config

    # デスクトップ台帳は従来DBを維持
    raise SystemExit(run(abs_path(load_config(), "storage.legacy_sqlite_path")))
