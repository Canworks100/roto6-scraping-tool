"""公開ページのプレイヤーをブラウザで見て、結果ボードの数字を読む。

プレイリストのトークンは作らない。ブラウザが公開ページを開いたときの再生だけを使う。
フレームは読んだら捨てる。動画は保存しない。
"""

from __future__ import annotations

import io
import logging
import os
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image

from loto6.games import get_game
from loto6.live_board import BoardRead, read_result_board
from loto6.parser import Draw

logger = logging.getLogger("loto6")

JST = ZoneInfo("Asia/Tokyo")
LIVE_PAGE = "https://www.takarakuji-dream.jp/takarakuji/"
BACKNUMBER_PAGE = "https://www.takarakuji-dream.jp/takarakuji/backnumber"
CHROME_ENV = "LOTO_CHROME"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_SECTIONS = (("loto7", "loto7"), ("loto6", "loto6"), ("mini_loto", "miniloto"))
_CAPTION = {
    "loto6": r"ロト[6６]第(\d+)回",
    "loto7": r"ロト[7７]第(\d+)回",
    "miniloto": r"ミニロト第(\d+)回",
}
_SLUG = {"loto6": "loto6", "loto7": "loto7", "miniloto": "mini"}


def fetch_text(url: str, timeout: float = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_backnumber(html: str) -> dict[str, list[dict[str, Any]]]:
    """バックナンバー表の公開視聴リンク。新しい順。"""
    positions: list[tuple[int, str]] = []
    for section, game in _SECTIONS:
        index = html.find(f'id="{section}"')
        if index >= 0:
            positions.append((index, game))
    positions.sort()
    found: dict[str, list[dict[str, Any]]] = {game: [] for _, game in _SECTIONS}
    for index, (start, game) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(html)
        chunk = html[start:end]
        rows = re.findall(
            r"第(\d+)回</td>\s*<td>(\d{4})年(\d{1,2})月(\d{1,2})日</td>.*?"
            r'href="(https://api01-platform\.stream\.co\.jp/apiservice/plt3/[^"]+)"',
            chunk,
            flags=re.S,
        )
        for draw_no, year, month, day, url in rows:
            found[game].append(
                {
                    "draw_no": int(draw_no),
                    "draw_date": f"{int(year):04d}-{int(month):02d}-{int(day):02d}",
                    "url": url,
                }
            )
    return found


def parse_live_watch(html: str, game: str) -> tuple[str | None, int | None]:
    """ライブページの再生ボタンと、その種目の回号。"""
    url_match = re.search(
        r'href="(https://api01-platform\.stream\.co\.jp/apiservice/plt3/[^"]+)"',
        html,
    )
    draw_match = re.search(_CAPTION[game], html)
    url = url_match.group(1) if url_match else None
    draw_no = int(draw_match.group(1)) if draw_match else None
    return url, draw_no


def settle(readings: list[BoardRead], need: int, *, require_prizes: bool = False) -> BoardRead | None:
    """同じ読みが need 回以上あり、それが一つだけのとき採用する。"""
    if need < 2:
        raise ValueError("確認回数は2以上")
    pool = [item for item in readings if item.amounts is not None] if require_prizes else list(readings)

    def key(item: BoardRead) -> tuple:
        if require_prizes:
            return (item.numbers, item.bonuses, item.amounts, item.carryover)
        return (item.numbers, item.bonuses)

    counts: Counter[tuple] = Counter(key(item) for item in pool)
    winners = [item_key for item_key, count in counts.items() if count >= need]
    if len(winners) != 1:
        return None
    chosen = winners[0]
    for item in pool:
        if key(item) == chosen:
            return item
    return None


def _settings(config: dict[str, Any]) -> dict[str, Any]:
    live = config.get("live_read") or {}
    start = str(live.get("window_start") or "18:50")
    publish_at = str(live.get("publish_at") or "19:00")
    end = str(live.get("window_end") or "19:15")
    return {
        "publish": bool(live.get("publish")),
        "confirmations": int(live.get("confirmations") or 3),
        "interval_sec": int(live.get("interval_sec") or 5),
        "window_start": start,
        "publish_at": publish_at,
        "window_end": end,
    }


def _clock(hhmm: str, day: datetime) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":", 1))
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def run_live(config: dict[str, Any], game: str) -> int:
    """抽せん日は 18:50 から結果表を見て、19:00 に速報を出す。"""
    from loto6.notify import alert

    settings = _settings(config)
    now = datetime.now(JST)
    end = _clock(settings["window_end"], now)
    start = _clock(settings["window_start"], now)
    publish_at = _clock(settings["publish_at"], now)
    if now >= end:
        alert(f"中継の読み取りは締め時刻を過ぎています game={game}")
        return 0
    if now < start:
        time.sleep((start - now).total_seconds())

    game_def = get_game(config, game)
    watch_url, draw_no = _wait_for_draw(config, game, end)
    if watch_url is None or draw_no is None:
        alert(f"中継の視聴ページで当回を確認できませんでした game={game}")
        return 0

    readings = _sample_player(
        watch_url,
        game_def,
        until=end,
        interval_sec=settings["interval_sec"],
        seek_tail_sec=None,
        need=settings["confirmations"],
        require_prizes=True,
    )
    settled = settle(readings, settings["confirmations"], require_prizes=True)
    if settled is None or settled.amounts is None:
        alert(f"{settings['window_end']}までに結果表を確定できませんでした game={game} 第{draw_no}回")
        return 0
    logger.info(
        "[%s] 中継で確定 第%s回 本数字=%s ボーナス=%s 金額=%s キャリー=%s",
        game,
        draw_no,
        list(settled.numbers),
        list(settled.bonuses),
        list(settled.amounts),
        settled.carryover,
    )
    if not settings["publish"]:
        logger.info("[%s] 自動公開はオフです", game)
        return 0
    now = datetime.now(JST)
    if now < publish_at:
        time.sleep((publish_at - now).total_seconds())
    saved = _save_live(config, game, game_def, draw_no, settled, watch_url)
    if saved:
        logger.info("[%s] 中継の速報を公開しました 第%s回", game, draw_no)
    return 0


