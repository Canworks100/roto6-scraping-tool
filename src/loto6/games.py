"""種目定義の読み取り。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

GAME_IDS = ("loto6", "loto7", "miniloto")

# 通常の抽せん曜日（0=月 … 6=日）。祝日振替は扱わない。
DRAW_WEEKDAYS: dict[str, tuple[int, ...]] = {
    "loto6": (0, 3),
    "loto7": (4,),
    "miniloto": (1,),
}


def next_draw_date(game: str, last_draw_date: str) -> str:
    """直前の抽せん日の翌日から、次の通常抽せん日を返す（ISO日付）。"""
    start = date.fromisoformat(str(last_draw_date)[:10])
    weekdays = DRAW_WEEKDAYS.get(game)
    if not weekdays:
        raise ValueError(f"未知の種目です: {game}")
    for offset in range(1, 15):
        candidate = start + timedelta(days=offset)
        if candidate.weekday() in weekdays:
            return candidate.isoformat()
    raise ValueError("次の抽せん日を算出できません")


def game_ids(config: dict[str, Any]) -> list[str]:
    games = config.get("games") or {}
    return [gid for gid in GAME_IDS if gid in games]


def get_game(config: dict[str, Any], game: str) -> dict[str, Any]:
    games = config.get("games") or {}
    if game not in games:
        raise KeyError(f"未知の種目です: {game}")
    data = dict(games[game])
    data["id"] = game
    return data


def site_for_game(config: dict[str, Any], game: str) -> dict[str, Any]:
    """HttpClient / collect が使う site 辞書を種目付きで返す。"""
    base = dict(config.get("site") or {})
    g = get_game(config, game)
    base.update(
        {
            "_game": game,
            "current_page": g["current_page"],
            "summary_csv": g["summary_csv"],
            "draw_csv": g["draw_csv"],
            "detail_page": g.get("detail_page", ""),
            "static_backnumber": g.get("static_backnumber", ""),
            "static_html_last": int(g.get("static_html_last") or 0),
        }
    )
    return base


def public_game_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for gid in game_ids(config):
        g = get_game(config, gid)
        items.append(
            {
                "id": gid,
                "label": g["label"],
                "min_number": int(g["min_number"]),
                "max_number": int(g["max_number"]),
                "main_count": int(g["main_count"]),
                "bonus_count": int(g["bonus_count"]),
                "prize_grades": int(g["prize_grades"]),
                "ready": bool(g.get("ready", True)),
            }
        )
    return items
