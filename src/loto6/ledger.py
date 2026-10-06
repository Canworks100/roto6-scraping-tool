"""自分で買ったロト6の記録と、公式結果に基づく収支。"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

UNIT_PRICE = 200


class LedgerError(ValueError):
    """入力が記録できない。"""


class Ledger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init()

    def close(self) -> None:
        self.conn.close()

    def _init(self) -> None:
        with self._lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_no INTEGER NOT NULL,
                    n1 INTEGER NOT NULL,
                    n2 INTEGER NOT NULL,
                    n3 INTEGER NOT NULL,
                    n4 INTEGER NOT NULL,
                    n5 INTEGER NOT NULL,
                    n6 INTEGER NOT NULL,
                    ticket_count INTEGER NOT NULL,
                    unit_price INTEGER NOT NULL,
                    purchased_on TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    prize_override INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_draw ON tickets(draw_no)")
            self.conn.commit()

    def add_ticket(self, payload: dict) -> dict:
        fields = _normalize(payload)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            cursor = self.conn.execute(
                """
                INSERT INTO tickets (
                    draw_no, n1, n2, n3, n4, n5, n6,
                    ticket_count, unit_price, purchased_on, note, prize_override, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*_field_values(fields), created_at),
            )
            self.conn.commit()
            ticket_id = int(cursor.lastrowid)
        return self.get_ticket(ticket_id)

    def update_ticket(self, ticket_id: int, payload: dict) -> dict:
        fields = _normalize(payload)
        with self._lock:
            found = self.conn.execute("SELECT 1 FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if found is None:
                raise LedgerError("その記録はありません")
            self.conn.execute(
                """
                UPDATE tickets SET
                    draw_no=?, n1=?, n2=?, n3=?, n4=?, n5=?, n6=?,
                    ticket_count=?, unit_price=?, purchased_on=?, note=?, prize_override=?
                WHERE id=?
                """,
                (*_field_values(fields), ticket_id),
            )
            self.conn.commit()
        return self.get_ticket(ticket_id)

    def has_same(self, draw_no: int, numbers: list[int]) -> bool:
        ordered = tuple(sorted(int(number) for number in numbers))
        with self._lock:
            row = self.conn.execute(
                """
                SELECT 1 FROM tickets
                WHERE draw_no=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND n6=?
                """,
                (draw_no, *ordered),
            ).fetchone()
        return row is not None

    def delete_ticket(self, ticket_id: int) -> None:
        with self._lock:
            cursor = self.conn.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
            self.conn.commit()
            if cursor.rowcount == 0:
                raise LedgerError("その記録はありません")

    def get_ticket(self, ticket_id: int) -> dict:
        with self._lock:
            row = self.conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            draw = self._draw_for(row["draw_no"]) if row else None
        if row is None:
            raise LedgerError("その記録はありません")
        return _present(row, draw)

    def list_tickets(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM tickets ORDER BY draw_no DESC, id DESC").fetchall()
            draws = {row["draw_no"]: self._draw_for(row["draw_no"]) for row in rows}
        return [_present(row, draws[row["draw_no"]]) for row in rows]

    def summary(self) -> dict:
        tickets = self.list_tickets()
        ticket_count = sum(item["ticket_count"] for item in tickets)
        purchase_total = sum(item["cost"] for item in tickets)
        settled = [item for item in tickets if item["prize"] is not None]
        pending = [item for item in tickets if item["prize"] is None]
        prize_total = sum(int(item["prize"]) for item in settled)
        settled_cost = sum(item["cost"] for item in settled)
        pending_cost = sum(item["cost"] for item in pending)
        hit_count = sum(item["ticket_count"] for item in settled if item["grade"])
        series = _cumulative([item for item in reversed(settled)])
        return {
            "ticket_count": ticket_count,
            "purchase_total": purchase_total,
            "prize_total": prize_total,
            "profit": prize_total - settled_cost,
            "settled_cost": settled_cost,
            "pending_cost": pending_cost,
            "pending_count": sum(item["ticket_count"] for item in pending),
            "hit_count": hit_count,
            "series": series,
        }

    def recent_draws(self, limit: int = 30) -> list[dict]:
        if not self._has_draws():
            return []
        with self._lock:
            rows = self.conn.execute(
                "SELECT draw_no, draw_date FROM draws ORDER BY draw_no DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"draw_no": int(row["draw_no"]), "draw_date": row["draw_date"]} for row in rows]

    def history(self, limit: int = 50, offset: int = 0) -> dict:
        if not self._has_draws():
            return {"total": 0, "items": [], "oldest_date": None, "newest_date": None}
        with self._lock:
            total_row = self.conn.execute(
                "SELECT COUNT(*), MIN(draw_date), MAX(draw_date), MIN(draw_no), MAX(draw_no) FROM draws"
            ).fetchone()
            if limit <= 0:
                rows = self.conn.execute(
                    "SELECT * FROM draws ORDER BY draw_no DESC"
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM draws ORDER BY draw_no DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return {
            "total": int(total_row[0]),
            "oldest_date": total_row[1],
            "newest_date": total_row[2],
            "oldest_draw": None if total_row[3] is None else int(total_row[3]),
            "newest_draw": None if total_row[4] is None else int(total_row[4]),
            "items": [_draw_payload(row) for row in rows],
        }

    def search_numbers(self, numbers: list[int], limit: int = 50, offset: int = 0) -> dict:
        """指定した本数字がすべて含まれた回を返す。1個以上必須。"""
        cleaned = _clean_search_numbers(numbers)
        if not cleaned:
            raise LedgerError("数字を1個以上入れてください（1〜43）")
        if not self._has_draws():
            return {
                "numbers": cleaned,
                "total": 0,
                "items": [],
                "number_stats": [],
                "exact_six": False,
            }
        clauses = []
        params: list[int] = []
        for number in cleaned:
            clauses.append(
                "(n1 = ? OR n2 = ? OR n3 = ? OR n4 = ? OR n5 = ? OR n6 = ?)"
            )
            params.extend([number] * 6)
        where = " AND ".join(clauses)
        with self._lock:
            total = int(
                self.conn.execute(f"SELECT COUNT(*) FROM draws WHERE {where}", params).fetchone()[0]
            )
            rows = self.conn.execute(
                f"SELECT * FROM draws WHERE {where} ORDER BY draw_no DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            number_stats = []
            for number in cleaned:
                one = [number] * 6
                stat = self.conn.execute(
                    """
                    SELECT COUNT(*), MAX(draw_no), MAX(draw_date)
                    FROM draws
                    WHERE n1 = ? OR n2 = ? OR n3 = ? OR n4 = ? OR n5 = ? OR n6 = ?
                    """,
                    one,
                ).fetchone()
                number_stats.append(
                    {
                        "number": number,
                        "count": int(stat[0]),
                        "last_draw_no": None if stat[1] is None else int(stat[1]),
                        "last_draw_date": stat[2],
                    }
                )
        items = []
        for row in rows:
            payload = _draw_payload(row)
            winning = set(payload["numbers"])
            matched = [n for n in cleaned if n in winning]
            payload["matched"] = matched
            payload["match_count"] = len(matched)
            items.append(payload)
        return {
            "numbers": cleaned,
            "total": total,
            "items": items,
            "number_stats": number_stats,
            "exact_six": len(cleaned) == 6,
        }

    def load_draws(self, start_date: str | None = None, end_date: str | None = None) -> list:
        if not self._has_draws():
            return []
        sql = "SELECT * FROM draws"
        params: list[str] = []
        where: list[str] = []
        if start_date:
            where.append("draw_date >= ?")
            params.append(start_date)
        if end_date:
            where.append("draw_date <= ?")
            params.append(end_date)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY draw_no"
        with self._lock:
            return list(self.conn.execute(sql, params))

    def draw_detail(self, draw_no: int) -> dict | None:
        with self._lock:
            row = self._draw_for(draw_no)
        if row is None:
            return None
        return _draw_payload(row)

    def _has_draws(self) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='draws'"
            ).fetchone()
        return row is not None

    def _draw_for(self, draw_no: int) -> sqlite3.Row | None:
        if not self._draw_table_unlocked():
            return None
        return self.conn.execute("SELECT * FROM draws WHERE draw_no=?", (draw_no,)).fetchone()

    def _draw_table_unlocked(self) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='draws'"
        ).fetchone()
        return row is not None


def judge(numbers: list[int], main: list[int], bonus: int) -> tuple[int | None, int, bool]:
    """等級、本数字の一致数、ボーナス一致。ボーナスは2等の判定だけに使う。"""
    matched = len(set(numbers) & set(main))
    bonus_hit = bonus in numbers
    if matched == 6:
        return 1, matched, bonus_hit
    if matched == 5 and bonus_hit:
        return 2, matched, bonus_hit
    if matched == 5:
        return 3, matched, bonus_hit
    if matched == 4:
        return 4, matched, bonus_hit
    if matched == 3:
        return 5, matched, bonus_hit
    return None, matched, bonus_hit


def _normalize(payload: dict) -> dict:
    try:
        draw_no = int(payload.get("draw_no"))
    except (TypeError, ValueError) as exc:
        raise LedgerError("回号を数字で入れてください") from exc
    if draw_no < 1:
        raise LedgerError("回号を数字で入れてください")

    raw_numbers = payload.get("numbers")
    if not isinstance(raw_numbers, list) or len(raw_numbers) != 6:
        raise LedgerError("本数字は6個入れてください")
    try:
        numbers = [int(value) for value in raw_numbers]
    except (TypeError, ValueError) as exc:
        raise LedgerError("本数字は1から43の整数です") from exc
    if len(set(numbers)) != 6 or any(number < 1 or number > 43 for number in numbers):
        raise LedgerError("本数字は1から43で、重複なく6個にしてください")
    numbers = sorted(numbers)

    try:
        ticket_count = int(payload.get("ticket_count"))
        unit_price = int(payload.get("unit_price"))
    except (TypeError, ValueError) as exc:
        raise LedgerError("口数と1口の金額を数字で入れてください") from exc
    if ticket_count < 1:
        raise LedgerError("口数は1以上にしてください")
    if unit_price < 0:
        raise LedgerError("1口の金額が不正です")

    purchased_on = str(payload.get("purchased_on") or "").strip()
    try:
        datetime.strptime(purchased_on, "%Y-%m-%d")
    except ValueError as exc:
        raise LedgerError("購入日は YYYY-MM-DD で入れてください") from exc

    note = str(payload.get("note") or "").strip()
    if len(note) > 200:
        raise LedgerError("メモは200文字までです")

    override = payload.get("prize_override")
    if override is None or override == "":
        prize_override = None
    else:
        try:
            prize_override = int(override)
        except (TypeError, ValueError) as exc:
            raise LedgerError("当選額は数字で入れてください") from exc
        if prize_override < 0:
            raise LedgerError("当選額は0円以上です")

    return {
        "draw_no": draw_no,
        "numbers": numbers,
        "ticket_count": ticket_count,
        "unit_price": unit_price,
        "purchased_on": purchased_on,
        "note": note,
        "prize_override": prize_override,
    }


def _field_values(fields: dict) -> tuple:
    numbers = fields["numbers"]
    return (
        fields["draw_no"],
        *numbers,
        fields["ticket_count"],
        fields["unit_price"],
        fields["purchased_on"],
        fields["note"],
        fields["prize_override"],
    )


def _present(row: sqlite3.Row, draw: sqlite3.Row | None) -> dict:
    numbers = [int(row[f"n{index}"]) for index in range(1, 7)]
    ticket_count = int(row["ticket_count"])
    unit_price = int(row["unit_price"])
    cost = ticket_count * unit_price
    grade = None
    matched = None
    bonus_hit = False
    draw_date = None
    winning = None
    if draw is not None:
        main = [int(draw[f"n{index}"]) for index in range(1, 7)]
        bonus = int(draw["bonus"])
        grade, matched, bonus_hit = judge(numbers, main, bonus)
        draw_date = draw["draw_date"]
        winning = {"numbers": main, "bonus": bonus, "draw_date": draw_date}

    override = row["prize_override"]
    if override is not None:
        prize = int(override)
        status = "手入力"
    elif draw is None:
        prize = None
        status = "未抽せん"
    elif grade is None:
        prize = 0
        status = "はずれ"
    else:
        amount = draw[f"prize{grade}_amount"]
        if amount is None:
            prize = None
            status = "金額未確定"
        else:
            prize = int(amount) * ticket_count
            status = f"{grade}等"
    profit = None if prize is None else prize - cost
    return {
        "id": int(row["id"]),
        "draw_no": int(row["draw_no"]),
        "draw_date": draw_date,
        "numbers": numbers,
        "ticket_count": ticket_count,
        "unit_price": unit_price,
        "cost": cost,
        "purchased_on": row["purchased_on"],
        "note": row["note"],
        "prize_override": None if override is None else int(override),
        "grade": grade,
        "matched": matched,
        "bonus_hit": bonus_hit,
        "status": status,
        "prize": prize,
        "profit": profit,
        "winning": winning,
    }


def _clean_search_numbers(numbers: list[int]) -> list[int]:
    seen: set[int] = set()
    cleaned: list[int] = []
    for raw in numbers:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise LedgerError("数字は1〜43の整数") from exc
        if value < 1 or value > 43:
            raise LedgerError(f"{value} は範囲外。1〜43を指定")
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
        if len(cleaned) >= 6:
            break
    return cleaned


def _draw_payload(row: sqlite3.Row) -> dict:
    keys = set(row.keys())
    prizes = {}
    for grade in range(1, 6):
        key = f"prize{grade}_amount"
        amount = row[key] if key in keys else None
        prizes[str(grade)] = None if amount is None else int(amount)
    sales = row["sales_amount"] if "sales_amount" in keys else None
    carry = row["carryover_amount"] if "carryover_amount" in keys else None
    return {
        "draw_no": int(row["draw_no"]),
        "draw_date": row["draw_date"],
        "numbers": [int(row[f"n{index}"]) for index in range(1, 7)],
        "bonus": int(row["bonus"]),
        "prizes": prizes,
        "sales_amount": None if sales is None else int(sales),
        "carryover_amount": None if carry is None else int(carry),
    }


def _cumulative(settled_oldest_first: list[dict]) -> list[dict]:
    ordered = sorted(
        settled_oldest_first,
        key=lambda item: (item["draw_date"] or "", item["draw_no"], item["id"]),
    )
    total = 0
    series = []
    for item in ordered:
        total += int(item["profit"])
        series.append({"draw_no": item["draw_no"], "profit": total})
    return series