def _wait_for_draw(config: dict[str, Any], game: str, end: datetime) -> tuple[str | None, int | None]:
    from loto6.storage import Store

    store = Store(Path(config["_sqlite_path"]))
    try:
        while datetime.now(JST) < end:
            html = fetch_text(LIVE_PAGE)
            url, draw_no = parse_live_watch(html, game)
            latest = store.latest_draw(game)
            latest_no = int(latest["draw_no"]) if latest is not None else 0
            if url and draw_no is not None and draw_no == latest_no + 1:
                return url, draw_no
            logger.info("[%s] 当回の視聴リンク待ち ページの回=%s 最新=%s", game, draw_no, latest_no)
            time.sleep(30)
    finally:
        store.close()
    return None, None


def _save_live(
    config: dict[str, Any],
    game: str,
    game_def: dict[str, Any],
    draw_no: int,
    reading: BoardRead,
    source_url: str,
) -> bool:
    from loto6.flash_article import refresh_articles
    from loto6.publish import publish_from_config
    from loto6.storage import Store

    grades = int(game_def["prize_grades"])
    if reading.amounts is None or len(reading.amounts) != grades:
        logger.info("[%s] 第%s回は等級の金額が揃っていないので保存しません", game, draw_no)
        return False
    draw = Draw(
        draw_no=draw_no,
        draw_date=datetime.now(JST).date().isoformat(),
        numbers=list(reading.numbers),
        bonus=reading.bonuses[0],
        bonus2=reading.bonuses[1] if len(reading.bonuses) > 1 else None,
        prizes={grade: (None, reading.amounts[grade - 1]) for grade in range(1, grades + 1)},
        carryover_amount=reading.carryover,
        source_url=source_url,
        game=game,
    )
    store = Store(Path(config["_sqlite_path"]))
    try:
        latest = store.latest_draw(game)
        latest_no = int(latest["draw_no"]) if latest is not None else 0
        if draw_no != latest_no + 1:
            logger.info("[%s] 第%s回は次の回ではないので保存しません", game, draw_no)
            return False
        existing = store.get_draw(game, draw_no)
        if existing is not None:
            stage = existing["result_stage"] if "result_stage" in existing.keys() else "official"
            if stage == "official":
                return False
        if not store.save(draw, stage="live"):
            return False
        refresh_articles(store, game_def, [draw_no])
    finally:
        store.close()
    publish_from_config(config)
    return True


def score_game(config: dict[str, Any], game: str, limit: int = 3) -> list[dict[str, Any]]:
    """直近の公開録画を結果ボードで読み、楽天の番号と照合する。公開はしない。"""
    html = fetch_text(BACKNUMBER_PAGE)
    items = parse_backnumber(html).get(game, [])[:limit]
    expected = _rakuten_numbers(config, game, items)
    game_def = get_game(config, game)
    need = _settings(config)["confirmations"]
    results: list[dict[str, Any]] = []
    for item in items:
        readings = _sample_player(
            item["url"],
            game_def,
            until=None,
            interval_sec=2,
            seek_tail_sec=45,
        )
        settled = settle(readings, need)
        truth = expected.get(int(item["draw_no"]))
        ok = settled is not None and truth is not None and _same_reading(settled, truth)
        results.append(
            {
                "draw_no": int(item["draw_no"]),
                "draw_date": item["draw_date"],
                "ok": ok,
                "read": None if settled is None else {"numbers": list(settled.numbers), "bonuses": list(settled.bonuses)},
                "expected": None if truth is None else {"numbers": list(truth.numbers), "bonus": truth.bonus, "bonus2": truth.bonus2},
                "frames": len(readings),
            }
        )
        logger.info("[%s] 録画照合 第%s回 %s", game, item["draw_no"], "一致" if ok else "不一致")
    return results


