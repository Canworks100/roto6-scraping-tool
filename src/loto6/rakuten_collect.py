"""楽天×宝くじを入手先とする収集。みずほ用 BrowserClient は使わない。"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from loto6.client import FetchError, HttpClient
from loto6.games import get_game
from loto6.parser import Draw, parse_rakuten_lastresults, parse_rakuten_month_html
from loto6.storage import Store, _same_numbers

logger = logging.getLogger("loto6")

SLUG = {"loto6": "loto6", "loto7": "loto7", "miniloto": "mini"}
_live_mismatch_sent: set[tuple[str, int]] = set()


def _note_live_mismatch(store: Store, game: str, draw: Draw) -> None:
    """中継（live）と楽天の番号が違うときだけ、上書き前に一度通知する。"""
    existing = store.get_draw(game, draw.draw_no)
    if existing is None:
        return
    stage = existing["result_stage"] if "result_stage" in existing.keys() else "official"
    if stage != "live":
        return
    if _same_numbers(existing, draw):
        logger.info("[%s] 中継の番号は楽天と一致 第%s回", game, draw.draw_no)
        return
    key = (game, int(draw.draw_no))
    if key in _live_mismatch_sent:
        return
    _live_mismatch_sent.add(key)
    from loto6.notify import alert

    alert(f"中継と楽天の番号が違います。{game} 第{draw.draw_no}回を楽天の値で上書きします。")


def _rakuten_cfg(config: dict[str, Any]) -> dict[str, Any]:
    primary = config.get("primary") or {}
    rakuten = config.get("rakuten") or {}
    base = str(rakuten.get("base_url") or primary.get("base_url") or "https://takarakuji.rakuten.co.jp").rstrip("/")
    return {
        "base_url": base,
        "lastresults": dict(rakuten.get("lastresults") or primary.get("lastresults") or {}),
        "user_agent": str(
            (rakuten.get("user_agent") or (config.get("site") or {}).get("user_agent") or "LotoAnalyticsCollector/1.0")
        ),
        "past_path": str(rakuten.get("past_path") or "/backnumber/{slug}_past/"),
        "month_path": str(rakuten.get("month_path") or "/backnumber/{slug}/{yyyymm}/"),
    }


def _client(config: dict[str, Any], path: str) -> HttpClient:
    r = _rakuten_cfg(config)
    site = {
        "base_url": r["base_url"],
        "current_page": path,
        "user_agent": r["user_agent"],
    }
    return HttpClient({**config, "site": site})


def collect_rakuten_latest(config: dict[str, Any], game: str = "loto6", lookback: int = 4) -> dict[str, int]:
    """直近番号（lastresults）＋当月の月次ページで金額を足す。販売実績は null。"""
    game_def = get_game(config, game)
    store = Store(Path(config["_sqlite_path"]))
    inserted = skipped = absent = failed = 0
    changed = 0
    saved_nos: list[int] = []
    try:
        primary = _ingest_lastresults(config, game, store, lookback=lookback)
        inserted += primary["inserted"]
        skipped += primary["skipped"]
        failed += primary["failed"]
        changed += primary["changed"]
        saved_nos.extend(primary["saved_nos"])

        months = _recent_month_keys(store, game, extra=1)
        for yyyymm in months:
            try:
                result = _ingest_month(config, game, store, yyyymm, refresh=True)
                saved_nos.extend(result["saved_nos"])
                changed += result["changed"]
                inserted += result["changed"]
            except FetchError as exc:
                failed += 1
                logger.error("[%s] 月次 %s 取得失敗: %s", game, yyyymm, exc)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error("[%s] 月次 %s 解析失敗: %s", game, yyyymm, exc)

        if saved_nos:
            from loto6.flash_article import refresh_articles

            n = refresh_articles(store, game_def, sorted(set(saved_nos)))
            logger.info("[%s] 速報記事 %s件を自動生成", game, n)
        store.export_csv(Path(config["_csv_path"]), game=game)
    finally:
        store.close()
    logger.info(
        "[%s] 楽天速報 変更%s スキップ%s 失敗%s",
        game,
        changed,
        skipped,
        failed,
    )
    return {
        "inserted": inserted,
        "skipped": skipped,
        "absent": absent,
        "failed": failed,
        "changed": changed,
    }


def collect_rakuten_history(
    config: dict[str, Any],
    game: str = "loto6",
    *,
    refresh: bool = False,
) -> dict[str, int]:
    """過去索引の月次URLを順に取る（初回用）。間隔は HttpClient の rate_limit に従う。"""
    game_def = get_game(config, game)
    store = Store(Path(config["_sqlite_path"]))
    inserted = skipped = failed = 0
    changed = 0
    saved_nos: list[int] = []
    try:
        months = _list_month_paths(config, game)
        logger.info("[%s] 楽天 月次 %s 件を取り込みます", game, len(months))
        existing = set() if refresh else store.existing_draw_nos(game)
        for yyyymm in months:
            try:
                result = _ingest_month(
                    config,
                    game,
                    store,
                    yyyymm,
                    refresh=refresh,
                    skip_existing=existing,
                )
                for n in result["saved_nos"]:
                    if n in existing and not refresh:
                        skipped += 1
                    else:
                        inserted += 1
                        saved_nos.append(n)
                        existing.add(n)
                changed += result["changed"]
            except FetchError as exc:
                failed += 1
                logger.error("[%s] 月次 %s: %s", game, yyyymm, exc)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error("[%s] 月次 %s 解析: %s", game, yyyymm, exc)
        if saved_nos:
            from loto6.flash_article import refresh_articles

            n = refresh_articles(store, game_def, sorted(set(saved_nos)))
            logger.info("[%s] 速報記事 %s件を自動生成", game, n)
        store.export_csv(Path(config["_csv_path"]), game=game)
    finally:
        store.close()
    logger.info("[%s] 楽天過去 保存相当%s スキップ%s 失敗%s", game, inserted, skipped, failed)
    return {
        "inserted": inserted,
        "skipped": skipped,
        "absent": 0,
        "failed": failed,
        "changed": changed,
    }


def backfill_missing_prizes(config: dict[str, Any], game: str = "loto6") -> dict[str, int]:
    """金額が欠けている回だけ、対象月の月次ページを再取得して埋める（1回きりの補完用）。"""
    game_def = get_game(config, game)
    store = Store(Path(config["_sqlite_path"]))
    filled = still_missing = failed = 0
    saved_nos: list[int] = []
    try:
        before_rows = store.draws_missing_prizes(game)
        before = {int(r["draw_no"]) for r in before_rows}
        if not before:
            logger.info("[%s] 金額欠けなし", game)
            return {"filled": 0, "still_missing": 0, "failed": 0, "months": 0, "changed": 0}

        months = sorted(
            {
                str(r["draw_date"])[:7].replace("-", "")
                for r in before_rows
                if r["draw_date"] and len(str(r["draw_date"])) >= 7
            }
        )
        logger.info("[%s] 金額補完: 欠け %s 回 / 月次 %s 件", game, len(before), len(months))
        for yyyymm in months:
            try:
                result = _ingest_month(config, game, store, yyyymm, refresh=True)
                saved_nos.extend(result["saved_nos"])
            except FetchError as exc:
                failed += 1
                logger.error("[%s] 補完 月次 %s: %s", game, yyyymm, exc)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error("[%s] 補完 月次 %s 解析: %s", game, yyyymm, exc)

        after = {int(r["draw_no"]) for r in store.draws_missing_prizes(game)}
        filled = len(before - after)
        still_missing = len(after)
        if saved_nos:
            from loto6.flash_article import refresh_articles

            refresh_articles(store, game_def, sorted(set(saved_nos) & before))
        store.export_csv(Path(config["_csv_path"]), game=game)
        logger.info("[%s] 金額補完 埋まった%s / 残null%s / 失敗%s", game, filled, still_missing, failed)
        return {
            "filled": filled,
            "still_missing": still_missing,
            "failed": failed,
            "months": len(months),
            "changed": filled,
        }
    finally:
        store.close()


def check_draw_night_numbers(config: dict[str, Any], game: str) -> bool:
    """抽せん日なのに当日の番号が DB に無いとき False。非抽せん日は True。"""
    today = date.today()
    # Mon=0 ... Sun=6 / ロト6=月木, ロト7=金, ミニロト=火
    draw_weekdays = {"loto6": {0, 3}, "loto7": {4}, "miniloto": {1}}
    if today.weekday() not in draw_weekdays.get(game, set()):
        return True

    store = Store(Path(config["_sqlite_path"]))
    try:
        row = store.latest_draw(game)
        if row is None:
            return False
        return str(row["draw_date"])[:10] == today.isoformat()
    finally:
        store.close()


def _ingest_lastresults(
    config: dict[str, Any],
    game: str,
    store: Store,
    lookback: int = 4,
) -> dict[str, Any]:
    r = _rakuten_cfg(config)
    path = r["lastresults"].get(game)
    if not path:
        return {"inserted": 0, "skipped": 0, "failed": 0, "changed": 0, "saved_nos": []}
    game_def = get_game(config, game)
    client = _client(config, path)
    try:
        status, body = client.get(path)
    except FetchError as exc:
        logger.error("[%s] lastresults 取得失敗: %s", game, exc)
        client.close()
        return {"inserted": 0, "skipped": 0, "failed": 1, "changed": 0, "saved_nos": []}
    client.close()
    if status != 200 or not body:
        return {"inserted": 0, "skipped": 0, "failed": 1, "changed": 0, "saved_nos": []}
    html = body.decode("utf-8", errors="replace")
    source = r["base_url"] + path
    draws = parse_rakuten_lastresults(
        html,
        source_url=source,
        game=game,
        main_count=int(game_def["main_count"]),
        bonus_count=int(game_def["bonus_count"]),
        min_number=int(game_def["min_number"]),
        max_number=int(game_def["max_number"]),
    )
    inserted = skipped = changed = 0
    saved_nos: list[int] = []
    existing_max = max(store.existing_draw_nos(game), default=0)
    floor = max(1, existing_max - lookback + 1) if existing_max else 1
    for draw in draws:
        if draw.draw_no < floor:
            skipped += 1
            continue
        _note_live_mismatch(store, game, draw)
        if store.save(draw, stage="numbers"):
            inserted += 1
            changed += 1
            saved_nos.append(draw.draw_no)
            logger.info("[%s] 番号 第%s回を保存", game, draw.draw_no)
        else:
            skipped += 1
            saved_nos.append(draw.draw_no)
    return {
        "inserted": inserted,
        "skipped": skipped,
        "failed": 0,
        "changed": changed,
        "saved_nos": saved_nos,
    }


def _ingest_month(
    config: dict[str, Any],
    game: str,
    store: Store,
    yyyymm: str,
    *,
    refresh: bool = False,
    skip_existing: set[int] | None = None,
) -> dict[str, Any]:
    r = _rakuten_cfg(config)
    slug = SLUG[game]
    path = r["month_path"].format(slug=slug, yyyymm=yyyymm)
    game_def = get_game(config, game)
    client = _client(config, path)
    try:
        status, body = client.get(path)
    finally:
        client.close()
    if status == 404 or not body:
        logger.info("[%s] 月次なし %s", game, yyyymm)
        return {"saved_nos": [], "changed": 0}
    if status != 200:
        raise FetchError(f"HTTP {status} {path}")
    html = body.decode("utf-8", errors="replace")
    source = urljoin(r["base_url"] + "/", path.lstrip("/"))
    draws = parse_rakuten_month_html(
        html,
        source_url=source,
        game=game,
        main_count=int(game_def["main_count"]),
        bonus_count=int(game_def["bonus_count"]),
        min_number=int(game_def["min_number"]),
        max_number=int(game_def["max_number"]),
        prize_grades=int(game_def["prize_grades"]),
    )
    saved: list[int] = []
    changed = 0
    for draw in draws:
        if skip_existing is not None and draw.draw_no in skip_existing and not refresh:
            continue
        _note_live_mismatch(store, game, draw)
        if store.save(draw, refresh=refresh, stage="official"):
            changed += 1
            saved.append(draw.draw_no)
            logger.info("[%s] 公式相当 第%s回を保存", game, draw.draw_no)
        else:
            saved.append(draw.draw_no)
    return {"saved_nos": saved, "changed": changed}


def _recent_month_keys(store: Store, game: str, extra: int = 1) -> list[str]:
    """DBの最新抽せん月から、当月・前月など。"""
    row = store.latest_draw(game)
    today = date.today()
    keys: list[str] = [f"{today.year:04d}{today.month:02d}"]
    if row is not None and row["draw_date"]:
        d = str(row["draw_date"])[:10]
        y, m, _ = d.split("-")
        keys.append(f"{int(y):04d}{int(m):02d}")
    # 前月
    y, m = today.year, today.month - 1
    if m <= 0:
        y, m = y - 1, 12
    keys.append(f"{y:04d}{m:02d}")
    out: list[str] = []
    for k in keys:
        if k not in out:
            out.append(k)
    return out[: 2 + extra]


def _list_month_paths(config: dict[str, Any], game: str) -> list[str]:
    r = _rakuten_cfg(config)
    slug = SLUG[game]
    past = r["past_path"].format(slug=slug)
    client = _client(config, past)
    try:
        status, body = client.get(past)
    finally:
        client.close()
    if status != 200 or not body:
        raise FetchError(f"過去索引を取得できません: {past}")
    html = body.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    months: list[str] = []
    pattern = re.compile(rf"/backnumber/{re.escape(slug)}/(\d{{6}})/")
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        matched = pattern.search(href)
        if matched:
            months.append(matched.group(1))
    return sorted(set(months))
