#!/usr/bin/env python3
"""楽天 lastresults の本数字が、既存 DB と一致するか確認する（ネット接続あり）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loto6.client import HttpClient  # noqa: E402
from loto6.config import abs_path, load_config  # noqa: E402
from loto6.games import get_game  # noqa: E402
from loto6.parser import parse_rakuten_lastresults  # noqa: E402
from loto6.storage import Store, row_to_draw  # noqa: E402


def main() -> int:
    config = load_config()
    config["_sqlite_path"] = abs_path(config, "storage.sqlite_path")
    primary = config.get("primary") or {}
    base = str(primary.get("base_url") or "https://takarakuji.rakuten.co.jp").rstrip("/")
    paths = primary.get("lastresults") or {}
    store = Store(config["_sqlite_path"])
    ok = fail = skip = 0
    try:
        for game, path in paths.items():
            g = get_game(config, game)
            site = {"base_url": base, "current_page": path, "user_agent": config["site"]["user_agent"]}
            client = HttpClient({**config, "site": site})
            try:
                status, body = client.get(path)
            finally:
                client.close()
            if status != 200 or not body:
                print(f"FAIL {game}: HTTP {status}")
                fail += 1
                continue
            draws = parse_rakuten_lastresults(
                body.decode("utf-8", errors="replace"),
                source_url=base + path,
                game=game,
                main_count=int(g["main_count"]),
                bonus_count=int(g["bonus_count"]),
                min_number=int(g["min_number"]),
                max_number=int(g["max_number"]),
            )
            for draw in draws:
                row = store.get_draw(game, draw.draw_no)
                if row is None:
                    print(f"SKIP {game} #{draw.draw_no}: DBに無し")
                    skip += 1
                    continue
                existing = row_to_draw(row, int(g["main_count"]))
                if existing["numbers"] == draw.numbers and existing.get("bonus") == draw.bonus:
                    print(f"OK   {game} #{draw.draw_no}")
                    ok += 1
                else:
                    print(
                        f"FAIL {game} #{draw.draw_no}: "
                        f"db={existing['numbers']}+{existing.get('bonus')} "
                        f"rakuten={draw.numbers}+{draw.bonus}"
                    )
                    fail += 1
    finally:
        store.close()
    print(f"結果: OK={ok} FAIL={fail} SKIP={skip}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
