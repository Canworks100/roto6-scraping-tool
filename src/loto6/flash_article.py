"""抽せん1回ぶんの速報記事。番号はDBの値だけを埋め、型で文章にする。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loto6.storage import Store, row_to_draw


def format_date(iso: str | None) -> str:
    if not iso:
        return "—"
    matched = str(iso)[:10].split("-")
    if len(matched) != 3:
        return str(iso)
    return f"{int(matched[0])}年{int(matched[1])}月{int(matched[2])}日"


def format_draw(draw_no: int) -> str:
    return f"第{draw_no:04d}回"


def format_yen(n: int | None) -> str:
    if n is None:
        return "—"
    return f"{n:,}円"


def format_count(n: int | None) -> str:
    if n is None:
        return "—"
    return f"{n:,}口"


def _article_cache(store: Store, game_def: dict[str, Any]) -> dict[str, Any]:
    game = str(game_def["id"])
    main_count = int(game_def["main_count"])
    return {
        "avg_sum": store.average_main_sum(game, main_count),
        "prize1_amounts": [
            int(row["amount"])
            for row in store.conn.execute(
                """
                SELECT prize1_amount AS amount
                FROM draws
                WHERE game=? AND prize1_amount IS NOT NULL AND prize1_amount > 0
                GROUP BY prize1_amount
                ORDER BY amount DESC
                """,
                (game,),
            )
        ],
    }


def refresh_articles(
    store: Store,
    game_def: dict[str, Any],
    draw_nos: list[int],
    *,
    cache: dict[str, Any] | None = None,
) -> int:
    if not draw_nos:
        return 0
    cache = cache or _article_cache(store, game_def)
    count = 0
    for draw_no in draw_nos:
        article = build_article(store, game_def, draw_no, cache=cache)
        if article is None:
            continue
        store.upsert_flash_article(article, commit=False)
        count += 1
    store.conn.commit()
    return count


def refresh_all_articles(store: Store, game_def: dict[str, Any]) -> int:
    game = str(game_def["id"])
    nos = sorted(store.existing_draw_nos(game))
    return refresh_articles(store, game_def, nos)


def ensure_missing_articles(store: Store, game_def: dict[str, Any]) -> int:
    """未生成の回だけ書き出す。"""
    return refresh_articles(store, game_def, store.missing_flash_draw_nos(str(game_def["id"])))


def article_or_build(store: Store, game_def: dict[str, Any], draw_no: int) -> dict[str, Any] | None:
    row = store.get_flash_article_row(str(game_def["id"]), draw_no)
    if row is not None:
        try:
            return json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            pass
    article = build_article(store, game_def, draw_no)
    if article is None:
        return None
    store.upsert_flash_article(article)
    return article


def list_articles(store: Store, game_def: dict[str, Any], limit: int, offset: int) -> dict[str, Any]:
    game = str(game_def["id"])
    total = store.count_draws(game)
    rows = store.load_draws(game=game, limit=limit, offset=offset, newest_first=True)
    cache: dict[str, Any] | None = None
    items = []
    dirty = False
    for row in rows:
        draw_no = int(row["draw_no"])
        stored = store.get_flash_article_row(game, draw_no)
        article = None
        if stored is not None:
            try:
                article = json.loads(stored["payload"])
            except (TypeError, json.JSONDecodeError):
                article = None
        if article is None:
            if cache is None:
                cache = _article_cache(store, game_def)
            article = build_article(store, game_def, draw_no, row=row, cache=cache)
            if article is None:
                continue
            store.upsert_flash_article(article, commit=False)
            dirty = True
        items.append(
            {
                "draw_no": article["draw_no"],
                "draw_date": article["draw_date"],
                "title": article["title"],
                "lead": article["lead"],
                "numbers": article["item"]["numbers"],
                "bonus": article["item"]["bonus"],
                "bonus2": article["item"]["bonus2"],
            }
        )
    if dirty:
        store.conn.commit()
    return {"game": game, "total": total, "limit": limit, "offset": offset, "items": items}


def build_article(
    store: Store,
    game_def: dict[str, Any],
    draw_no: int,
    row: Any | None = None,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    game = str(game_def["id"])
    label = str(game_def["label"])
    main_count = int(game_def["main_count"])
    max_number = int(game_def["max_number"])
    prize_grades = int(game_def["prize_grades"])
    if row is None:
        row = store.get_draw(game, draw_no)
    if row is None:
        return None
    item = row_to_draw(row, main_count)
    numbers = list(item["numbers"])
    prizes = {int(p["grade"]): p for p in item["prizes"]}
    prize1 = prizes.get(1, {})
    p1_count = prize1.get("count")
    p1_amount = prize1.get("amount")
    carry = item.get("carryover_amount")
    stage = str(item.get("result_stage") or "official")
    numbers_text = "・".join(f"{n:02d}" for n in numbers)

    if stage != "official":
        title = f"{label} {format_draw(draw_no)}　{numbers_text}"
    elif p1_count:
        title = f"{label} {format_draw(draw_no)}　1等 {format_count(int(p1_count))} {format_yen(p1_amount if p1_amount is None else int(p1_amount))}"
    else:
        title = f"{label} {format_draw(draw_no)}　1等なし"

    observations = _observations(
        store,
        game=game,
        main_count=main_count,
        max_number=max_number,
        draw_no=draw_no,
        numbers=numbers,
        p1_amount=None if p1_amount is None else int(p1_amount),
        cache=cache,
    )
    lead = _lead(
        label=label,
        draw_no=draw_no,
        draw_date=str(item["draw_date"]),
        numbers=numbers,
        bonus=int(item["bonus"]),
        bonus2=None if item.get("bonus2") is None else int(item["bonus2"]),
        p1_count=None if p1_count is None else int(p1_count),
        p1_amount=None if p1_amount is None else int(p1_amount),
        carry=None if carry is None else int(carry),
        observations=observations,
        stage=stage,
    )
    carry_text = _carry_text(
        p1_count=None if p1_count is None else int(p1_count),
        carry=None if carry is None else int(carry),
        stage=stage,
    )
    prev_no, next_no = store.neighbor_draw_nos(game, draw_no)
    return {
        "game": game,
        "label": label,
        "draw_no": draw_no,
        "draw_date": item["draw_date"],
        "title": title,
        "lead": lead,
        "carry_text": carry_text,
        "result_stage": stage,
        "observations": observations[:6],
        "prize_grades": prize_grades,
        "item": item,
        "prev_draw_no": prev_no,
        "next_draw_no": next_no,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _lead(
    *,
    label: str,
    draw_no: int,
    draw_date: str,
    numbers: list[int],
    bonus: int,
    bonus2: int | None,
    p1_count: int | None,
    p1_amount: int | None,
    carry: int | None,
    observations: list[str],
    stage: str = "official",
) -> str:
    parts = [f"{label}{format_draw(draw_no)}は{format_date(draw_date)}の抽せん。"]
    numbers_text = "・".join(f"{n:02d}" for n in numbers)
    if stage != "official":
        parts.append(f"本数字は{numbers_text}。")
        if bonus2 is None:
            parts.append(f"ボーナスは{bonus:02d}。")
        else:
            parts.append(f"ボーナスは{bonus:02d}と{bonus2:02d}。")
    elif p1_count:
        parts.append(f"1等は{format_count(p1_count)}、{format_yen(p1_amount)}。")
        if carry:
            parts.append(f"キャリーは{format_yen(carry)}。")
    else:
        parts.append("1等はなし。")
        if carry:
            parts.append(f"キャリーは{format_yen(carry)}。")
    extra = _lead_extra(observations)
    if extra:
        parts.append(extra)
    return "".join(parts)


def _lead_extra(observations: list[str]) -> str:
    for text in observations:
        if "連番" in text or "回ぶり" in text or "初めて" in text or "第" in text and "位" in text:
            return text
    return observations[0] if observations else ""


def _carry_text(*, p1_count: int | None, carry: int | None, stage: str = "official") -> str:
    if stage != "official":
        return ""
    if p1_count:
        if carry:
            return f"1等は{format_count(p1_count)}。キャリーは{format_yen(carry)}。"
        return f"1等は{format_count(p1_count)}。"
    if carry:
        return f"1等はなし。キャリーは{format_yen(carry)}。"
    return "1等はなし。"


def _observations(
    store: Store,
    *,
    game: str,
    main_count: int,
    max_number: int,
    draw_no: int,
    numbers: list[int],
    p1_amount: int | None,
    cache: dict[str, Any] | None = None,
) -> list[str]:
    lines: list[str] = []
    odd = sum(1 for n in numbers if n % 2)
    even = len(numbers) - odd
    lines.append(f"奇数{odd}個、偶数{even}個。")
    total = sum(numbers)
    avg = cache["avg_sum"] if cache and "avg_sum" in cache else store.average_main_sum(game, main_count)
    if avg is None:
        lines.append(f"本数字の合計は{total}。")
    elif total > avg * 1.08:
        lines.append(f"本数字の合計は{total}。これまでの平均（{avg:.0f}）より多め。")
    elif total < avg * 0.92:
        lines.append(f"本数字の合計は{total}。これまでの平均（{avg:.0f}）より少なめ。")
    else:
        lines.append(f"本数字の合計は{total}。平均（{avg:.0f}）のあたり。")

    runs = _consecutive_runs(numbers)
    if runs:
        shown = "、".join(f"{a:02d}–{b:02d}" for a, b in runs)
        lines.append(f"本数字に連番{shown}があった。")

    zone_text = _zone_text(numbers, max_number)
    if zone_text:
        lines.append(zone_text)

    droughts: list[tuple[int, int]] = []
    firsts: list[int] = []
    for number in numbers:
        last = store.last_main_hit(game, number, draw_no, main_count)
        if last is None:
            firsts.append(number)
            continue
        gap = draw_no - int(last["draw_no"])
        if gap >= 20:
            droughts.append((number, gap))
    droughts.sort(key=lambda pair: pair[1], reverse=True)
    if firsts:
        joined = "、".join(f"{n:02d}" for n in firsts)
        lines.append(f"{joined}はこの種目で初めての本数字。")
    for number, gap in droughts[:2]:
        lines.append(f"{number:02d}は{gap}回ぶり。")

    prev = store.previous_draw(game, draw_no)
    if prev is not None:
        prev_item = row_to_draw(prev, main_count)
        overlap = sorted(set(numbers) & set(prev_item["numbers"]))
        if overlap:
            joined = "、".join(f"{n:02d}" for n in overlap)
            lines.append(f"前回と{len(overlap)}個重なった（{joined}）。")
        else:
            lines.append("前回の本数字との重なりはなし。")

    if cache and "prize1_amounts" in cache:
        rank = None
        if p1_amount:
            try:
                rank = cache["prize1_amounts"].index(p1_amount) + 1
            except ValueError:
                rank = None
    else:
        rank = store.prize1_amount_rank(game, p1_amount)
    if rank is not None and rank <= 5 and p1_amount:
        lines.append(f"1等の金額はこれまでの第{rank}位。")
    return lines


def _consecutive_runs(numbers: list[int]) -> list[tuple[int, int]]:
    if len(numbers) < 2:
        return []
    ordered = sorted(numbers)
    runs: list[tuple[int, int]] = []
    start = prev = ordered[0]
    for number in ordered[1:]:
        if number == prev + 1:
            prev = number
            continue
        if prev > start:
            runs.append((start, prev))
        start = prev = number
    if prev > start:
        runs.append((start, prev))
    return runs


def _zone_text(numbers: list[int], max_number: int) -> str:
    buckets: dict[str, int] = {}
    for number in numbers:
        low = ((number - 1) // 10) * 10 + 1
        high = min(low + 9, max_number)
        key = f"{low}〜{high}"
        buckets[key] = buckets.get(key, 0) + 1
    parts = [f"{label}が{count}個" for label, count in buckets.items() if count]
    if not parts:
        return ""
    return "ゾーンは" + "、".join(parts) + "。"
