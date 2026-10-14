"""ロト購入シミュレーター（疑似抽せん・理論配当）。"""

from __future__ import annotations

import random
from typing import Any

from loto6.analyze import ticket_grade

DETAIL_THRESHOLD = 50
MAX_HAND_TICKETS = 500
YEN_CAP = 200_000_000


class SimuError(ValueError):
    """入力がシミュレーターの前提を満たさない。"""


def unit_price_for(game_def: dict[str, Any]) -> int:
    return int(game_def.get("unit_price") or 200)


def max_tickets_for(game_def: dict[str, Any]) -> int:
    price = unit_price_for(game_def)
    return max(1, YEN_CAP // price)


def _pick_unique(rng: random.Random, pool: list[int], count: int) -> list[int]:
    return sorted(rng.sample(pool, count))


def draw_winning(
    game_def: dict[str, Any],
    rng: random.Random | None = None,
) -> tuple[list[int], list[int]]:
    rng = rng or random.Random()
    min_n = int(game_def["min_number"])
    max_n = int(game_def["max_number"])
    main_count = int(game_def["main_count"])
    bonus_count = int(game_def["bonus_count"])
    pool = list(range(min_n, max_n + 1))
    mains = _pick_unique(rng, pool, main_count)
    remain = [n for n in pool if n not in mains]
    bonuses = _pick_unique(rng, remain, bonus_count)
    return mains, bonuses


def _normalize_ticket(
    numbers: list[int],
    *,
    main_count: int,
    min_n: int,
    max_n: int,
) -> list[int]:
    cleaned: list[int] = []
    seen: set[int] = set()
    for value in numbers:
        n = int(value)
        if n < min_n or n > max_n:
            raise SimuError(f"数字は{min_n}〜{max_n}の整数です")
        if n in seen:
            raise SimuError("同じ数字は1口に1回だけです")
        seen.add(n)
        cleaned.append(n)
    if len(cleaned) != main_count:
        raise SimuError(f"本数字は{main_count}個選んでください")
    return sorted(cleaned)


def _grade_amount(
    grade: int,
    *,
    grade1_pool: int,
    grade1_winners: int,
    fixed: dict[int, int],
) -> int:
    if grade == 1:
        if grade1_winners <= 0:
            return 0
        return grade1_pool // grade1_winners
    return int(fixed.get(grade) or 0)


def run_simu(
    game_def: dict[str, Any],
    *,
    tickets: list[list[int]],
    random_count: int,
    carryover_amount: int | None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """疑似抽せんを1回行い、収支と明細を返す。"""
    rng = rng or random.Random()
    game = str(game_def.get("id") or "")
    min_n = int(game_def["min_number"])
    max_n = int(game_def["max_number"])
    main_count = int(game_def["main_count"])
    unit_price = unit_price_for(game_def)
    max_tickets = max_tickets_for(game_def)
    grade1_base = int(game_def.get("simu_grade1_base") or 0)
    fixed_raw = game_def.get("simu_prizes") or {}
    fixed = {int(k): int(v) for k, v in fixed_raw.items()}

    if random_count < 0:
        raise SimuError("ランダム口数は0以上です")
    if len(tickets) > MAX_HAND_TICKETS:
        raise SimuError(f"手選びは{MAX_HAND_TICKETS}口までです")

    hand: list[list[int]] = []
    for row in tickets:
        hand.append(_normalize_ticket(row, main_count=main_count, min_n=min_n, max_n=max_n))

    total_count = len(hand) + int(random_count)
    if total_count < 1:
        raise SimuError("1口以上指定してください")
    if total_count > max_tickets:
        raise SimuError("口数が多すぎて処理できません。口数を減らして再度お試しください。")

    win_mains, win_bonuses = draw_winning(game_def, rng)
    main_set = set(win_mains)
    bonus_set = set(win_bonuses)
    pool = list(range(min_n, max_n + 1))
    winners_only = total_count > DETAIL_THRESHOLD

    # 1パス目: 等級件数だけ数える（1等按分のため）
    by_grade_counts: dict[int, int] = {}
    hand_grades: list[tuple[list[int], int | None, int, bool]] = []
    for numbers in hand:
        grade, matched, bonus_hit = ticket_grade(set(numbers), main_set, bonus_set, main_count)
        hand_grades.append((numbers, grade, matched, bonus_hit))
        if grade is not None:
            by_grade_counts[int(grade)] = by_grade_counts.get(int(grade), 0) + 1

    random_grades: list[tuple[list[int], int | None, int, bool]] = []
    keep_all_random = not winners_only
    for _ in range(int(random_count)):
        numbers = _pick_unique(rng, pool, main_count)
        grade, matched, bonus_hit = ticket_grade(set(numbers), main_set, bonus_set, main_count)
        if grade is not None:
            by_grade_counts[int(grade)] = by_grade_counts.get(int(grade), 0) + 1
        if keep_all_random or grade is not None:
            random_grades.append((numbers, grade, matched, bonus_hit))

    carry = 0 if carryover_amount is None else max(0, int(carryover_amount))
    grade1_pool = carry + grade1_base
    grade1_winners = by_grade_counts.get(1, 0)

    by_grade = []
    prize_total = 0
    for grade in sorted(by_grade_counts):
        count = by_grade_counts[grade]
        per = _grade_amount(
            grade,
            grade1_pool=grade1_pool,
            grade1_winners=grade1_winners,
            fixed=fixed,
        )
        total = per * count
        prize_total += total
        by_grade.append(
            {
                "grade": grade,
                "count": count,
                "amount_each": per,
                "amount_total": total,
            }
        )

    details: list[dict[str, Any]] = []
    idx = 0

    def append_detail(
        numbers: list[int],
        source: str,
        grade: int | None,
        matched: int,
        bonus_hit: bool,
    ) -> None:
        nonlocal idx
        idx += 1
        amount = 0
        if grade is not None:
            amount = _grade_amount(
                int(grade),
                grade1_pool=grade1_pool,
                grade1_winners=grade1_winners,
                fixed=fixed,
            )
        if winners_only and grade is None:
            return
        details.append(
            {
                "index": idx,
                "source": source,
                "numbers": numbers,
                "grade": grade,
                "match_count": matched,
                "bonus_hit": bonus_hit,
                "amount": amount,
            }
        )

    for numbers, grade, matched, bonus_hit in hand_grades:
        append_detail(numbers, "hand", grade, matched, bonus_hit)
    for numbers, grade, matched, bonus_hit in random_grades:
        append_detail(numbers, "random", grade, matched, bonus_hit)

    cost = total_count * unit_price
    return {
        "game": game,
        "label": game_def.get("label"),
        "unit_price": unit_price,
        "ticket_count": total_count,
        "hand_count": len(hand),
        "random_count": int(random_count),
        "cost": cost,
        "prize_total": prize_total,
        "net": prize_total - cost,
        "carryover_amount": carry,
        "grade1_pool": grade1_pool,
        "draw": {
            "numbers": win_mains,
            "bonuses": win_bonuses,
        },
        "by_grade": by_grade,
        "winners_only": winners_only,
        "detail_threshold": DETAIL_THRESHOLD,
        "details": details,
        "max_tickets": max_tickets,
    }
