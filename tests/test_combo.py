import math
import tempfile
import unittest
from pathlib import Path

from loto6.analyze import combo_payload, theoretical_prizes
from loto6.parser import Draw
from loto6.storage import Store


def _draw(game: str, draw_no: int, date: str, numbers: list[int], bonus: int) -> Draw:
    prizes = {grade: (1, 1000) for grade in range(1, 7)}
    return Draw(
        draw_no=draw_no,
        draw_date=date,
        numbers=numbers,
        bonus=bonus,
        bonus2=None,
        prizes=prizes,
        game=game,
    )


class ComboTest(unittest.TestCase):
    def test_loto6_first_prize_ways(self) -> None:
        items = theoretical_prizes(43, 6, 1, 5)
        self.assertEqual(items[0]["total"], math.comb(43, 6))
        self.assertEqual(items[0]["ways"], 1)
        self.assertEqual(items[1]["ways"], 6)
        self.assertEqual(items[2]["ways"], 216)

    def test_combo_counts_matches(self) -> None:
        path = Path(tempfile.gettempdir()) / "loto-combo-test.sqlite"
        path.unlink(missing_ok=True)
        store = Store(path)
        store.save(_draw("loto6", 1, "2026-01-02", [1, 2, 4, 15, 21, 32], 7))
        store.save(_draw("loto6", 2, "2026-01-09", [1, 2, 4, 8, 9, 10], 11))
        rows = store.load_draws(game="loto6")
        payload = combo_payload(
            rows,
            [1, 2, 4, 15, 21, 32],
            {
                "_game": "loto6",
                "prize_grades": 5,
                "lottery": {
                    "min_number": 1,
                    "max_number": 43,
                    "main_count": 6,
                    "bonus_count": 1,
                    "prize_grades": 5,
                    "game": "loto6",
                },
            },
            "all",
        )
        self.assertEqual(payload["exact_count"], 1)
        hist = {row["match_count"]: row["draws"] for row in payload["match_hist"]}
        self.assertEqual(hist[6], 1)
        self.assertEqual(hist[3], 1)
        self.assertEqual(payload["shape"]["even_count"], 3)
        self.assertEqual(payload["shape"]["odd_count"], 3)
        self.assertEqual(payload["shape"]["sum"], 75)
        self.assertIn(payload["diagnosis"]["verdict"], {"いい感じ", "バランスがよい", "標準的", "やや偏っている", "個性の強い並び"})
        self.assertTrue(payload["diagnosis"]["points"])
        store.close()
        path.unlink(missing_ok=True)
