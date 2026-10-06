"""出現頻度、共起、奇数偶数比、合計値の集計。"""

from __future__ import annotations

import sqlite3
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def analyze(rows: list[sqlite3.Row], config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    if not rows:
        raise ValueError("分析対象の抽せんがありません")

    frame = pd.DataFrame([dict(row) for row in rows])
    frame = frame.sort_values("draw_no").reset_index(drop=True)
    draw_count = len(frame)
    main_count = int(config.get("lottery", {}).get("main_count", 6))
    number_frame = _number_frame(frame, main_count)
    frequency = _frequency(frame, number_frame, draw_count, int(config["lottery"]["max_number"]), main_count)
    pairs = _cooccurrence(number_frame, 2, draw_count, int(config["analysis"]["top_pairs"]))
    triples = _cooccurrence(number_frame, 3, draw_count, int(config["analysis"]["top_triples"]))
    odd_even = _odd_even(number_frame, draw_count, main_count)
    sums = _sums(number_frame, draw_count)
    return {
        "frequency": frequency,
        "pairs": pairs,
        "triples": triples,
        "odd_even": odd_even,
        "sums": sums,
        "draws": frame,
    }


def to_payload(result: dict[str, pd.DataFrame]) -> dict[str, Any]:
    draws = result["draws"]
    return {
        "meta": {
            "draw_count": int(len(draws)),
            "start_draw": int(draws["draw_no"].iloc[0]),
            "end_draw": int(draws["draw_no"].iloc[-1]),
            "start_date": str(draws["draw_date"].iloc[0]),
            "end_date": str(draws["draw_date"].iloc[-1]),
        },
        "frequency": _records(result["frequency"]),
        "pairs": _records(result["pairs"]),
        "triples": _records(result["triples"]),
        "odd_even": _records(result["odd_even"]),
        "sums": _records(result["sums"]),
        "summary_text": render_summary(result),
    }


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    clean = frame.replace({np.nan: None})
    return [
        {
            key: (int(value) if isinstance(value, (np.integer,)) else float(value) if isinstance(value, (np.floating,)) else value)
            for key, value in row.items()
        }
        for row in clean.to_dict(orient="records")
    ]


def write_outputs(result: dict[str, pd.DataFrame], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result["frequency"].to_csv(output_dir / "frequency.csv", index=False)
    result["pairs"].to_csv(output_dir / "pairs.csv", index=False)
    result["triples"].to_csv(output_dir / "triples.csv", index=False)
    result["odd_even"].to_csv(output_dir / "odd_even.csv", index=False)
    result["sums"].to_csv(output_dir / "sum_distribution.csv", index=False)
    summary_path = output_dir / "summary.txt"
    summary_path.write_text(render_summary(result), encoding="utf-8")
    return summary_path


def render_summary(result: dict[str, pd.DataFrame]) -> str:
    draws = result["draws"]
    frequency = result["frequency"]
    pairs = result["pairs"]
    triples = result["triples"]
    odd_even = result["odd_even"]
    sums = result["sums"]
    draw_count = len(draws)
    lines = [
        "ロト6 統計分析",
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
    lines.extend(["", "2数字の同時出現 上位10"])
    for row in pairs.head(10).itertuples(index=False):
        lines.append(f"  {int(row.number_a):02d}-{int(row.number_b):02d}  {int(row.count)}回  確率{row.probability:.3f}")
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
    mean = float(np.average(present["sum_value"], weights=present["draws"]))
    # 中央値は開催回ごとの合計から
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
    bins = _sum_bins(present)
    for label, count in bins:
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


def _frequency(
    frame: pd.DataFrame,
    number_frame: pd.DataFrame,
    draw_count: int,
    max_number: int,
    main_count: int = 6,
) -> pd.DataFrame:
    counts = number_frame.groupby("number").size()
    bonus_counts = frame["bonus"].astype(int).value_counts()
    last_pos: dict[int, int] = {}
    last_draw: dict[int, tuple[int, str]] = {}
    ordered = frame.sort_values("draw_no")
    for position, row in enumerate(ordered.itertuples(index=False)):
        for index in range(1, main_count + 1):
            value = getattr(row, f"n{index}", None)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            number = int(value)
            last_pos[number] = position
            last_draw[number] = (int(row.draw_no), row.draw_date)
    records = []
    for number in range(1, max_number + 1):
        count = int(counts.get(number, 0))
        if number in last_pos:
            since = (draw_count - 1) - last_pos[number]
            last_no, last_date = last_draw[number]
        else:
            since = draw_count
            last_no, last_date = None, None
        records.append(
            {
                "number": number,
                "count": count,
                "probability": count / draw_count,
                "draws_since_last": since,
                "last_draw_no": last_no,
                "last_draw_date": last_date,
                "bonus_count": int(bonus_counts.get(number, 0)),
            }
        )
    table = pd.DataFrame(records)
    table = table.sort_values(["count", "number"], ascending=[False, True]).reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table


def _cooccurrence(number_frame: pd.DataFrame, size: int, draw_count: int, limit: int) -> pd.DataFrame:
    grouped = number_frame.groupby("draw_no")["number"].apply(lambda values: tuple(sorted(int(v) for v in values)))
    counts: dict[tuple[int, ...], int] = {}
    for numbers in grouped:
        for combo in combinations(numbers, size):
            counts[combo] = counts.get(combo, 0) + 1
    rows = []
    for combo, count in counts.items():
        row = {f"number_{name}": value for name, value in zip("abc", combo)}
        row["count"] = count
        row["probability"] = count / draw_count
        rows.append(row)
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table = table.sort_values(["count", "number_a"], ascending=[False, True]).reset_index(drop=True)
    return table.head(limit)


def _odd_even(number_frame: pd.DataFrame, draw_count: int, main_count: int = 6) -> pd.DataFrame:
    grouped = number_frame.groupby("draw_no")["number"].apply(list)
    records = []
    for numbers in grouped:
        even_count = sum(1 for number in numbers if number % 2 == 0)
        records.append({"even_count": even_count, "odd_count": main_count - even_count})
    table = pd.DataFrame(records)
    summary = (
        table.groupby(["even_count", "odd_count"])
        .size()
        .reset_index(name="draws")
        .sort_values("even_count")
        .reset_index(drop=True)
    )
    summary["rate"] = summary["draws"] / draw_count
    return summary


def _sums(number_frame: pd.DataFrame, draw_count: int) -> pd.DataFrame:
    totals = number_frame.groupby("draw_no")["number"].sum().astype(int)
    summary = totals.value_counts().rename_axis("sum_value").reset_index(name="draws")
    summary = summary.sort_values("sum_value").reset_index(drop=True)
    summary["rate"] = summary["draws"] / draw_count
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
