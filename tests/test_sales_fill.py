import tempfile
import unittest
from pathlib import Path

from loto6.config import load_config
from loto6.parser import Draw
from loto6.sales_fill import fill_missing_sales, parse_sales_page
from loto6.storage import Store

FIXTURES = Path(__file__).parent / "fixtures"


class SalesPageTests(unittest.TestCase):
    def test_loto6_page_matches_official_style_amount(self) -> None:
        html = (FIXTURES / "sales_loto6_2144.html").read_text(encoding="utf-8")
        read = parse_sales_page(html, main_count=6, bonus_count=1)
        self.assertEqual(read.draw_no, 2144)
        self.assertEqual(read.numbers, [5, 6, 11, 25, 31, 32])
        self.assertEqual(read.bonuses, [15])
        self.assertEqual(read.sales_amount, 1_270_263_600)

    def test_loto7_page(self) -> None:
        html = (FIXTURES / "sales_loto7_697.html").read_text(encoding="utf-8")
        read = parse_sales_page(html, main_count=7, bonus_count=2)
        self.assertEqual(read.draw_no, 697)
        self.assertEqual(read.numbers, [1, 6, 12, 23, 28, 32, 36])
        self.assertEqual(read.bonuses, [31, 34])
        self.assertEqual(read.sales_amount, 1_852_655_100)

    def test_miniloto_page(self) -> None:
        html = (FIXTURES / "sales_miniloto_1407.html").read_text(encoding="utf-8")
        read = parse_sales_page(html, main_count=5, bonus_count=1)
        self.assertEqual(read.draw_no, 1407)
        self.assertEqual(read.numbers, [7, 13, 15, 26, 28])
        self.assertEqual(read.bonuses, [4])
        self.assertEqual(read.sales_amount, 536_744_200)


class SalesKeepTests(unittest.TestCase):
    def test_refresh_without_sales_keeps_existing_amount(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loto.sqlite"
            store = Store(path)
            prizes = {grade: (1, 1000) for grade in range(1, 6)}
            store.save(
                Draw(
                    draw_no=2141,
                    draw_date="2026-09-28",
                    numbers=[14, 15, 22, 32, 37, 41],
                    bonus=1,
                    prizes=prizes,
                    sales_amount=1_528_752_600,
                    carryover_amount=0,
                    game="loto6",
                )
            )
            changed = dict(prizes)
            changed[5] = (2, 1000)
            store.save(
                Draw(
                    draw_no=2141,
                    draw_date="2026-09-28",
                    numbers=[14, 15, 22, 32, 37, 41],
                    bonus=1,
                    prizes=changed,
                    sales_amount=None,
                    carryover_amount=0,
                    game="loto6",
                ),
                refresh=True,
            )
            row = store.get_draw("loto6", 2141)
            assert row is not None
            self.assertEqual(int(row["sales_amount"]), 1_528_752_600)
            self.assertEqual(int(row["prize5_count"]), 2)
            store.close()

    def test_present_sales_is_not_fetched_again(self) -> None:
        config = load_config()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loto.sqlite"
            store = Store(path)
            prizes = {grade: (1, 1000) for grade in range(1, 6)}
            store.save(
                Draw(
                    draw_no=2144,
                    draw_date="2026-10-08",
                    numbers=[5, 6, 11, 25, 31, 32],
                    bonus=15,
                    prizes=prizes,
                    sales_amount=1_270_263_600,
                    carryover_amount=0,
                    game="loto6",
                )
            )
            result = fill_missing_sales(config, "loto6", store)
            self.assertEqual(result["checked"], 0)
            self.assertEqual(result["draw_nos"], [])
            store.close()


if __name__ == "__main__":
    unittest.main()
