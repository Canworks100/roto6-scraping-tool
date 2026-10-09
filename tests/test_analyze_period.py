import tempfile
import unittest
from pathlib import Path

from loto6.analyze import analyze, parse_period, to_payload
from loto6.parser import Draw
from loto6.storage import Store


def _draw(game: str, draw_no: int, date: str, numbers: list[int], bonus: int, bonus2: int | None = None) -> Draw:
    prizes = {grade: (1, 1000) for grade in range(1, 7)}
    return Draw(
        draw_no=draw_no,
        draw_date=date,
        numbers=numbers,
        bonus=bonus,
        bonus2=bonus2,
        prizes=prizes,
        game=game,
    )


class PeriodAnalyzeTest(unittest.TestCase):
    def test_parse_period(self) -> None:
        self.assertEqual(parse_period("all", None), "all")
        self.assertEqual(parse_period(None, 10), "years10")
        self.assertEqual(parse_period(None, 5), "years5")
        with self.assertRaises(ValueError):
            parse_period("nope", None)

    def test_loto7_bonus2_and_odd_even_rows(self) -> None:
        path = Path(tempfile.gettempdir()) / "loto-analyze-test.sqlite"
        path.unlink(missing_ok=True)
        store = Store(path)
        store.save(_draw("loto7", 1, "2026-01-02", [1, 2, 3, 4, 5, 6, 7], 8, 9))
        store.save(_draw("loto7", 2, "2026-01-09", [1, 2, 10, 11, 12, 13, 14], 15, 16))
        rows = store.load_draws(game="loto7")
        result = analyze(
            rows,
            {
                "_game": "loto7",
                "lottery": {
                    "min_number": 1,
                    "max_number": 37,
                    "main_count": 7,
                    "bonus_count": 2,
                },
                "analysis": {"top_pairs": 30, "top_triples": 20},
            },
        )
        freq = result["frequency"]
        row1 = freq[freq["number"] == 1].iloc[0]
        self.assertEqual(int(row1["count"]), 2)
        row8 = freq[freq["number"] == 8].iloc[0]
        self.assertEqual(int(row8["bonus_count"]), 1)
        row9 = freq[freq["number"] == 9].iloc[0]
        self.assertEqual(int(row9["bonus_count"]), 1)
        odd = result["odd_even"]
        self.assertEqual(len(odd), 8)
        self.assertEqual(int(odd["draws"].sum()), 2)
        payload = to_payload(result, "all")
        self.assertEqual(payload["period"], "all")
        self.assertEqual(payload["meta"]["draw_count"], 2)
        summary = {item["key"]: item["draws"] for item in payload["follow"]["summary"]}
        self.assertEqual(summary["any"] + summary["none"], 1)
        self.assertEqual(summary["any"], 1)
        by1 = next(r for r in payload["follow"]["by_number"] if r["number"] == 1)
        self.assertEqual(by1["with_prev"], 1)
        self.assertEqual(by1["streak2"], 1)
        store.close()
        path.unlink(missing_ok=True)

    def test_triples_carry_latest_draw_and_other_numbers(self) -> None:
        path = Path(tempfile.gettempdir()) / "loto-analyze-triples-test.sqlite"
        path.unlink(missing_ok=True)
        store = Store(path)
        store.save(_draw("loto6", 1, "2026-01-01", [1, 2, 3, 4, 5, 6], 7))
        store.save(_draw("loto6", 2, "2026-01-05", [1, 2, 3, 10, 11, 12], 13))
        store.save(_draw("loto6", 3, "2026-01-08", [7, 8, 9, 20, 21, 22], 23))
        result = analyze(
            store.load_draws(game="loto6"),
            {"_game": "loto6", "lottery": {"min_number": 1, "max_number": 43, "main_count": 6, "bonus_count": 1}},
        )
        top = to_payload(result, "all")["triples_high"][0]
        self.assertEqual((top["number_a"], top["number_b"], top["number_c"]), (1, 2, 3))
        self.assertEqual(top["count"], 2)
        self.assertEqual(top["last_draw_no"], 2)
        self.assertEqual(top["last_draw_date"], "2026-01-05")
        self.assertEqual(top["others"], [10, 11, 12])
        store.close()
        path.unlink(missing_ok=True)
