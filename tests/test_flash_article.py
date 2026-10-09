import unittest
from pathlib import Path

from loto6.flash_article import build_article, ensure_missing_articles, list_articles, refresh_articles
from loto6.parser import Draw
from loto6.storage import Store

GAME = {
    "id": "loto6",
    "label": "ロト6",
    "main_count": 6,
    "max_number": 43,
    "min_number": 1,
    "prize_grades": 5,
}


def _draw(
    draw_no: int,
    date: str,
    numbers: list[int],
    bonus: int,
    *,
    prize1: tuple[int | None, int | None] = (1, 200_000_000),
    carry: int = 0,
) -> Draw:
    prizes = {grade: (10, 1000) for grade in range(2, 6)}
    prizes[1] = prize1
    return Draw(
        draw_no=draw_no,
        draw_date=date,
        numbers=numbers,
        bonus=bonus,
        prizes=prizes,
        sales_amount=1_000_000,
        carryover_amount=carry,
        game="loto6",
    )


class FlashArticleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path("/tmp/loto-flash-test.sqlite")
        self.path.unlink(missing_ok=True)
        self.store = Store(self.path)
        self.store.save(_draw(1, "2026-01-05", [1, 2, 3, 10, 20, 30], 7, prize1=(None, None), carry=50_000_000))
        self.store.save(_draw(2, "2026-01-08", [1, 8, 9, 15, 22, 40], 4, prize1=(2, 210_000_000)))
        self.store.save(_draw(3, "2026-01-12", [5, 8, 16, 21, 33, 41], 2, prize1=(1, 400_000_000)))

    def tearDown(self) -> None:
        self.store.close()
        self.path.unlink(missing_ok=True)

    def test_one_article_per_draw(self) -> None:
        article = build_article(self.store, GAME, 2)
        assert article is not None
        self.assertEqual(article["draw_no"], 2)
        self.assertIn("第0002回", article["title"])
        self.assertIn("2口", article["title"])
        self.assertIn("ロト6第0002回は", article["lead"])
        self.assertIn("連番", " ".join(article["observations"]))
        self.assertEqual(article["item"]["numbers"], [1, 8, 9, 15, 22, 40])
        self.assertEqual(article["prev_draw_no"], 1)
        self.assertEqual(article["next_draw_no"], 3)

    def test_no_first_prize_title(self) -> None:
        article = build_article(self.store, GAME, 1)
        assert article is not None
        self.assertIn("1等なし", article["title"])
        self.assertIn("キャリーは", article["lead"])

    def test_drought_and_overlap(self) -> None:
        article = build_article(self.store, GAME, 3)
        assert article is not None
        joined = " ".join(article["observations"])
        self.assertIn("08", joined)
        self.assertIn("重なった", joined)

    def test_refresh_overwrites(self) -> None:
        first = refresh_articles(self.store, GAME, [2])
        self.assertEqual(first, 1)
        row = self.store.get_flash_article_row("loto6", 2)
        assert row is not None
        old_at = row["generated_at"]
        again = refresh_articles(self.store, GAME, [2])
        self.assertEqual(again, 1)
        row2 = self.store.get_flash_article_row("loto6", 2)
        assert row2 is not None
        self.assertEqual(row2["title"], row["title"])
        self.assertGreaterEqual(row2["generated_at"], old_at)

    def test_unknown_draw(self) -> None:
        self.assertIsNone(build_article(self.store, GAME, 99))

    def test_ensure_missing_and_list(self) -> None:
        self.assertEqual(self.store.count_flash_articles("loto6"), 0)
        made = ensure_missing_articles(self.store, GAME)
        self.assertEqual(made, 3)
        self.assertEqual(ensure_missing_articles(self.store, GAME), 0)
        page = list_articles(self.store, GAME, limit=10, offset=0)
        self.assertEqual(page["total"], 3)
        self.assertEqual(len(page["items"]), 3)
        self.assertEqual(page["items"][0]["draw_no"], 3)

    def test_numbers_only_does_not_claim_no_winner(self) -> None:
        draw = Draw(
            draw_no=4,
            draw_date="2026-01-15",
            numbers=[2, 5, 11, 18, 27, 33],
            bonus=9,
            prizes={grade: (None, None) for grade in range(1, 6)},
            game="loto6",
        )
        self.assertTrue(self.store.save(draw, stage="numbers"))
        article = build_article(self.store, GAME, 4)
        assert article is not None
        self.assertNotIn("1等なし", article["title"])
        self.assertNotIn("1等なし", article["lead"])
        self.assertIn("02・05・11・18・27・33", article["title"])
        self.assertIn("本数字は", article["lead"])
        self.assertIn("速報（当せん金額は確定後に追記）", article["lead"])
        self.assertEqual(article["carry_text"], "")
        official = _draw(4, "2026-01-15", [2, 5, 11, 18, 27, 33], 9, prize1=(1, 300_000_000))
        self.assertTrue(self.store.save(official, refresh=True, stage="official"))
        updated = build_article(self.store, GAME, 4)
        assert updated is not None
        self.assertIn("1等", updated["title"])
        self.assertNotIn("1等なし", updated["title"])


if __name__ == "__main__":
    unittest.main()
