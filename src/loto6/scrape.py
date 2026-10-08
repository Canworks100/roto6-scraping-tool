"""収集の実行。失敗しても中断位置からやり直せる。"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from loto6.browser_client import BrowserClient
from loto6.client import FetchError, HttpClient
from loto6.games import get_game, site_for_game
from loto6.parser import (
    ParseError,
    discover_archive_links,
    draw_numbers_from_links,
    parse_draw_csv,
    parse_rakuten_lastresults,
    parse_static_backnumber_html,
    parse_summary_csv,
)
from loto6.storage import Store

logger = logging.getLogger("loto6")


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def years_ago(years: int, today: date | None = None) -> str:
    today = today or date.today()
    try:
        cutoff = today.replace(year=today.year - years)
    except ValueError:
        cutoff = today.replace(year=today.year - years, day=28)
    return cutoff.isoformat()


def _collector_source(config: dict[str, Any]) -> str:
    return str((config.get("collector") or {}).get("source") or "mizuho").strip().lower()


def collect(
    config: dict[str, Any],
    years: int | None = None,
    refresh: bool = False,
    all_history: bool = False,
    game: str = "loto6",
) -> dict[str, int]:
    if _collector_source(config) == "rakuten":
        from loto6.rakuten_collect import collect_rakuten_history

        if all_history or years is None or years <= 0:
            return collect_rakuten_history(config, game=game, refresh=refresh)
        # 年指定でも楽天は月次一覧を辿る（間隔は rate_limit）。部分取り込みは未対応のため全履歴相当。
        logger.info("[%s] collector.source=rakuten のため過去月次を取り込みます", game)
        return collect_rakuten_history(config, game=game, refresh=refresh)

    game_def = get_game(config, game)
    site = site_for_game(config, game)
    client_config = {**config, "site": site}
    client: BrowserClient | HttpClient = BrowserClient(client_config)
    store = Store(Path(config["_sqlite_path"]))
    if all_history or years is None or years <= 0:
        cutoff = "1990-01-01"
        logger.info("[%s] 第1回から最新回まで全件を対象にします", game)
    else:
        cutoff = years_ago(years)
        logger.info("[%s] 対象は %s 以降の抽せんです", game, cutoff)

    static_last = int(game_def.get("static_html_last") or 0)
    main_count = int(game_def["main_count"])
    bonus_count = int(game_def["bonus_count"])
    min_number = int(game_def["min_number"])
    max_number = int(game_def["max_number"])
    prize_grades = int(game_def["prize_grades"])
    inserted = skipped = absent = failed = 0
    exported = 0
    saved_nos: list[int] = []

    try:
        archive_draws = _crawl_archive(client, site)
        latest = _latest_draw_no(client, site, archive_draws)
        if latest is None:
            # 既存最大から前進探索
            existing_max = max(store.existing_draw_nos(game), default=0)
            latest = existing_max or None
        if latest is None:
            raise FetchError(f"{game}: 最新回を特定できませんでした")

        if all_history or years is None or years <= 0:
            start = 1
        else:
            start = _find_start_draw(client, site, latest, cutoff, game_def)
        logger.info("[%s] 取得範囲は第%s回から第%s回です", game, start, latest)

        existing = set() if refresh else store.existing_draw_nos(game)
        missing = store.known_missing(game)
        consecutive_failures = 0
        limit = int(config["rate_limit"]["max_consecutive_failures"])
        template = site["draw_csv"]
        static_template = site.get("static_backnumber") or ""

        if start <= static_last and static_template:
            html_stats = _collect_static_html(
                client=client,
                store=store,
                template=static_template,
                start=start,
                end=min(static_last, latest),
                cutoff=cutoff,
                existing=existing,
                refresh=refresh,
                game=game,
                game_def=game_def,
            )
            inserted += html_stats["inserted"]
            skipped += html_stats["skipped"]
            failed += html_stats["failed"]
            saved_nos.extend(html_stats.get("saved_nos") or [])
            existing = store.existing_draw_nos(game) if not refresh else existing

        csv_start = max(start, static_last + 1) if static_last else start
        for draw_no in range(csv_start, latest + 1):
            if draw_no in existing:
                skipped += 1
                continue
            if draw_no in missing and not refresh:
                skipped += 1
                continue
            path = template.format(draw=draw_no)
            try:
                status, body = client.get(path)
            except FetchError as exc:
                failed += 1
                consecutive_failures += 1
                logger.error("[%s] 第%s回を取得できません: %s", game, draw_no, exc)
                if consecutive_failures >= limit:
                    logger.error("連続失敗が %s 回に達したため中断します", limit)
                    break
                continue
            consecutive_failures = 0
            if status == 404 or not body:
                store.mark_missing(draw_no, "404", game=game)
                absent += 1
                logger.warning("[%s] 第%s回のCSVがありません", game, draw_no)
                continue
            try:
                draw = parse_draw_csv(
                    body,
                    source_url=client.url(path),
                    game=game,
                    main_count=main_count,
                    bonus_count=bonus_count,
                    min_number=min_number,
                    max_number=max_number,
                    prize_grades=prize_grades,
                )
            except ParseError as exc:
                failed += 1
                logger.error("[%s] 第%s回の解析に失敗しました: %s", game, draw_no, exc)
                continue
            if draw.draw_date < cutoff:
                skipped += 1
                continue
            if store.save(draw, refresh=refresh):
                inserted += 1
                saved_nos.append(draw_no)
                if inserted % 50 == 0:
                    logger.info("[%s] 進捗 新規%s件（最新保存: 第%s回）", game, inserted, draw_no)
            else:
                skipped += 1
        exported = store.export_csv(Path(config["_csv_path"]), game=game)
        if saved_nos:
            from loto6.flash_article import refresh_articles

            n = refresh_articles(store, game_def, sorted(set(saved_nos)))
            logger.info("[%s] 速報記事 %s件を自動生成", game, n)
    finally:
        store.close()
        client.close()

    logger.info(
        "[%s] 完了 新規%s 既存スキップ%s 欠番%s 失敗%s CSV%s行",
        game,
        inserted,
        skipped,
        absent,
        failed,
        exported,
    )
    return {"inserted": inserted, "skipped": skipped, "absent": absent, "failed": failed, "exported": exported}


def collect_latest(config: dict[str, Any], game: str = "loto6", lookback: int = 4) -> dict[str, int]:
    """番号が分かった時点で保存し、公式CSVが出ていれば金額も足して速報にする。"""
    if _collector_source(config) == "rakuten":
        from loto6.rakuten_collect import collect_rakuten_latest

        return collect_rakuten_latest(config, game=game, lookback=lookback)

    game_def = get_game(config, game)
    site = site_for_game(config, game)
    store = Store(Path(config["_sqlite_path"]))
    inserted = skipped = absent = failed = 0
    saved_nos: list[int] = []
    client: BrowserClient | HttpClient | None = None
    main_count = int(game_def["main_count"])
    bonus_count = int(game_def["bonus_count"])
    min_number = int(game_def["min_number"])
    max_number = int(game_def["max_number"])
    prize_grades = int(game_def["prize_grades"])
    template = site["draw_csv"]
    try:
        primary = _ingest_primary_numbers(config, game, store, lookback=lookback)
        inserted += primary["inserted"]
        skipped += primary["skipped"]
        failed += primary["failed"]
        saved_nos.extend(primary["saved_nos"])

        try:
            client = BrowserClient({**config, "site": site})
            latest = _latest_draw_no(client, site, [])
            existing_max = max(store.existing_draw_nos(game), default=0)
            if latest is None:
                latest = existing_max
            if latest:
                start = max(1, latest - lookback + 1)
                end = latest + 1
                logger.info("[%s] 公式取り込み 第%s回〜第%s回", game, start, end)
                for draw_no in range(start, end + 1):
                    path = template.format(draw=draw_no)
                    try:
                        status, body = client.get(path)
                    except FetchError as exc:
                        failed += 1
                        logger.error("[%s] 第%s回を取得できません: %s", game, draw_no, exc)
                        continue
                    if status == 404 or not body:
                        absent += 1
                        continue
                    try:
                        draw = parse_draw_csv(
                            body,
                            source_url=client.url(path),
                            game=game,
                            main_count=main_count,
                            bonus_count=bonus_count,
                            min_number=min_number,
                            max_number=max_number,
                            prize_grades=prize_grades,
                        )
                    except ParseError as exc:
                        failed += 1
                        logger.error("[%s] 第%s回の解析に失敗しました: %s", game, draw_no, exc)
                        continue
                    if store.save(draw, refresh=True, stage="official"):
                        inserted += 1
                        saved_nos.append(draw_no)
                        logger.info("[%s] 公式 第%s回を保存", game, draw_no)
                    else:
                        skipped += 1
                        saved_nos.append(draw_no)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] 公式取り込みに失敗: %s", game, exc)

        store.export_csv(Path(config["_csv_path"]), game=game)
        if saved_nos:
            from loto6.flash_article import refresh_articles

            n = refresh_articles(store, game_def, sorted(set(saved_nos)))
            logger.info("[%s] 速報記事 %s件を自動生成", game, n)
    finally:
        store.close()
        if client is not None:
            client.close()
    logger.info("[%s] 速報完了 新規/更新%s スキップ%s 欠番%s 失敗%s", game, inserted, skipped, absent, failed)
    return {"inserted": inserted, "skipped": skipped, "absent": absent, "failed": failed}


def _ingest_primary_numbers(
    config: dict[str, Any],
    game: str,
    store: Store,
    lookback: int = 4,
) -> dict[str, Any]:
    """抽せん後すぐ出る番号案内から、分かった回を保存する。"""
    inserted = skipped = failed = 0
    saved_nos: list[int] = []
    primary = config.get("primary") or {}
    paths = primary.get("lastresults") or {}
    path = paths.get(game)
    if not path or not primary.get("base_url"):
        return {"inserted": 0, "skipped": 0, "failed": 0, "saved_nos": []}
    game_def = get_game(config, game)
    site = {
        "base_url": str(primary["base_url"]).rstrip("/"),
        "current_page": path,
        "user_agent": config["site"]["user_agent"],
    }
    client = HttpClient({**config, "site": site})
    try:
        status, body = client.get(path)
    except FetchError as exc:
        logger.error("[%s] 番号案内を取得できません: %s", game, exc)
        client.close()
        return {"inserted": 0, "skipped": 0, "failed": 1, "saved_nos": []}
    client.close()
    if status != 200 or not body:
        logger.warning("[%s] 番号案内が空です status=%s", game, status)
        return {"inserted": 0, "skipped": 0, "failed": 1, "saved_nos": []}
    html = body.decode("utf-8", errors="replace")
    source = site["base_url"] + path
    try:
        draws = parse_rakuten_lastresults(
            html,
            source_url=source,
            game=game,
            main_count=int(game_def["main_count"]),
            bonus_count=int(game_def["bonus_count"]),
            min_number=int(game_def["min_number"]),
            max_number=int(game_def["max_number"]),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] 番号案内の解析に失敗: %s", game, exc)
        return {"inserted": 0, "skipped": 0, "failed": 1, "saved_nos": []}
    if not draws:
        logger.warning("[%s] 番号案内から回を読めませんでした", game)
        return {"inserted": 0, "skipped": 0, "failed": 0, "saved_nos": []}
    existing_max = max(store.existing_draw_nos(game), default=0)
    floor = max(1, existing_max - lookback + 1) if existing_max else 1
    for draw in draws:
        if draw.draw_no < floor:
            skipped += 1
            continue
        if store.save(draw, stage="numbers"):
            inserted += 1
            saved_nos.append(draw.draw_no)
            logger.info("[%s] 番号 第%s回を保存", game, draw.draw_no)
        else:
            skipped += 1
    return {"inserted": inserted, "skipped": skipped, "failed": failed, "saved_nos": saved_nos}


def import_raw(config: dict[str, Any], raw_dir: Path, refresh: bool = False, game: str = "loto6") -> dict[str, int]:
    store = Store(Path(config["_sqlite_path"]))
    game_def = get_game(config, game)
    site = site_for_game(config, game)
    template = site["draw_csv"]
    base = site["base_url"].rstrip("/")
    prefix = {"loto6": "A102", "loto7": "A103", "miniloto": "A101"}.get(game, "A102")
    files = sorted(set(raw_dir.glob("*.CSV")) | set(raw_dir.glob("*.csv")))
    inserted = skipped = failed = 0
    saved_nos: list[int] = []
    try:
        for path in files:
            try:
                stem = path.stem.upper().replace(prefix, "")
                draw_no = int(stem)
                source = base + template.format(draw=draw_no)
                draw = parse_draw_csv(
                    path.read_bytes(),
                    source_url=source,
                    game=game,
                    main_count=int(game_def["main_count"]),
                    bonus_count=int(game_def["bonus_count"]),
                    min_number=int(game_def["min_number"]),
                    max_number=int(game_def["max_number"]),
                    prize_grades=int(game_def["prize_grades"]),
                )
            except (ParseError, ValueError) as exc:
                failed += 1
                logger.error("読み飛ばしました %s: %s", path.name, exc)
                continue
            if store.save(draw, refresh=refresh):
                inserted += 1
                saved_nos.append(draw.draw_no)
            else:
                skipped += 1
        exported = store.export_csv(Path(config["_csv_path"]), game=game)
        if saved_nos:
            from loto6.flash_article import refresh_articles

            n = refresh_articles(store, game_def, saved_nos)
            logger.info("[%s] 速報記事 %s件を自動生成", game, n)
    finally:
        store.close()
    logger.info("[%s] 取り込み 新規%s 既存スキップ%s 失敗%s CSV%s行", game, inserted, skipped, failed, exported)
    return {"inserted": inserted, "skipped": skipped, "failed": failed, "exported": exported}


def _collect_static_html(
    client: BrowserClient | HttpClient,
    store: Store,
    template: str,
    start: int,
    end: int,
    cutoff: str,
    existing: set[int],
    refresh: bool,
    game: str,
    game_def: dict[str, Any],
) -> dict[str, Any]:
    inserted = skipped = failed = 0
    saved_nos: list[int] = []
    page_starts = list(range(((start - 1) // 20) * 20 + 1, end + 1, 20))
    for page_start in page_starts:
        needed = [
            draw_no
            for draw_no in range(page_start, min(page_start + 20, end + 1))
            if refresh or draw_no not in existing
        ]
        if not needed:
            skipped += min(20, end - page_start + 1)
            continue
        path = template.format(start=page_start)
        try:
            status, body = client.get(path)
        except FetchError as exc:
            failed += len(needed)
            logger.error("静的HTML %s を取得できません: %s", path, exc)
            continue
        if status != 200 or not body:
            failed += len(needed)
            logger.error("静的HTML %s が空です status=%s", path, status)
            continue
        try:
            draws = parse_static_backnumber_html(
                body.decode("utf-8", errors="replace"),
                source_url=client.url(path),
                game=game,
                main_count=int(game_def["main_count"]),
                bonus_count=int(game_def["bonus_count"]),
                min_number=int(game_def["min_number"]),
                max_number=int(game_def["max_number"]),
            )
        except Exception as exc:  # noqa: BLE001
            failed += len(needed)
            logger.error("静的HTML %s の解析に失敗: %s", path, exc)
            continue
        by_no = {draw.draw_no: draw for draw in draws}
        for draw_no in needed:
            draw = by_no.get(draw_no)
            if draw is None:
                failed += 1
                logger.error("静的HTMLに第%s回がありません", draw_no)
                continue
            if draw.draw_date < cutoff:
                skipped += 1
                continue
            if store.save(draw, refresh=refresh):
                inserted += 1
                saved_nos.append(draw.draw_no)
            else:
                skipped += 1
        logger.info("[%s] 静的HTML 第%s〜処理（新規累計 %s）", game, page_start, inserted)
    return {"inserted": inserted, "skipped": skipped, "failed": failed, "saved_nos": saved_nos}


def _crawl_archive(client: BrowserClient | HttpClient, site: dict[str, Any]) -> list[int]:
    path = site["backnumber_index"]
    try:
        status, body = client.get(path)
    except FetchError as exc:
        logger.warning("アーカイブ索引を取得できません: %s", exc)
        return []
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", errors="replace")
    # site に game id が無い場合は loto6
    game = str(site.get("_game") or "loto6")
    links = discover_archive_links(html, site["base_url"], game=game)
    draws = draw_numbers_from_links(links, game=game)
    logger.info("アーカイブ索引からリンク %s 件、回号 %s 件", len(links), len(draws))
    return draws


def _latest_draw_no(client: BrowserClient | HttpClient, site: dict[str, Any], archive_draws: list[int]) -> int | None:
    try:
        status, body = client.get(site["summary_csv"])
    except FetchError as exc:
        logger.warning("直近一覧CSVを取得できません: %s", exc)
        return max(archive_draws) if archive_draws else None
    if status != 200 or not body:
        return max(archive_draws) if archive_draws else None
    summary = parse_summary_csv(body)
    if not summary:
        return max(archive_draws) if archive_draws else None
    latest = max(draw_no for draw_no, _date in summary)
    logger.info("直近一覧の最新は第%s回です", latest)
    return latest


def _find_start_draw(
    client: BrowserClient | HttpClient,
    site: dict[str, Any],
    latest: int,
    cutoff: str,
    game_def: dict[str, Any],
) -> int:
    template = site["draw_csv"]
    static_last = int(game_def.get("static_html_last") or 0)
    low = static_last + 1
    high = latest
    start = latest
    while low <= high:
        mid = (low + high) // 2
        draw_date = _probe_date(client, template, mid, game_def)
        if draw_date is None:
            low = mid + 1
            continue
        if draw_date >= cutoff:
            start = mid
            high = mid - 1
        else:
            low = mid + 1
    return start


def _probe_date(
    client: BrowserClient | HttpClient,
    template: str,
    draw_no: int,
    game_def: dict[str, Any],
) -> str | None:
    path = template.format(draw=draw_no)
    try:
        status, body = client.get(path)
    except FetchError:
        return None
    if status != 200 or not body:
        return None
    try:
        return parse_draw_csv(
            body,
            source_url=path,
            game=str(game_def.get("id") or "loto6"),
            main_count=int(game_def["main_count"]),
            bonus_count=int(game_def["bonus_count"]),
            min_number=int(game_def["min_number"]),
            max_number=int(game_def["max_number"]),
            prize_grades=int(game_def["prize_grades"]),
        ).draw_date
    except ParseError as exc:
        logger.error("第%s回の日付を読めません: %s", draw_no, exc)
        return None
