"""過去出現頻度を重みにした本数字組み合わせ生成。"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

from loto6.storage import Store


FLOOR = 0.5
MAX_TICKETS = 20
MAX_UNIQUE_ATTEMPTS = 80


def generate_combos(
    store: Store,
    game: str,
    main_count: int,
    max_number: int,
    min_number: int = 1,
    tickets: int = 1,
    mode: str = "hot",
    recent_draws: int | None = None,
    recent_years: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    tickets = max(1, min(MAX_TICKETS, int(tickets)))
    if mode not in ("hot", "balanced"):
        mode = "hot"

    start_date = None
    if recent_years and recent_years > 0:
        from loto6.scrape import years_ago

        start_date = years_ago(recent_years)

    rows = store.load_draws(start_date=start_date, game=game, newest_first=True)
    if recent_draws and recent_draws > 0:
        rows = rows[:recent_draws]
    # 生成は古い順でもよいが頻度集計は集合で十分
    counts: Counter[int] = Counter()
    for row in rows:
        for i in range(1, main_count + 1):
            value = row[f"n{i}"]
            if value is not None:
                counts[int(value)] += 1

    universe = list(range(min_number, max_number + 1))
    raw_weights = []
    for number in universe:
        count = float(counts.get(number, 0))
        if mode == "balanced":
            # 偏りを弱める（平方根）
            weight = (count + FLOOR) ** 0.5
        else:
            weight = count + FLOOR
        raw_weights.append(weight)

    rng = random.Random(seed)
    combos: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    warnings: list[str] = []

    for _ in range(tickets):
        picked: list[int] | None = None
        for _attempt in range(MAX_UNIQUE_ATTEMPTS):
            candidate = _weighted_sample_without_replacement(universe, raw_weights, main_count, rng)
            key = tuple(sorted(candidate))
            if key not in seen:
                seen.add(key)
                picked = list(key)
                break
        if picked is None:
            # 打ち切り: 重複を許容
            picked = sorted(_weighted_sample_without_replacement(universe, raw_weights, main_count, rng))
            warnings.append("口どうしの重複を完全には避けられませんでした")
        combos.append(picked)

    ranked = sorted(
        [{"number": n, "count": int(counts.get(n, 0)), "weight": round(w, 3)} for n, w in zip(universe, raw_weights)],
        key=lambda item: (-item["count"], item["number"]),
    )
    return {
        "game": game,
        "tickets": tickets,
        "mode": mode,
        "main_count": main_count,
        "draw_count": len(rows),
        "period": {
            "start_date": start_date,
            "recent_draws": recent_draws,
            "recent_years": recent_years,
        },
        "combos": [{"index": i + 1, "numbers": combo} for i, combo in enumerate(combos)],
        "weights_summary": ranked[:10],
        "warnings": list(dict.fromkeys(warnings)),
        "disclaimer": (
            "過去の抽せん結果における出現回数などを重みにして、指定口数分の番号候補を機械的に作ります。"
            "抽せんは毎回独立であり、当せんを保証するものではありません。"
        ),
    }


def _weighted_sample_without_replacement(
    universe: list[int],
    weights: list[float],
    k: int,
    rng: random.Random,
) -> list[int]:
    pool = list(universe)
    pool_w = list(weights)
    chosen: list[int] = []
    for _ in range(k):
        total = sum(pool_w)
        if total <= 0:
            break
        pick = rng.random() * total
        cumulative = 0.0
        index = 0
        for index, weight in enumerate(pool_w):
            cumulative += weight
            if pick <= cumulative:
                break
        chosen.append(pool[index])
        del pool[index]
        del pool_w[index]
    return chosen
