"""種目定義の読み取り。"""

from __future__ import annotations

from typing import Any

GAME_IDS = ("loto6", "loto7", "miniloto")


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
