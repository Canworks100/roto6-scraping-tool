import unittest
from pathlib import Path

from loto6.analyze import analyze, render_summary
from loto6.config import load_config
from loto6.parser import (
    Draw,
    discover_archive_links,
    draw_numbers_from_links,
    parse_draw_csv,
    parse_html_tables,
    parse_japanese_date,
    parse_rakuten_lastresults,
    parse_static_backnumber_html,
    parse_summary_csv,
)
from loto6.storage import Store

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = load_config()


class ParserTest(unittest.TestCase):
    def test_reiwa_and_heisei_dates(self) -> None:
        self.assertEqual(parse_japanese_date("令和8年9月28日"), "2026-09-28")
        self.assertEqual(parse_japanese_date("平成28年10月6日"), "2016-10-06")
        self.assertEqual(parse_japanese_date("令和元年5月7日"), "2019-05-07")
        self.assertEqual(parse_japanese_date("第2143回 2026/10/05"), "2026-10-05")

    def test_draw_with_first_prize(self) -> None:
        draw = parse_draw_csv((FIXTURES / "draw_2141.csv").read_bytes())
        self.assertEqual(draw.draw_no, 2141)
        self.assertEqual(draw.draw_date, "2026-09-28")
        self.assertEqual(draw.numbers, [14, 15, 22, 32, 37, 41])
        self.assertEqual(draw.bonus, 1)
        self.assertEqual(draw.prizes[1], (1, 450730500))
        self.assertEqual(draw.sales_amount, 1528752600)
        self.assertEqual(draw.carryover_amount, 0)

    def test_draw_without_first_prize(self) -> None:
        draw = parse_draw_csv((FIXTURES / "draw_1000.csv").read_text(encoding="utf-8"))
        self.assertEqual(draw.draw_date, "2015-09-07")
        self.assertEqual(draw.prizes[1], (None, None))
        self.assertEqual(draw.prizes[4], (13791, 9800))
        self.assertEqual(draw.carryover_amount, 268345233)

    def test_html_table(self) -> None:
        html = (FIXTURES / "table_2141.html").read_text(encoding="utf-8")
        draws = parse_html_tables(html, CONFIG["selectors"])
        self.assertEqual(len(draws), 1)
        self.assertEqual(draws[0].draw_no, 2141)
        self.assertEqual(draws[0].bonus, 1)
        self.assertEqual(draws[0].prizes[1], (1, 450730500))
        self.assertEqual(draws[0].sales_amount, 1528752600)

    def test_archive_links(self) -> None:
        html = """
        <a href="/takarakuji/check/loto/loto6/index.html?year=2026&month=9">ロト6</a>
        <a href="/takarakuji/check/loto/backnumber/detail.html?fromto=2021_2038&type=loto6">第2021回〜第2038回</a>
        <a href="/takarakuji/check/loto/backnumber/detail.html?fromto=1_20&type=loto7">ロト7</a>
        <a href="/takarakuji/check/loto/backnumber/loto60001.html">第1回</a>
        """
        links = discover_archive_links(html, "https://www.mizuhobank.co.jp")
        self.assertEqual(len(links), 3)
        numbers = draw_numbers_from_links(links)
        self.assertEqual(numbers[0], 2021)
        self.assertEqual(numbers[-1], 2038)
        self.assertEqual(len(numbers), 18)

    def test_summary_csv(self) -> None:
        text = "A52\n第2143回ロト6,数字選択式全国自治宝くじ,令和8年10月5日,大阪\n"
        self.assertEqual(parse_summary_csv(text), [(2143, "2026-10-05")])

    def test_static_backnumber_html(self) -> None:
        html = """
        <table class="section__table sp-only">
          <tr><th>回</th><td>第1回</td></tr>
          <tr><th>抽せん日</th><td>2000年10月5日</td></tr>
          <tr><th>本数字</th><td>02 08 10 13 27 30</td></tr>
          <tr><th>ボーナス数字</th><td>39</td></tr>
        </table>
        """
        draws = parse_static_backnumber_html(html, source_url="test")
        self.assertEqual(len(draws), 1)
        self.assertEqual(draws[0].draw_no, 1)
        self.assertEqual(draws[0].draw_date, "2000-10-05")
        self.assertEqual(draws[0].numbers, [2, 8, 10, 13, 27, 30])
        self.assertEqual(draws[0].bonus, 39)

    def test_rakuten_lastresults(self) -> None:
        html = (FIXTURES / "rakuten_lastresults_loto6.html").read_text(encoding="utf-8")
        draws = parse_rakuten_lastresults(html, source_url="https://example.test/loto6")
        self.assertEqual([d.draw_no for d in draws], [2142, 2143])
        self.assertEqual(draws[-1].numbers, [1, 7, 8, 29, 40, 43])
        self.assertEqual(draws[-1].bonus, 15)
        self.assertEqual(draws[-1].draw_date, "2026-10-05")
        self.assertEqual(draws[-1].prizes[1], (None, None))


class StorageAndAnalysisTest(unittest.TestCase):
    def test_save_is_idempotent_and_analysis_runs(self) -> None:
        path = Path("/tmp/loto6-test.sqlite")
        path.unlink(missing_ok=True)
        store = Store(path)
        first = _sample(1, "2026-09-01", [1, 2, 3, 4, 5, 6], 7)
        second = _sample(2, "2026-09-04", [1, 2, 3, 4, 5, 8], 9)
        self.assertTrue(store.save(first))
        self.assertFalse(store.save(first))
        self.assertTrue(store.save(second))
        self.assertEqual(len(store.load_draws()), 2)
        result = analyze(store.load_draws(), CONFIG)
        text = render_summary(result)
        self.assertIn("開催回数: 2", text)
        top = result["pairs"].iloc[0]
        self.assertEqual((int(top.number_a), int(top.number_b)), (1, 2))
        self.assertEqual(int(top["count"]), 2)
        store.close()
        path.unlink(missing_ok=True)

    def test_numbers_stage_does_not_overwrite_official(self) -> None:
        path = Path("/tmp/loto6-stage-test.sqlite")
        path.unlink(missing_ok=True)
        store = Store(path)
        official = _sample(10, "2026-09-01", [1, 2, 3, 4, 5, 6], 7)
        self.assertTrue(store.save(official, stage="official"))
        numbers = Draw(
            draw_no=10,
            draw_date="2026-09-01",
            numbers=[9, 10, 11, 12, 13, 14],
            bonus=8,
            prizes={grade: (None, None) for grade in range(1, 6)},
            game="loto6",
        )
        self.assertFalse(store.save(numbers, stage="numbers"))
        row = store.get_draw("loto6", 10)
        assert row is not None
        self.assertEqual(int(row["n1"]), 1)
        self.assertEqual(row["result_stage"], "official")
        store.close()
        path.unlink(missing_ok=True)


def _sample(draw_no: int, draw_date: str, numbers: list[int], bonus: int) -> Draw:
    prizes = {grade: (1, 1000) for grade in range(1, 6)}
    return Draw(
        draw_no=draw_no,
        draw_date=draw_date,
        numbers=numbers,
        bonus=bonus,
        prizes=prizes,
        sales_amount=100,
        carryover_amount=0,
    )


if __name__ == "__main__":
    unittest.main()
