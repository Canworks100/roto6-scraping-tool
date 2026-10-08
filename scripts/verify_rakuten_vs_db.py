#!/usr/bin/env python3
"""楽天 lastresults / 直近月次の番号・金額が、既存 DB と一致するか確認する（ネット接続あり）。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loto6.client import HttpClient  # noqa: E402
from loto6.config import abs_path, load_config  # noqa: E402
from loto6.games import get_game  # noqa: E402
from loto6.parser import parse_rakuten_lastresults, parse_rakuten_month_html  # noqa: E402
from loto6.rakuten_collect import SLUG, _rakuten_cfg  # noqa: E402
from loto6.storage import Store, row_to_draw  # noqa: E402


def _client(config: dict, base: str, path: str, ua: str) -> HttpClient:
    site = {"base_url": base, "current_page": path, "user_agent": ua}
    return HttpClient({**config, "site": site})


def main() -> int:
    config = load_config()
    config["_sqlite_path"] = abs_path(config, "storage.sqlite_path")
    r = _rakuten_cfg(config)
    base = r["base_url"]
    store = Store(config["_sqlite_path"])
    ok = fail = skip = 0
    try:
        for game, path in (r["lastresults"] or {}).items():
            g = get_game(config, game)
            client = _client(config, base, path, r["user_agent"])
            try:
                status, body = client.get(path)
            finally:
                client.close()
            if status != 200 or not body:
                print(f"FAIL {game}: lastresults HTTP {status}")
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
            for draw in draws[:4]:
                row = store.get_draw(game, draw.draw_no)
                if row is None:
                    print(f"SKIP {game} #{draw.draw_no}: DBに無し")
                    skip += 1
                    continue
                existing = row_to_draw(row, int(g["main_count"]))
                if existing["numbers"] == draw.numbers and existing.get("bonus") == draw.bonus:
                    print(f"OK   {game} #{draw.draw_no} numbers")
                    ok += 1
                else:
                    print(
                        f"FAIL {game} #{draw.draw_no}: "
                        f"db={existing['numbers']}+{existing.get('bonus')} "
                        f"rakuten={draw.numbers}+{draw.bonus}"
                    )
                    fail += 1

            # 当月の月次で金額照合
            today = date.today()
            yyyymm = f"{today.year:04d}{today.month:02d}"
            month_path = r["month_path"].format(slug=SLUG[game], yyyymm=yyyymm)
            client = _client(config, base, month_path, r["user_agent"])
            try:
                status, body = client.get(month_path)
            finally:
                client.close()
            if status != 200 or not body:
                print(f"SKIP {game}: month {yyyymm} HTTP {status}")
                skip += 1
                continue
            month_draws = parse_rakuten_month_html(
                body.decode("utf-8", errors="replace"),
                source_url=base + month_path,
                game=game,
                main_count=int(g["main_count"]),
                bonus_count=int(g["bonus_count"]),
                min_number=int(g["min_number"]),
                max_number=int(g["max_number"]),
                prize_grades=int(g["prize_grades"]),
            )
            for draw in month_draws[-3:]:
                row = store.get_draw(game, draw.draw_no)
                if row is None:
                    print(f"SKIP {game} #{draw.draw_no}: month DBに無し")
                    skip += 1
                    continue
                existing = row_to_draw(row, int(g["main_count"]))
                db_p1 = None
                for p in existing.get("prizes") or []:
                    if int(p.get("grade") or 0) == 1:
                        db_p1 = p.get("amount")
                        break
                rk_p1 = draw.prizes.get(1, (None, None))[1]
                db_co = existing.get("carryover_amount")
                rk_co = draw.carryover_amount
                nums_ok = existing["numbers"] == draw.numbers
                prize_ok = db_p1 == rk_p1 and db_co == rk_co
                if nums_ok and prize_ok:
                    print(f"OK   {game} #{draw.draw_no} month prizes p1={rk_p1} co={rk_co}")
                    ok += 1
                elif not nums_ok:
                    print(f"FAIL {game} #{draw.draw_no} month numbers mismatch")
                    fail += 1
                else:
                    # DB 側がまだ null のときは SKIP（補完前）
                    if db_p1 is None and rk_p1 is not None:
                        print(f"SKIP {game} #{draw.draw_no}: DB金額未反映 p1={rk_p1}")
                        skip += 1
                    else:
                        print(
                            f"FAIL {game} #{draw.draw_no} prizes "
                            f"db_p1={db_p1} rk_p1={rk_p1} db_co={db_co} rk_co={rk_co}"
                        )
                        fail += 1
    finally:
        store.close()
    print(f"結果: OK={ok} FAIL={fail} SKIP={skip}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