def _same_reading(reading: BoardRead, draw: Draw) -> bool:
    bonuses = (draw.bonus,) if draw.bonus2 is None else (draw.bonus, draw.bonus2)
    return tuple(sorted(reading.numbers)) == tuple(sorted(draw.numbers)) and tuple(reading.bonuses) == tuple(bonuses)


def _rakuten_numbers(config: dict[str, Any], game: str, items: list[dict[str, Any]]) -> dict[int, Draw]:
    from loto6.parser import parse_rakuten_month_html
    from loto6.rakuten_collect import _client, _rakuten_cfg

    wanted = {int(item["draw_no"]) for item in items}
    months = sorted({str(item["draw_date"])[:7].replace("-", "") for item in items})
    game_def = get_game(config, game)
    cfg = _rakuten_cfg(config)
    found: dict[int, Draw] = {}
    for yyyymm in months:
        path = cfg["month_path"].format(slug=_SLUG[game], yyyymm=yyyymm)
        client = _client(config, path)
        try:
            status, body = client.get(path)
        finally:
            client.close()
        if status != 200 or not body:
            logger.info("[%s] 楽天月次なし %s", game, yyyymm)
            continue
        html = body.decode("utf-8", errors="replace")
        draws = parse_rakuten_month_html(
            html,
            source_url=cfg["base_url"] + path,
            game=game,
            main_count=int(game_def["main_count"]),
            bonus_count=int(game_def["bonus_count"]),
            min_number=int(game_def["min_number"]),
            max_number=int(game_def["max_number"]),
            prize_grades=int(game_def["prize_grades"]),
        )
        for draw in draws:
            if draw.draw_no in wanted:
                found[draw.draw_no] = draw
    return found


def _sample_player(
    url: str,
    game_def: dict[str, Any],
    *,
    until: datetime | None,
    interval_sec: int,
    seek_tail_sec: int | None,
    need: int | None = None,
    require_prizes: bool = False,
) -> list[BoardRead]:
    from playwright.sync_api import sync_playwright

    main_count = int(game_def["main_count"])
    bonus_count = int(game_def["bonus_count"])
    min_number = int(game_def["min_number"])
    max_number = int(game_def["max_number"])
    prize_grades = int(game_def["prize_grades"])
    readings: list[BoardRead] = []
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            video = _find_video(page)
            if video is None:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                video = _find_video(page)
            if video is None:
                logger.info("再生できませんでした")
                return []
            if seek_tail_sec is not None:
                readings.extend(
                    _sample_recording(
                        page,
                        video,
                        tail_sec=seek_tail_sec,
                        step_sec=interval_sec,
                        main_count=main_count,
                        bonus_count=bonus_count,
                        min_number=min_number,
                        max_number=max_number,
                        prize_grades=prize_grades,
                    )
                )
            else:
                video.evaluate("v => { v.muted = true; const p = v.play(); if (p && p.catch) p.catch(() => {}); }")
                while until is None or datetime.now(JST) < until:
                    readings.extend(
                        _read_shot(
                            video,
                            main_count=main_count,
                            bonus_count=bonus_count,
                            min_number=min_number,
                            max_number=max_number,
                            prize_grades=prize_grades,
                        )
                    )
                    if need is not None and settle(readings, need, require_prizes=require_prizes) is not None:
                        break
                    if until is not None and datetime.now(JST) >= until:
                        break
                    page.wait_for_timeout(interval_sec * 1000)
        finally:
            browser.close()
    return readings


def _sample_recording(page: Any, video: Any, *, tail_sec: int, step_sec: int, **kwargs: int) -> list[BoardRead]:
    duration = 0.0
    for _ in range(40):
        duration = float(video.evaluate("v => (isFinite(v.duration) ? v.duration : 0)") or 0)
        if duration > 1:
            break
        page.wait_for_timeout(300)
    if duration <= 1:
        logger.info("再生時間を取得できませんでした")
        return []
    readings: list[BoardRead] = []
    t = max(0.0, duration - tail_sec)
    while t < duration - 0.4:
        video.evaluate("(v, t) => { v.pause(); v.currentTime = t }", t)
        page.wait_for_timeout(900)
        readings.extend(_read_shot(video, **kwargs))
        t += step_sec
    return readings


def _read_shot(video: Any, **kwargs: int) -> list[BoardRead]:
    png = video.screenshot(type="png")
    try:
        image = Image.open(io.BytesIO(png))
        image.load()
        found = read_result_board(image, **kwargs)
    finally:
        del png
    if found is None:
        return []
    return [found]


def _find_video(page: Any) -> Any | None:
    deadline = time.time() + 20
    while time.time() < deadline:
        for frame in page.frames:
            loc = frame.locator("video")
            if loc.count():
                return loc.first
        page.wait_for_timeout(400)
    return None


def _launch(playwright: Any) -> Any:
    exe = os.environ.get(CHROME_ENV, "").strip()
    options: dict[str, Any] = {
        "headless": True,
        "args": ["--autoplay-policy=no-user-gesture-required", "--mute-audio", "--disable-dev-shm-usage"],
    }
    if exe:
        options["executable_path"] = exe
    return playwright.chromium.launch(**options)
