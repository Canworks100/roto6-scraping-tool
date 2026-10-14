"""出現頻度、共起、奇数偶数比、合計値の集計。"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PERIODS: dict[str, str] = {
    "all": "全期間",
    "draws50": "直近50回",
    "draws100": "直近100回",
    "draws500": "直近500回",
    "years1": "過去1年",
    "years3": "過去3年",
    "years5": "過去5年",
    "years10": "過去10年",
}

BANDS_3: dict[str, list[tuple[str, int, int]]] = {
    "loto6": [("低", 1, 14), ("中", 15, 29), ("高", 30, 43)],
    "loto7": [("低", 1, 12), ("中", 13, 25), ("高", 26, 37)],
    "miniloto": [("低", 1, 10), ("中", 11, 21), ("高", 22, 31)],
}


def years_ago(years: int, today: date | None = None) -> str:
    today = today or date.today()
    try:
        cutoff = today.replace(year=today.year - years)
    except ValueError:
        cutoff = today.replace(year=today.year - years, day=28)
    return cutoff.isoformat()


def parse_period(period: str | None, years: int | None) -> str:
    if period:
        if period not in PERIODS:
            raise ValueError("期間が不正です")
        return period
    if years is not None:
        if years == 5:
            return "years5"
        if years == 10:
            return "years10"
        return "years10"
    return "all"


def load_period_rows(store: Any, game: str, period: str) -> list[sqlite3.Row]:
    if period == "all":
        return store.load_draws(game=game)
    if period.startswith("draws"):
        count = int(period.replace("draws", ""))
        rows = store.load_draws(game=game, limit=count, newest_first=True)
        return list(reversed(rows))
    if period.startswith("years"):
        years = int(period.replace("years", ""))
        return store.load_draws(start_date=years_ago(years), game=game)
    raise ValueError("期間が不正です")


def analyze(rows: list[sqlite3.Row], config: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        raise ValueError("分析対象の抽せんがありません")

    frame = pd.DataFrame([dict(row) for row in rows])
    frame = frame.sort_values("draw_no").reset_index(drop=True)
    draw_count = len(frame)
    lottery = config.get("lottery") or {}
    main_count = int(lottery.get("main_count", 6))
    min_number = int(lottery.get("min_number", 1))
    max_number = int(lottery.get("max_number", 43))
    bonus_count = int(lottery.get("bonus_count", 1))
    game_id = str(config.get("_game") or lottery.get("game") or "loto6")
    number_frame = _number_frame(frame, main_count)
    n_universe = max_number - min_number + 1
    frequency = _frequency(
        frame,
        number_frame,
        draw_count,
        min_number,
        max_number,
        main_count,
        bonus_count,
    )
    pairs_all = _cooccurrence(number_frame, 2, draw_count, None)
    triples_all = _cooccurrence(number_frame, 3, draw_count, None)
    pair_expected = draw_count * math.comb(main_count, 2) / math.comb(n_universe, 2)
    triple_expected = draw_count * math.comb(main_count, 3) / math.comb(n_universe, 3)
    if not pairs_all.empty:
        pairs_all["expected"] = pair_expected
    if not triples_all.empty:
        triples_all["expected"] = triple_expected
    pairs_high, pairs_low = _high_low(pairs_all, 30, 10)
    triples_high, triples_low = _high_low(triples_all, 100, 10)
    triples_high = _with_last_draw(triples_high, number_frame)
    triples_low = _with_last_draw(triples_low, number_frame)
    odd_even = _odd_even(number_frame, draw_count, main_count)
    sums = _sums(number_frame, draw_count)
    return {
        "frequency": frequency,
        "pairs": pairs_high,
        "pairs_high": pairs_high,
        "pairs_low": pairs_low,
        "triples": triples_high,
        "triples_high": triples_high,
        "triples_low": triples_low,
        "pairs_all": pairs_all,
        "odd_even": odd_even,
        "sums": sums,
        "draws": frame,
        "shape": _shape(frame, number_frame, draw_count, main_count, min_number, max_number, game_id),
        "follow": _follow(frame, main_count, min_number, max_number),
        "main_count": main_count,
        "min_number": min_number,
        "max_number": max_number,
        "bonus_count": bonus_count,
        "n_universe": n_universe,
        "pair_expected": pair_expected,
        "triple_expected": triple_expected,
    }


def to_payload(result: dict[str, Any], period: str = "all") -> dict[str, Any]:
    draws = result["draws"]
    return {
        "period": period,
        "period_label": PERIODS.get(period, period),
        "meta": {
            "draw_count": int(len(draws)),
            "start_draw": int(draws["draw_no"].iloc[0]),
            "end_draw": int(draws["draw_no"].iloc[-1]),
            "start_date": str(draws["draw_date"].iloc[0]),
            "end_date": str(draws["draw_date"].iloc[-1]),
        },
        "frequency": _records(result["frequency"]),
        "pairs": _records(result["pairs"]),
        "pairs_high": _records(result["pairs_high"]),
        "pairs_low": _records(result["pairs_low"]),
        "triples": _records(result["triples"]),
        "triples_high": _records(result["triples_high"]),
        "triples_low": _records(result["triples_low"]),
        "odd_even": _records(result["odd_even"]),
        "sums": _records(result["sums"]),
        "shape": result["shape"],
        "follow": result["follow"],
        "summary_text": render_summary(result),
    }


def number_payload(result: dict[str, Any], number: int, items: list[dict[str, Any]], total: int) -> dict[str, Any]:
    freq = result["frequency"]
    row = freq[freq["number"] == number]
    if row.empty:
        return {}
    rec = _records(row)[0]
    pairs = result.get("pairs_all")
    mates: list[dict[str, Any]] = []
    if pairs is not None and not pairs.empty:
        hit = pairs[(pairs["number_a"] == number) | (pairs["number_b"] == number)].copy()
        hit = hit.sort_values(["count", "number_a"], ascending=[False, True]).head(20)
        for item in _records(hit):
            other = int(item["number_b"] if int(item["number_a"]) == number else item["number_a"])
            mates.append({"number": other, "count": int(item["count"]), "probability": item["probability"]})
    return {
        "number": number,
        "frequency": rec,
        "mates": mates,
        "total": total,
        "items": items,
        "meta": to_payload(result).get("meta"),
    }


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    clean = frame.replace({np.nan: None})
    return [
        {
            key: (
                int(value)
                if isinstance(value, (np.integer,))
                else float(value)
                if isinstance(value, (np.floating,))
                else value
            )
            for key, value in row.items()
        }
        for row in clean.to_dict(orient="records")
    ]


def write_outputs(result: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result["frequency"].to_csv(output_dir / "frequency.csv", index=False)
    result["pairs"].to_csv(output_dir / "pairs.csv", index=False)
    result["triples"].to_csv(output_dir / "triples.csv", index=False)
    result["odd_even"].to_csv(output_dir / "odd_even.csv", index=False)
    result["sums"].to_csv(output_dir / "sum_distribution.csv", index=False)
    summary_path = output_dir / "summary.txt"
    summary_path.write_text(render_summary(result), encoding="utf-8")
    return summary_path


def render_summary(result: dict[str, Any]) -> str:
    draws = result["draws"]
    frequency = result["frequency"]
    pairs = result["pairs"]
    triples = result["triples"]
    odd_even = result["odd_even"]
    sums = result["sums"]
    draw_count = len(draws)
    lines = [
        "統計分析",
        f"対象: 第{int(draws['draw_no'].iloc[0])}回（{draws['draw_date'].iloc[0]}）"
        f" 〜 第{int(draws['draw_no'].iloc[-1])}回（{draws['draw_date'].iloc[-1]}）",
        f"開催回数: {draw_count}",
        "",
        "出現回数の上位10（本数字）",
    ]
    for row in frequency.head(10).itertuples(index=False):
        lines.append(
            f"  {int(row.rank):2d}位  {int(row.number):2d}  "
            f"{int(row.count)}回  確率{row.probability:.3f}  経過{int(row.draws_since_last)}回"
        )
    lines.extend(["", "出現回数の下位5（本数字）"])
    for row in frequency.tail(5).itertuples(index=False):
        lines.append(
            f"  {int(row.rank):2d}位  {int(row.number):2d}  "
            f"{int(row.count)}回  確率{row.probability:.3f}  経過{int(row.draws_since_last)}回"
        )
    if not pairs.empty:
        lines.extend(["", "2数字の同時出現 上位10"])
        for row in pairs.head(10).itertuples(index=False):
            lines.append(f"  {int(row.number_a):02d}-{int(row.number_b):02d}  {int(row.count)}回  確率{row.probability:.3f}")
    if not triples.empty:
        lines.extend(["", "3数字の同時出現 上位5"])
        for row in triples.head(5).itertuples(index=False):
            lines.append(
                f"  {int(row.number_a):02d}-{int(row.number_b):02d}-{int(row.number_c):02d}  "
                f"{int(row.count)}回  確率{row.probability:.3f}"
            )
    lines.extend(["", "本数字の偶数・奇数"])
    for row in odd_even.itertuples(index=False):
        lines.append(f"  偶数{int(row.even_count)}・奇数{int(row.odd_count)}  {int(row.draws)}回  割合{row.rate:.3f}")
    present = sums[sums["draws"] > 0]
    if not present.empty:
        mean = float(np.average(present["sum_value"], weights=present["draws"]))
        expanded = np.repeat(present["sum_value"].to_numpy(), present["draws"].to_numpy())
        lines.extend(
            [
                "",
                "本数字の合計",
                f"  平均 {mean:.2f}",
                f"  中央値 {float(np.median(expanded)):.1f}",
                f"  最小 {int(expanded.min())}",
                f"  最大 {int(expanded.max())}",
                f"  最頻値 {int(present.loc[present['draws'].idxmax(), 'sum_value'])}",
                "",
                "合計値の分布（10刻み）",
            ]
        )
        for label, count in _sum_bins(present):
            lines.append(f"  {label}  {count}回")
    lines.append("")
    return "\n".join(lines)


def _number_frame(frame: pd.DataFrame, main_count: int = 6) -> pd.DataFrame:
    parts = []
    for index in range(1, main_count + 1):
        col = f"n{index}"
        if col not in frame.columns:
            continue
        part = frame[["draw_no", "draw_date", col]].rename(columns={col: "number"})
        part = part[part["number"].notna()]
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    out["number"] = out["number"].astype(int)
    return out


def _mains(row: Any, main_count: int) -> list[int]:
    values = []
    for index in range(1, main_count + 1):
        value = getattr(row, f"n{index}", None)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        values.append(int(value))
    return values


def _bonuses(row: Any) -> list[int]:
    values = [int(row.bonus)]
    bonus2 = getattr(row, "bonus2", None)
    if bonus2 is not None and not (isinstance(bonus2, float) and pd.isna(bonus2)):
        values.append(int(bonus2))
    return values


def _rest_streak(ordered: pd.DataFrame, main_count: int, universe: list[int], kind: str) -> dict[int, dict[str, Any]]:
    rest_run = {n: 0 for n in universe}
    hit_run = {n: 0 for n in universe}
    max_rest = {n: 0 for n in universe}
    max_streak = {n: 0 for n in universe}
    last_pos: dict[int, int] = {}
    last_draw: dict[int, tuple[int, str]] = {}
    draw_count = len(ordered)
    for position, row in enumerate(ordered.itertuples(index=False)):
        hits = set(_mains(row, main_count) if kind == "main" else _bonuses(row))
        for number in universe:
            if number in hits:
                hit_run[number] += 1
                rest_run[number] = 0
                max_streak[number] = max(max_streak[number], hit_run[number])
                last_pos[number] = position
                last_draw[number] = (int(row.draw_no), str(row.draw_date))
            else:
                hit_run[number] = 0
                rest_run[number] += 1
                max_rest[number] = max(max_rest[number], rest_run[number])
    out: dict[int, dict[str, Any]] = {}
    for number in universe:
        if number in last_pos:
            since = (draw_count - 1) - last_pos[number]
            last_no, last_date = last_draw[number]
        else:
            since = draw_count
            last_no, last_date = None, None
            max_rest[number] = draw_count
        out[number] = {
            "draws_since_last": since,
            "last_draw_no": last_no,
            "last_draw_date": last_date,
            "max_rest": max_rest[number],
            "max_streak": max_streak[number],
        }
    return out


def _frequency(
    frame: pd.DataFrame,
    number_frame: pd.DataFrame,
    draw_count: int,
    min_number: int,
    max_number: int,
    main_count: int,
    bonus_count: int,
) -> pd.DataFrame:
    universe = list(range(min_number, max_number + 1))
    n_universe = len(universe)
    counts = number_frame.groupby("number").size()
    bonus_series = []
    bonus_series.append(frame["bonus"].astype(int))
    if "bonus2" in frame.columns:
        extra = frame["bonus2"].dropna().astype(int)
        bonus_series.append(extra)
    bonus_counts = pd.concat(bonus_series, ignore_index=True).value_counts()
    ordered = frame.sort_values("draw_no")
    main_stats = _rest_streak(ordered, main_count, universe, "main")
    bonus_stats = _rest_streak(ordered, main_count, universe, "bonus")
    expected_main = draw_count * main_count / n_universe
    expected_bonus = draw_count * bonus_count / n_universe
    records = []
    for number in universe:
        count = int(counts.get(number, 0))
        bonus_count_n = int(bonus_counts.get(number, 0))
        main = main_stats[number]
        bonus = bonus_stats[number]
        records.append(
            {
                "number": number,
                "count": count,
                "probability": count / draw_count if draw_count else 0,
                "draws_since_last": main["draws_since_last"],
                "last_draw_no": main["last_draw_no"],
                "last_draw_date": main["last_draw_date"],
                "bonus_count": bonus_count_n,
                "main_plus_bonus": count + bonus_count_n,
                "expected_main": expected_main,
                "expected_bonus": expected_bonus,
                "max_rest": main["max_rest"],
                "max_streak": main["max_streak"],
                "bonus_draws_since_last": bonus["draws_since_last"],
                "bonus_last_draw_no": bonus["last_draw_no"],
                "bonus_last_draw_date": bonus["last_draw_date"],
                "bonus_max_rest": bonus["max_rest"],
                "bonus_max_streak": bonus["max_streak"],
            }
        )
    table = pd.DataFrame(records)
    table = table.sort_values(["count", "number"], ascending=[False, True]).reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table


def _cooccurrence(number_frame: pd.DataFrame, size: int, draw_count: int, limit: int | None) -> pd.DataFrame:
    grouped = number_frame.groupby("draw_no")["number"].apply(lambda values: tuple(sorted(int(v) for v in values)))
    counts: dict[tuple[int, ...], int] = {}
    last_draw: dict[tuple[int, ...], int] = {}
    for draw_no, numbers in grouped.items():
        for combo in combinations(numbers, size):
            counts[combo] = counts.get(combo, 0) + 1
            last_draw[combo] = int(draw_no)
    rows = []
    for combo, count in counts.items():
        row = {f"number_{name}": value for name, value in zip("abc", combo)}
        row["count"] = count
        row["probability"] = count / draw_count if draw_count else 0
        row["last_draw_no"] = last_draw[combo]
        rows.append(row)
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table = table.sort_values(["count", "number_a"], ascending=[False, True]).reset_index(drop=True)
    if limit is not None:
        return table.head(limit)
    return table


def _with_last_draw(table: pd.DataFrame, number_frame: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return table
    hits = number_frame[number_frame["draw_no"].isin(table["last_draw_no"])]
    dates = hits.groupby("draw_no")["draw_date"].first()
    mains = hits.groupby("draw_no")["number"].apply(lambda values: sorted(int(v) for v in values))
    combo_cols = [col for col in ("number_a", "number_b", "number_c") if col in table.columns]
    out = table.copy()
    out["last_draw_date"] = [str(dates[no]) for no in out["last_draw_no"]]
    out["others"] = [
        [n for n in mains[no] if n not in combo]
        for no, combo in zip(out["last_draw_no"], out[combo_cols].itertuples(index=False, name=None))
    ]
    return out


def _high_low(table: pd.DataFrame, high: int, low: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    empty = table.iloc[0:0] if table is not None else pd.DataFrame()
    if table is None or table.empty:
        return empty, empty
    appeared = table[table["count"] >= 1]
    if len(appeared) < high + low:
        return appeared, empty
    return appeared.head(high).reset_index(drop=True), appeared.tail(low).reset_index(drop=True)


def _odd_even(number_frame: pd.DataFrame, draw_count: int, main_count: int = 6) -> pd.DataFrame:
    grouped = number_frame.groupby("draw_no")["number"].apply(list)
    found: dict[int, int] = {}
    for numbers in grouped:
        even_count = sum(1 for number in numbers if number % 2 == 0)
        found[even_count] = found.get(even_count, 0) + 1
    records = []
    for even_count in range(0, main_count + 1):
        draws = found.get(even_count, 0)
        records.append(
            {
                "even_count": even_count,
                "odd_count": main_count - even_count,
                "draws": draws,
                "rate": draws / draw_count if draw_count else 0,
            }
        )
    return pd.DataFrame(records)


def _sums(number_frame: pd.DataFrame, draw_count: int) -> pd.DataFrame:
    totals = number_frame.groupby("draw_no")["number"].sum().astype(int)
    summary = totals.value_counts().rename_axis("sum_value").reset_index(name="draws")
    summary = summary.sort_values("sum_value").reset_index(drop=True)
    summary["rate"] = summary["draws"] / draw_count if draw_count else 0
    return summary


def _sum_bins(present: pd.DataFrame) -> list[tuple[str, int]]:
    if present.empty:
        return []
    low = int(present["sum_value"].min()) // 10 * 10
    high = int(present["sum_value"].max())
    bins: list[tuple[str, int]] = []
    start = low
    while start <= high:
        end = start + 9
        count = int(present.loc[present["sum_value"].between(start, end), "draws"].sum())
        bins.append((f"{start:3d}-{end:3d}", count))
        start += 10
    return bins


def _shape(
    frame: pd.DataFrame,
    number_frame: pd.DataFrame,
    draw_count: int,
    main_count: int,
    min_number: int,
    max_number: int,
    game_id: str,
) -> dict[str, Any]:
    grouped = number_frame.groupby("draw_no")["number"].apply(lambda values: sorted(int(v) for v in values))
    adj_counts: dict[int, int] = {i: 0 for i in range(main_count)}
    run_counts: dict[int, int] = {}
    digit_counts = [0] * 10
    spans: dict[int, int] = {}
    totals = []
    for numbers in grouped:
        adj = sum(1 for a, b in zip(numbers, numbers[1:]) if b - a == 1)
        adj_counts[adj] = adj_counts.get(adj, 0) + 1
        run = 1
        longest = 1
        for a, b in zip(numbers, numbers[1:]):
            if b - a == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1
        run_counts[longest] = run_counts.get(longest, 0) + 1
        for n in numbers:
            digit_counts[n % 10] += 1
        span = numbers[-1] - numbers[0] if numbers else 0
        spans[span] = spans.get(span, 0) + 1
        totals.append(sum(numbers))

    n_universe = max_number - min_number + 1
    digit_expected = []
    for digit in range(10):
        have = sum(1 for n in range(min_number, max_number + 1) if n % 10 == digit)
        digit_expected.append(
            {
                "digit": digit,
                "count": digit_counts[digit],
                "expected": draw_count * main_count * have / n_universe if n_universe else 0,
            }
        )

    sum_summary = {}
    sum_bins: list[dict[str, Any]] = []
    if totals:
        arr = np.array(totals)
        present = _sums(number_frame, draw_count)
        present = present[present["draws"] > 0]
        sum_summary = {
            "mean": float(arr.mean()),
            "median": float(np.median(arr)),
            "min": int(arr.min()),
            "max": int(arr.max()),
            "mode": int(pd.Series(totals).value_counts().idxmax()),
        }
        sum_bins = [{"label": label, "draws": count} for label, count in _sum_bins(present)]

    bands3 = BANDS_3.get(game_id) or _equal_bands(min_number, max_number, 3)
    bands6 = _six_bands(min_number, max_number)
    band_counts: dict[str, int] = {label: 0 for label, _, _ in bands3}
    mix = {"低": 0.0, "中": 0.0, "高": 0.0}
    six_counts = [{"id": f"s{i}", "label": f"{a}–{b}", "min": a, "max": b, "count": 0} for i, (a, b) in enumerate(bands6, 1)]
    for numbers in grouped:
        for n in numbers:
            for label, a, b in bands3:
                if a <= n <= b:
                    band_counts[label] += 1
                    break
            for item in six_counts:
                if item["min"] <= n <= item["max"]:
                    item["count"] += 1
                    break
        if numbers:
            mix["低"] += sum(1 for n in numbers if bands3[0][1] <= n <= bands3[0][2])
            mix["中"] += sum(1 for n in numbers if bands3[1][1] <= n <= bands3[1][2])
            mix["高"] += sum(1 for n in numbers if bands3[2][1] <= n <= bands3[2][2])
    if draw_count:
        mix = {k: v / draw_count for k, v in mix.items()}

    weekday = [{"weekday": i, "draws": 0} for i in range(7)]
    for date in frame["draw_date"]:
        parsed = datetime.strptime(str(date)[:10], "%Y-%m-%d")
        weekday[parsed.weekday()]["draws"] += 1

    span_rows = [{"span": k, "draws": v} for k, v in sorted(spans.items())]
    span_vals = np.array([k for k, v in spans.items() for _ in range(v)]) if spans else np.array([])
    span_summary = {
        "mean": float(span_vals.mean()) if len(span_vals) else 0,
        "min": int(span_vals.min()) if len(span_vals) else 0,
        "max": int(span_vals.max()) if len(span_vals) else 0,
    }

    return {
        "odd_even": _records(_odd_even(number_frame, draw_count, main_count)),
        "sum_summary": sum_summary,
        "sum_bins": sum_bins,
        "consecutive_pairs": [
            {"adjacent_count": k, "draws": v, "rate": v / draw_count if draw_count else 0} for k, v in adj_counts.items()
        ],
        "consecutive_run": [
            {"run_length": k, "draws": v, "rate": v / draw_count if draw_count else 0}
            for k, v in sorted(run_counts.items())
        ],
        "last_digit": digit_expected,
        "span": {"summary": span_summary, "items": span_rows},
        "bands": [
            *[{"id": f"3{label}", "label": label, "min": a, "max": b, "count": band_counts[label]} for label, a, b in bands3],
            *six_counts,
        ],
        "band_mix": mix,
        "weekday": weekday,
    }


def _equal_bands(min_number: int, max_number: int, parts: int) -> list[tuple[str, int, int]]:
    labels = ["低", "中", "高"][:parts]
    edges = _six_bands(min_number, max_number) if parts == 6 else _split_range(min_number, max_number, parts)
    return [(labels[i] if i < len(labels) else str(i), a, b) for i, (a, b) in enumerate(edges)]


def _split_range(min_number: int, max_number: int, parts: int) -> list[tuple[int, int]]:
    size = max_number - min_number + 1
    base = size // parts
    rem = size % parts
    edges = []
    start = min_number
    for i in range(parts):
        width = base + (1 if i >= parts - rem else 0)
        end = start + width - 1
        edges.append((start, end))
        start = end + 1
    return edges


def _six_bands(min_number: int, max_number: int) -> list[tuple[int, int]]:
    return _split_range(min_number, max_number, 6)


def _follow(
    frame: pd.DataFrame, main_count: int, min_number: int, max_number: int
) -> dict[str, Any]:
    """前回の本数字が今回にも出たか（含む／2連続／3連続）。ボーナスは見ない。"""
    ordered = frame.sort_values("draw_no")
    sets = [set(_mains(row, main_count)) for row in ordered.itertuples(index=False)]
    n_draws = len(sets)
    numbers = list(range(min_number, max_number + 1))

    none_count = 0
    any_count = 0
    streak2_draws = 0
    streak3_draws = 0
    without_prev = {n: 0 for n in numbers}
    with_prev = {n: 0 for n in numbers}
    streak2 = {n: 0 for n in numbers}
    streak3 = {n: 0 for n in numbers}

    for i in range(1, n_draws):
        prev = sets[i - 1]
        curr = sets[i]
        inter = prev & curr
        if inter:
            any_count += 1
        else:
            none_count += 1
        prevprev = sets[i - 2] if i >= 2 else None
        if prevprev is None:
            if inter:
                streak2_draws += 1
        else:
            if inter - prevprev:
                streak2_draws += 1
            if inter & prevprev:
                streak3_draws += 1
        for n in curr:
            if n in prev:
                with_prev[n] += 1
                if prevprev is not None and n in prevprev:
                    streak3[n] += 1
                else:
                    streak2[n] += 1
            else:
                without_prev[n] += 1

    denom = float(n_draws) if n_draws else 0.0

    def _rate(count: int) -> float:
        return count / denom if denom else 0.0

    summary = [
        {"key": "none", "draws": none_count, "rate": _rate(none_count)},
        {"key": "any", "draws": any_count, "rate": _rate(any_count)},
        {"key": "streak2", "draws": streak2_draws, "rate": _rate(streak2_draws)},
        {"key": "streak3", "draws": streak3_draws, "rate": _rate(streak3_draws)},
    ]
    by_number = []
    for n in numbers:
        w = with_prev[n]
        wo = without_prev[n]
        appeared = w + wo
        by_number.append(
            {
                "number": n,
                "without_prev": wo,
                "with_prev": w,
                "with_prev_rate": (w / appeared) if appeared else 0.0,
                "streak2": streak2[n],
                "streak3": streak3[n],
            }
        )

    def _top(rows: list[dict[str, Any]], key: str, *, reverse: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        ranked = sorted(rows, key=lambda r: (-r[key] if reverse else r[key], r["number"]))
        out = []
        for r in ranked[:limit]:
            out.append({"number": r["number"], "value": r[key]})
        return out

    appeared_rows = [r for r in by_number if r["without_prev"] + r["with_prev"] > 0]
    highlights = {
        "with_prev_high": _top(appeared_rows, "with_prev"),
        "streak2_high": _top(appeared_rows, "streak2"),
        "rate_high": _top(appeared_rows, "with_prev_rate"),
        "rate_low": _top(appeared_rows, "with_prev_rate", reverse=False),
    }
    return {"summary": summary, "by_number": by_number, "highlights": highlights}


def theoretical_prizes(universe: int, main_count: int, bonus_count: int, grades: int) -> list[dict[str, Any]]:
    total = math.comb(universe, main_count)
    rest = universe - main_count
    rest_plain = universe - main_count - bonus_count
    items: list[dict[str, Any]] = []
    for grade in range(1, grades + 1):
        if grade == 1:
            ways = 1
        elif grade == 2:
            extra = main_count - (main_count - 1) - 1
            ways = math.comb(main_count, main_count - 1) * math.comb(bonus_count, 1) * math.comb(rest_plain, extra)
        elif grade == 3:
            ways = math.comb(main_count, main_count - 1) * math.comb(rest_plain, 1)
        else:
            hit = main_count - (grade - 2)
            extra = main_count - hit
            ways = math.comb(main_count, hit) * math.comb(rest, extra)
        items.append(
            {
                "grade": grade,
                "ways": int(ways),
                "total": int(total),
                "one_in": int(round(total / ways)) if ways else None,
            }
        )
    return items


def ticket_grade(
    picked: set[int],
    mains: set[int],
    bonuses: set[int],
    main_count: int,
) -> tuple[int | None, int, bool]:
    hit = len(picked & mains)
    bonus_hit = bool(picked & bonuses)
    if hit == main_count:
        return 1, hit, bonus_hit
    if hit == main_count - 1 and bonus_hit:
        return 2, hit, True
    if hit == main_count - 1:
        return 3, hit, False
    if hit >= 3:
        return (main_count - hit) + 2, hit, bonus_hit
    return None, hit, bonus_hit


def combo_payload(
    rows: list[sqlite3.Row],
    numbers: list[int],
    config: dict[str, Any],
    period: str = "all",
) -> dict[str, Any]:
    lottery = config.get("lottery") or {}
    main_count = int(lottery.get("main_count", 6))
    min_number = int(lottery.get("min_number", 1))
    max_number = int(lottery.get("max_number", 43))
    bonus_count = int(lottery.get("bonus_count", 1))
    grades = int(config.get("prize_grades") or lottery.get("prize_grades") or 5)
    game_id = str(config.get("_game") or lottery.get("game") or "loto6")
    picked = sorted(set(int(n) for n in numbers))
    if len(picked) != main_count:
        raise ValueError(f"本数字は{main_count}個選んでください")
    if any(n < min_number or n > max_number for n in picked):
        raise ValueError(f"数字は{min_number}〜{max_number}です")
    picked_set = set(picked)
    draw_count = len(rows)
    universe = max_number - min_number + 1
    expected = draw_count * main_count / universe if universe else 0
    even = sum(1 for n in picked if n % 2 == 0)
    odd = main_count - even
    total_sum = sum(picked)
    bin_start = (total_sum // 10) * 10
    sum_bin = f"{bin_start}-{bin_start + 9}"
    adjacent = sum(1 for a, b in zip(picked, picked[1:]) if b - a == 1)
    run = 1
    longest = 1
    for a, b in zip(picked, picked[1:]):
        if b - a == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    bands3 = BANDS_3.get(game_id) or _equal_bands(min_number, max_number, 3)
    band_mix = {label: 0 for label, _, _ in bands3}
    for n in picked:
        for label, lo, hi in bands3:
            if lo <= n <= hi:
                band_mix[label] += 1
                break
    freq: dict[int, dict[str, Any]] = {
        n: {"number": n, "count": 0, "last_draw_no": None, "last_draw_date": None} for n in picked
    }
    match_hist = {i: 0 for i in range(main_count + 1)}
    same_odd = 0
    same_adj = 0
    same_sum_bin = 0
    sum_acc = 0
    exact: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        mains = []
        for index in range(1, main_count + 1):
            value = data.get(f"n{index}")
            if value is None:
                continue
            mains.append(int(value))
        main_set = set(mains)
        hit = len(picked_set & main_set)
        match_hist[hit] = match_hist.get(hit, 0) + 1
        draw_no = int(data["draw_no"])
        draw_date = str(data["draw_date"])
        for n in picked_set & main_set:
            item = freq[n]
            item["count"] += 1
            if item["last_draw_no"] is None or draw_no > int(item["last_draw_no"]):
                item["last_draw_no"] = draw_no
                item["last_draw_date"] = draw_date
        sorted_mains = sorted(mains)
        draw_even = sum(1 for n in sorted_mains if n % 2 == 0)
        if draw_even == even:
            same_odd += 1
        draw_adj = sum(1 for a, b in zip(sorted_mains, sorted_mains[1:]) if b - a == 1)
        if draw_adj == adjacent:
            same_adj += 1
        draw_sum = sum(sorted_mains)
        draw_bin = (draw_sum // 10) * 10
        if draw_bin == bin_start:
            same_sum_bin += 1
        sum_acc += draw_sum
        if hit == main_count:
            p1 = data.get("prize1_amount")
            exact.append(
                {
                    "draw_no": draw_no,
                    "draw_date": draw_date,
                    "match_count": hit,
                    "prize1_amount": None if p1 is None else int(p1),
                }
            )
        if hit >= 3:
            samples.append(
                {
                    "draw_no": draw_no,
                    "draw_date": draw_date,
                    "match_count": hit,
                    "numbers": sorted_mains,
                }
            )
        bonuses = []
        if data.get("bonus") is not None:
            bonuses.append(int(data["bonus"]))
        if data.get("bonus2") is not None:
            bonuses.append(int(data["bonus2"]))
        grade, _, bonus_hit = ticket_grade(picked_set, main_set, set(bonuses), main_count)
        if grade is not None:
            amount_raw = data.get(f"prize{grade}_amount")
            amount = None if amount_raw is None else int(amount_raw)
            hits.append(
                {
                    "draw_no": draw_no,
                    "draw_date": draw_date,
                    "grade": grade,
                    "match_count": hit,
                    "bonus_hit": bonus_hit,
                    "numbers": sorted_mains,
                    "bonus": bonuses[0] if bonuses else None,
                    "bonus2": bonuses[1] if len(bonuses) > 1 else None,
                    "amount": amount,
                }
            )
    numbers_out = []
    for n in picked:
        item = freq[n]
        count = int(item["count"])
        numbers_out.append(
            {
                "number": n,
                "count": count,
                "expected": expected,
                "vs_expected": int(round(count - expected)),
                "last_draw_no": item["last_draw_no"],
                "last_draw_date": item["last_draw_date"],
            }
        )
    exact.sort(key=lambda item: -int(item["draw_no"]))
    samples.sort(key=lambda item: -int(item["draw_no"]))
    hits.sort(key=lambda item: -int(item["draw_no"]))
    unit_price = {"loto6": 200, "loto7": 300, "miniloto": 200}.get(game_id, 200)
    by_grade_map: dict[int, dict[str, int]] = {}
    prize_total = 0
    unknown_amount = 0
    for item in hits:
        g = int(item["grade"])
        row = by_grade_map.setdefault(g, {"grade": g, "draws": 0, "amount": 0})
        row["draws"] += 1
        if item["amount"] is None:
            unknown_amount += 1
        else:
            prize_total += int(item["amount"])
            row["amount"] += int(item["amount"])
    whatif = {
        "hit_count": len(hits),
        "prize_total": prize_total,
        "unknown_amount": unknown_amount,
        "unit_price": unit_price,
        "cost": draw_count * unit_price,
        "by_grade": [by_grade_map[g] for g in sorted(by_grade_map)],
    }
    mean_sum = sum_acc / draw_count if draw_count else 0
    shape = {
        "even_count": even,
        "odd_count": odd,
        "same_odd_even_draws": same_odd,
        "sum": total_sum,
        "sum_bin": sum_bin,
        "same_sum_bin_draws": same_sum_bin,
        "mean_sum": round(mean_sum, 1),
        "adjacent_count": adjacent,
        "longest_run": longest,
        "same_adjacent_draws": same_adj,
        "bands": [{"label": label, "count": band_mix[label]} for label, _, _ in bands3],
    }
    return {
        "period": period,
        "numbers": picked,
        "draw_count": draw_count,
        "prizes": theoretical_prizes(universe, main_count, bonus_count, grades),
        "match_hist": [{"match_count": k, "draws": match_hist.get(k, 0)} for k in range(main_count + 1)],
        "exact_count": len(exact),
        "exact": exact[:20],
        "samples": samples[:20],
        "hits": hits,
        "whatif": whatif,
        "numbers_stats": numbers_out,
        "shape": shape,
        "diagnosis": _combo_diagnosis(
            draw_count,
            shape,
            numbers_out,
            main_count,
        ),
        "meta": {"draw_count": draw_count, "period": period},
    }


DX_LEVELS = ("イマイチ", "もう一息", "普通", "いい感じ！", "とてもいい！")
_TONE_WEIGHT = {"good": 2, "ok": 1, "off": 0}


def _point_row(label: str, tone: str, text: str) -> dict[str, Any]:
    return {"label": label, "tone": tone, "text": text}


def _level_from_quality(quality: int) -> int:
    """内部品質 0〜10 を 0〜4 の段階へ。"""
    if quality >= 10:
        return 4
    if quality >= 9:
        return 3
    if quality >= 7:
        return 2
    if quality >= 5:
        return 1
    return 0


def _combo_diagnosis(
    draw_count: int,
    shape: dict[str, Any],
    numbers_stats: list[dict[str, Any]],
    main_count: int,
) -> dict[str, Any]:
    """5項目の形所見を、5段階の文言にまとめる。"""
    points: list[dict[str, Any]] = []
    even = int(shape["even_count"])
    odd = int(shape["odd_count"])
    same_odd = int(shape["same_odd_even_draws"])
    if main_count % 2 == 0:
        even_ok = even == main_count // 2
        even_near = abs(even - main_count // 2) == 1
    else:
        even_ok = abs(even - odd) <= 1
        even_near = abs(even - odd) == 3
    if even_ok:
        points.append(
            _point_row(
                "奇数偶数",
                "good",
                f"偶数{even}個・奇数{odd}個。過去{same_odd}回と同じ形です。",
            )
        )
    elif even_near:
        points.append(
            _point_row(
                "奇数偶数",
                "ok",
                f"偶数{even}個・奇数{odd}個。少し偏っています。過去{same_odd}回です。",
            )
        )
    else:
        points.append(
            _point_row(
                "奇数偶数",
                "off",
                f"偶数{even}個・奇数{odd}個。偏りが強めです。過去{same_odd}回です。",
            )
        )

    total_sum = int(shape["sum"])
    mean_sum = float(shape.get("mean_sum") or 0)
    sum_bin = str(shape["sum_bin"]).replace("-", "〜")
    same_sum = int(shape["same_sum_bin_draws"])
    diff = abs(total_sum - mean_sum) if mean_sum else 0
    if mean_sum and diff <= 15:
        points.append(
            _point_row(
                "合計",
                "good",
                f"合計{total_sum}（{sum_bin}）。平均{mean_sum:.0f}の近くです。過去{same_sum}回。",
            )
        )
    elif mean_sum and diff <= 35:
        points.append(
            _point_row(
                "合計",
                "ok",
                f"合計{total_sum}（{sum_bin}）。平均{mean_sum:.0f}からやや離れています。過去{same_sum}回。",
            )
        )
    else:
        points.append(
            _point_row(
                "合計",
                "off",
                f"合計{total_sum}（{sum_bin}）。平均{mean_sum:.0f}から離れています。過去{same_sum}回。",
            )
        )

    adjacent = int(shape["adjacent_count"])
    same_adj = int(shape["same_adjacent_draws"])
    if adjacent <= 1:
        points.append(
            _point_row(
                "連番",
                "good",
                f"連番{adjacent}組。並びは落ち着いています。過去{same_adj}回。",
            )
        )
    elif adjacent == 2:
        points.append(
            _point_row(
                "連番",
                "ok",
                f"連番{adjacent}組。やや多めです。過去{same_adj}回。",
            )
        )
    else:
        points.append(
            _point_row(
                "連番",
                "off",
                f"連番{adjacent}組。連なりが強い並びです。過去{same_adj}回。",
            )
        )

    bands = list(shape["bands"])
    used = sum(1 for b in bands if int(b["count"]) > 0)
    band_line = "、".join(f"{b['label']}{b['count']}個" for b in bands)
    if used >= 3:
        points.append(_point_row("番号帯", "good", f"低・中・高に分かれています。{band_line}。"))
    elif used == 2:
        points.append(_point_row("番号帯", "ok", f"帯が二つに寄っています。{band_line}。"))
    else:
        points.append(_point_row("番号帯", "off", f"帯が一方向に寄っています。{band_line}。"))

    hot = sum(1 for s in numbers_stats if int(s["vs_expected"]) >= 0)
    cold = len(numbers_stats) - hot
    if hot and cold:
        points.append(
            _point_row(
                "出現",
                "good",
                f"出現の多い数字が{hot}個、控えめが{cold}個です。",
            )
        )
    elif hot:
        points.append(_point_row("出現", "ok", "選んだ数字はいずれも出現が多めです。"))
    else:
        points.append(_point_row("出現", "ok", "選んだ数字はいずれも出現が控えめです。"))

    quality = sum(_TONE_WEIGHT.get(str(p["tone"]), 0) for p in points)
    level = _level_from_quality(quality)
    summaries = {
        4: "奇偶・合計・連番・帯・出現のバランスが寄った並びです。",
        3: "形はおおむね整っています。一部に寄りがあります。",
        2: "よくある形と、寄ったところが混ざっています。",
        1: "寄っているところがあり、もう一段の見直し余地があります。",
        0: "過去では少なめの形に寄っています。",
    }
    return {
        "verdict": DX_LEVELS[level],
        "level": level + 1,
        "summary": summaries[level],
        "points": points,
    }
