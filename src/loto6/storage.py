"""SQLiteへの保存とCSV書き出し。種目×回号で一意。"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from loto6.parser import Draw

COLUMNS = [
    "game",
    "draw_no",
    "draw_date",
    "n1",
    "n2",
    "n3",
    "n4",
    "n5",
    "n6",
    "n7",
    "bonus",
    "bonus2",
    "prize1_count",
    "prize1_amount",
    "prize2_count",
    "prize2_amount",
    "prize3_count",
    "prize3_amount",
    "prize4_count",
    "prize4_amount",
    "prize5_count",
    "prize5_amount",
    "prize6_count",
    "prize6_amount",
    "sales_amount",
    "carryover_amount",
    "source_url",
    "fetched_at",
    "result_stage",
]


class Store:
    def __init__(self, sqlite_path: Path) -> None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = sqlite_path
        self.conn = sqlite3.connect(sqlite_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._migrate_legacy_if_needed()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS draws (
                game TEXT NOT NULL,
                draw_no INTEGER NOT NULL,
                draw_date TEXT NOT NULL,
                n1 INTEGER,
                n2 INTEGER,
                n3 INTEGER,
                n4 INTEGER,
                n5 INTEGER,
                n6 INTEGER,
                n7 INTEGER,
                bonus INTEGER NOT NULL,
                bonus2 INTEGER,
                prize1_count INTEGER,
                prize1_amount INTEGER,
                prize2_count INTEGER,
                prize2_amount INTEGER,
                prize3_count INTEGER,
                prize3_amount INTEGER,
                prize4_count INTEGER,
                prize4_amount INTEGER,
                prize5_count INTEGER,
                prize5_amount INTEGER,
                prize6_count INTEGER,
                prize6_amount INTEGER,
                sales_amount INTEGER,
                carryover_amount INTEGER,
                source_url TEXT,
                fetched_at TEXT NOT NULL,
                result_stage TEXT NOT NULL DEFAULT 'official',
                PRIMARY KEY (game, draw_no)
            )
            """
        )
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(draws)").fetchall()}
        if cols and "result_stage" not in cols:
            self.conn.execute("ALTER TABLE draws ADD COLUMN result_stage TEXT NOT NULL DEFAULT 'official'")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS missing_draws (
                game TEXT NOT NULL,
                draw_no INTEGER NOT NULL,
                reason TEXT,
                checked_at TEXT NOT NULL,
                PRIMARY KEY (game, draw_no)
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_draws_game_date ON draws(game, draw_date)")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flash_articles (
                game TEXT NOT NULL,
                draw_no INTEGER NOT NULL,
                title TEXT NOT NULL,
                lead TEXT NOT NULL,
                payload TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                PRIMARY KEY (game, draw_no)
            )
            """
        )
        self.conn.commit()

    def _migrate_legacy_if_needed(self) -> None:
        """旧 schema（draw_no 単独PK・game列なし）を検出して移す。"""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(draws)").fetchall()}
        if not cols:
            return
        if "game" in cols and "n7" in cols:
            return
        # 旧テーブルをリネームして再作成・コピー
        self.conn.execute("ALTER TABLE draws RENAME TO draws_legacy_tmp")
        if "missing_draws" in {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            miss_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(missing_draws)").fetchall()}
            if "game" not in miss_cols:
                self.conn.execute("ALTER TABLE missing_draws RENAME TO missing_draws_legacy_tmp")
        self._init_schema()
        legacy_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(draws_legacy_tmp)").fetchall()}
        select_n7 = "NULL" if "n7" not in legacy_cols else "n7"
        select_bonus2 = "NULL" if "bonus2" not in legacy_cols else "bonus2"
        select_p6c = "NULL" if "prize6_count" not in legacy_cols else "prize6_count"
        select_p6a = "NULL" if "prize6_amount" not in legacy_cols else "prize6_amount"
        self.conn.execute(
            f"""
            INSERT INTO draws (
                game, draw_no, draw_date, n1, n2, n3, n4, n5, n6, n7,
                bonus, bonus2,
                prize1_count, prize1_amount, prize2_count, prize2_amount,
                prize3_count, prize3_amount, prize4_count, prize4_amount,
                prize5_count, prize5_amount, prize6_count, prize6_amount,
                sales_amount, carryover_amount, source_url, fetched_at
            )
            SELECT
                'loto6', draw_no, draw_date, n1, n2, n3, n4, n5, n6, {select_n7},
                bonus, {select_bonus2},
                prize1_count, prize1_amount, prize2_count, prize2_amount,
                prize3_count, prize3_amount, prize4_count, prize4_amount,
                prize5_count, prize5_amount, {select_p6c}, {select_p6a},
                sales_amount, carryover_amount, source_url, fetched_at
            FROM draws_legacy_tmp
            """
        )
        self.conn.execute("DROP TABLE draws_legacy_tmp")
        if "missing_draws_legacy_tmp" in {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            self.conn.execute(
                """
                INSERT INTO missing_draws (game, draw_no, reason, checked_at)
                SELECT 'loto6', draw_no, reason, checked_at FROM missing_draws_legacy_tmp
                """
            )
            self.conn.execute("DROP TABLE missing_draws_legacy_tmp")
        self.conn.commit()

    def existing_draw_nos(self, game: str = "loto6") -> set[int]:
        rows = self.conn.execute("SELECT draw_no FROM draws WHERE game=?", (game,)).fetchall()
        return {int(row["draw_no"]) for row in rows}

    def known_missing(self, game: str = "loto6") -> set[int]:
        rows = self.conn.execute("SELECT draw_no FROM missing_draws WHERE game=?", (game,)).fetchall()
        return {int(row["draw_no"]) for row in rows}

    def save(self, draw: Draw, refresh: bool = False, *, stage: str = "official") -> bool:
        """新規なら True。既存を残すときは False。refresh のときは上書きして True。
        stage=numbers は本数字だけ。公式（official）の回は数字速報で上書きしない。"""
        row = draw.as_row()
        row["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        row["result_stage"] = stage
        if not row.get("game"):
            row["game"] = "loto6"
        game = str(row["game"])
        existing = self.get_draw(game, draw.draw_no)
        if existing is not None:
            existing_stage = existing["result_stage"] if "result_stage" in existing.keys() else "official"
            if stage == "numbers" and existing_stage == "official":
                return False
            if stage == "numbers":
                if _same_numbers(existing, draw):
                    return False
                self._update_numbers(row)
                self.conn.execute(
                    "DELETE FROM missing_draws WHERE game = ? AND draw_no = ?",
                    (game, draw.draw_no),
                )
                self.conn.commit()
                return True
            if not refresh:
                return False
        columns = COLUMNS
        placeholders = ", ".join("?" for _ in columns)
        values = [row.get(column) for column in columns]
        if existing is None:
            sql = f"""
                INSERT INTO draws ({", ".join(columns)})
                VALUES ({placeholders})
            """
        else:
            sql = f"""
                INSERT INTO draws ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(game, draw_no) DO UPDATE SET
                {", ".join(f"{column}=excluded.{column}" for column in columns if column not in ("game", "draw_no"))}
            """
        self.conn.execute(sql, values)
        self.conn.execute(
            "DELETE FROM missing_draws WHERE game = ? AND draw_no = ?",
            (game, draw.draw_no),
        )
        self.conn.commit()
        return True

    def _update_numbers(self, row: dict[str, int | str | None]) -> None:
        self.conn.execute(
            """
            UPDATE draws SET
                draw_date=?, n1=?, n2=?, n3=?, n4=?, n5=?, n6=?, n7=?,
                bonus=?, bonus2=?, source_url=?, fetched_at=?, result_stage=?
            WHERE game=? AND draw_no=?
            """,
            (
                row["draw_date"],
                row["n1"],
                row["n2"],
                row["n3"],
                row["n4"],
                row["n5"],
                row["n6"],
                row["n7"],
                row["bonus"],
                row["bonus2"],
                row["source_url"],
                row["fetched_at"],
                row["result_stage"],
                row["game"],
                row["draw_no"],
            ),
        )

    def mark_missing(self, draw_no: int, reason: str, game: str = "loto6") -> None:
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            """
            INSERT INTO missing_draws (game, draw_no, reason, checked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(game, draw_no) DO UPDATE SET reason=excluded.reason, checked_at=excluded.checked_at
            """,
            (game, draw_no, reason, checked_at),
        )
        self.conn.commit()

    def load_draws(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        game: str = "loto6",
        limit: int | None = None,
        offset: int = 0,
        newest_first: bool = False,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM draws WHERE game=?"
        params: list[object] = [game]
        if start_date:
            sql += " AND draw_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND draw_date <= ?"
            params.append(end_date)
        sql += " ORDER BY draw_no " + ("DESC" if newest_first else "ASC")
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        return list(self.conn.execute(sql, params))

    def count_draws(self, game: str = "loto6", start_date: str | None = None, end_date: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS c FROM draws WHERE game=?"
        params: list[object] = [game]
        if start_date:
            sql += " AND draw_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND draw_date <= ?"
            params.append(end_date)
        return int(self.conn.execute(sql, params).fetchone()["c"])

    def latest_draw(self, game: str = "loto6") -> sqlite3.Row | None:
        rows = self.load_draws(game=game, limit=1, newest_first=True)
        return rows[0] if rows else None

    def get_draw(self, game: str, draw_no: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM draws WHERE game=? AND draw_no=?",
            (game, draw_no),
        ).fetchone()

    def previous_draw(self, game: str, draw_no: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM draws WHERE game=? AND draw_no < ? ORDER BY draw_no DESC LIMIT 1",
            (game, draw_no),
        ).fetchone()

    def neighbor_draw_nos(self, game: str, draw_no: int) -> tuple[int | None, int | None]:
        prev_row = self.conn.execute(
            "SELECT draw_no FROM draws WHERE game=? AND draw_no < ? ORDER BY draw_no DESC LIMIT 1",
            (game, draw_no),
        ).fetchone()
        next_row = self.conn.execute(
            "SELECT draw_no FROM draws WHERE game=? AND draw_no > ? ORDER BY draw_no ASC LIMIT 1",
            (game, draw_no),
        ).fetchone()
        prev_no = None if prev_row is None else int(prev_row["draw_no"])
        next_no = None if next_row is None else int(next_row["draw_no"])
        return prev_no, next_no

    def last_main_hit(self, game: str, number: int, before_draw_no: int, main_count: int) -> sqlite3.Row | None:
        clause = " OR ".join(f"n{index}=?" for index in range(1, main_count + 1))
        params: list[object] = [game, before_draw_no, *([number] * main_count)]
        return self.conn.execute(
            f"SELECT draw_no, draw_date FROM draws WHERE game=? AND draw_no < ? AND ({clause}) ORDER BY draw_no DESC LIMIT 1",
            params,
        ).fetchone()

    def average_main_sum(self, game: str, main_count: int) -> float | None:
        expr = "+".join(f"n{index}" for index in range(1, main_count + 1))
        row = self.conn.execute(
            f"SELECT AVG({expr}) AS v FROM draws WHERE game=? AND n1 IS NOT NULL",
            (game,),
        ).fetchone()
        if row is None or row["v"] is None:
            return None
        return float(row["v"])

    def prize1_amount_rank(self, game: str, amount: int | None) -> int | None:
        if amount is None or amount <= 0:
            return None
        rows = self.conn.execute(
            """
            SELECT prize1_amount AS amount
            FROM draws
            WHERE game=? AND prize1_amount IS NOT NULL AND prize1_amount > 0
            GROUP BY prize1_amount
            ORDER BY amount DESC
            """,
            (game,),
        ).fetchall()
        for index, row in enumerate(rows, 1):
            if int(row["amount"]) == amount:
                return index
        return None

    def upsert_flash_article(self, article: dict, *, commit: bool = True) -> None:
        payload = json.dumps(article, ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO flash_articles (game, draw_no, title, lead, payload, generated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(game, draw_no) DO UPDATE SET
                title=excluded.title,
                lead=excluded.lead,
                payload=excluded.payload,
                generated_at=excluded.generated_at
            """,
            (
                article["game"],
                int(article["draw_no"]),
                article["title"],
                article["lead"],
                payload,
                article["generated_at"],
            ),
        )
        if commit:
            self.conn.commit()

    def get_flash_article_row(self, game: str, draw_no: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM flash_articles WHERE game=? AND draw_no=?",
            (game, draw_no),
        ).fetchone()

    def load_flash_article_summaries(
        self, game: str, limit: int, offset: int = 0
    ) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT a.draw_no, a.title, a.lead, a.payload, d.draw_date
                FROM flash_articles a
                JOIN draws d ON d.game = a.game AND d.draw_no = a.draw_no
                WHERE a.game = ?
                ORDER BY a.draw_no DESC
                LIMIT ? OFFSET ?
                """,
                (game, limit, offset),
            )
        )

    def missing_flash_draw_nos(self, game: str) -> list[int]:
        rows = self.conn.execute(
            """
            SELECT d.draw_no
            FROM draws d
            LEFT JOIN flash_articles a ON a.game = d.game AND a.draw_no = d.draw_no
            WHERE d.game = ? AND a.draw_no IS NULL
            ORDER BY d.draw_no
            """,
            (game,),
        ).fetchall()
        return [int(row["draw_no"]) for row in rows]

    def count_flash_articles(self, game: str) -> int:
        return int(
            self.conn.execute("SELECT COUNT(*) AS c FROM flash_articles WHERE game=?", (game,)).fetchone()["c"]
        )

    def prize_amount_rankings(self, game: str, main_count: int, limit: int = 5) -> dict:
        """当せん金額がある回だけを対象に、1〜3等の上位・下位を返す。同額は1つの順位にまとめる。"""
        result: dict[str, dict[str, list[dict]]] = {}
        for grade in (1, 2, 3):
            amount_col = f"prize{grade}_amount"
            count_col = f"prize{grade}_count"

            def pack(order: str) -> list[dict]:
                amount_rows = self.conn.execute(
                    f"""
                    SELECT {amount_col} AS amount, COUNT(*) AS n
                    FROM draws
                    WHERE game=? AND {amount_col} IS NOT NULL AND {amount_col} > 0
                    GROUP BY {amount_col}
                    ORDER BY amount {order}
                    LIMIT ?
                    """,
                    (game, limit),
                ).fetchall()
                groups = []
                for index, amount_row in enumerate(amount_rows, 1):
                    amount = int(amount_row["amount"])
                    rows = self.conn.execute(
                        f"""
                        SELECT * FROM draws
                        WHERE game=? AND {amount_col}=?
                        ORDER BY draw_no DESC
                        """,
                        (game, amount),
                    ).fetchall()
                    draws = []
                    for row in rows:
                        draw = row_to_draw(row, main_count)
                        draws.append(
                            {
                                "amount": amount,
                                "count": None if row[count_col] is None else int(row[count_col]),
                                "draw_no": draw["draw_no"],
                                "draw_date": draw["draw_date"],
                                "numbers": draw["numbers"],
                                "bonus": draw["bonus"],
                                "bonus2": draw["bonus2"],
                            }
                        )
                    groups.append({"rank": index, "amount": amount, "draw_count": len(draws), "draws": draws})
                return groups

            result[str(grade)] = {"high": pack("DESC"), "low": pack("ASC")}
        return result

    def draw_range(self, game: str = "loto6") -> tuple[int | None, int | None, str | None, str | None]:
        row = self.conn.execute(
            """
            SELECT MIN(draw_no) AS min_no, MAX(draw_no) AS max_no,
                   MIN(draw_date) AS min_date, MAX(draw_date) AS max_date
            FROM draws WHERE game=?
            """,
            (game,),
        ).fetchone()
        if row is None or row["min_no"] is None:
            return None, None, None, None
        return int(row["min_no"]), int(row["max_no"]), str(row["min_date"]), str(row["max_date"])

    def export_csv(self, csv_path: Path, game: str = "loto6") -> int:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.load_draws(game=game)
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row[column] for column in COLUMNS})
        return len(rows)

    def search_numbers(
        self,
        numbers: list[int],
        game: str = "loto6",
        main_count: int = 6,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        cleaned = sorted({int(n) for n in numbers})
        if not cleaned:
            return {"numbers": [], "total": 0, "items": [], "number_stats": [], "exact_main": False}
        cols = [f"n{i}" for i in range(1, main_count + 1)]
        or_clause = " OR ".join(f"{col} = ?" for col in cols)
        clauses = []
        params: list[object] = [game]
        for number in cleaned:
            clauses.append(f"({or_clause})")
            params.extend([number] * main_count)
        where = "game=? AND " + " AND ".join(clauses)
        total = int(self.conn.execute(f"SELECT COUNT(*) FROM draws WHERE {where}", params).fetchone()[0])
        rows = self.conn.execute(
            f"SELECT * FROM draws WHERE {where} ORDER BY draw_no DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        number_stats = []
        for number in cleaned:
            one_params = [game, *[number] * main_count]
            stat = self.conn.execute(
                f"SELECT COUNT(*), MAX(draw_no), MAX(draw_date) FROM draws WHERE game=? AND ({or_clause})",
                one_params,
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
            payload = row_to_draw(row, main_count)
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
            "exact_main": len(cleaned) == main_count,
        }


def _same_numbers(existing: sqlite3.Row, draw: Draw) -> bool:
    mains = [int(existing[f"n{i}"]) for i in range(1, 8) if existing[f"n{i}"] is not None]
    bonus2 = existing["bonus2"] if "bonus2" in existing.keys() else None
    return (
        mains == list(draw.numbers)
        and int(existing["bonus"]) == int(draw.bonus)
        and (None if bonus2 is None else int(bonus2)) == draw.bonus2
        and str(existing["draw_date"]) == str(draw.draw_date)
    )


def row_to_draw(row: sqlite3.Row, main_count: int = 6) -> dict:
    numbers = [int(row[f"n{i}"]) for i in range(1, main_count + 1) if row[f"n{i}"] is not None]
    bonus2 = row["bonus2"] if "bonus2" in row.keys() else None
    return {
        "game": row["game"] if "game" in row.keys() else "loto6",
        "draw_no": int(row["draw_no"]),
        "draw_date": row["draw_date"],
        "numbers": numbers,
        "bonus": int(row["bonus"]),
        "bonus2": None if bonus2 is None else int(bonus2),
        "sales_amount": row["sales_amount"],
        "carryover_amount": row["carryover_amount"],
        "result_stage": row["result_stage"] if "result_stage" in row.keys() else "official",
        "prizes": [
            {
                "grade": grade,
                "count": row[f"prize{grade}_count"] if f"prize{grade}_count" in row.keys() else None,
                "amount": row[f"prize{grade}_amount"] if f"prize{grade}_amount" in row.keys() else None,
            }
            for grade in range(1, 7)
        ],
    }


def migrate_legacy_file(legacy_path: Path, dest_path: Path) -> int:
    """旧 loto6.sqlite をマルチゲームDBへ取り込む。"""
    if not legacy_path.exists():
        return 0
    dest = Store(dest_path)
    src = sqlite3.connect(legacy_path)
    src.row_factory = sqlite3.Row
    cols = {row[1] for row in src.execute("PRAGMA table_info(draws)").fetchall()}
    if not cols:
        src.close()
        dest.close()
        return 0
    if "game" in cols:
        rows = src.execute("SELECT * FROM draws").fetchall()
    else:
        rows = src.execute("SELECT * FROM draws").fetchall()
    inserted = 0
    for row in rows:
        data = dict(row)
        game = data.get("game") or "loto6"
        numbers = [int(data[f"n{i}"]) for i in range(1, 8) if data.get(f"n{i}") is not None]
        from loto6.parser import Draw

        prizes = {}
        for grade in range(1, 7):
            prizes[grade] = (data.get(f"prize{grade}_count"), data.get(f"prize{grade}_amount"))
        draw = Draw(
            draw_no=int(data["draw_no"]),
            draw_date=str(data["draw_date"]),
            numbers=numbers,
            bonus=int(data["bonus"]),
            bonus2=int(data["bonus2"]) if data.get("bonus2") is not None else None,
            prizes=prizes,
            sales_amount=data.get("sales_amount"),
            carryover_amount=data.get("carryover_amount"),
            source_url=str(data.get("source_url") or ""),
            game=str(game),
        )
        if dest.save(draw, refresh=False):
            inserted += 1
    src.close()
    dest.close()
    return inserted
