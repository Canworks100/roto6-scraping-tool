import importlib.util
import unittest

from loto6.eyecatch import FONT_PATH, _eyecatch_lines, eyecatch_png, eyecatch_svg


class EyecatchTest(unittest.TestCase):
    def test_svg_has_round_not_winning_numbers(self) -> None:
        svg = eyecatch_svg(
            label="ロト6",
            draw_no=2143,
            draw_date="2026-10-05",
            numbers=[1, 7, 8, 29, 40, 43],
            bonus=15,
        )
        self.assertIn('width="1200"', svg)
        self.assertIn("第2143回", svg)
        self.assertIn("ロト6", svg)
        self.assertIn("当選番号速報", svg)
        self.assertIn("#eeff00", svg)
        self.assertIn("#ffffff", svg)
        self.assertIn("#000000", svg)
        self.assertNotIn("#c74c0a", svg)
        self.assertNotIn("#0d1e30", svg)
        self.assertNotIn(">01<", svg)
        self.assertNotIn(">07<", svg)
        self.assertNotIn(">15<", svg)
        self.assertTrue(svg.strip().startswith("<?xml"))

    def test_png_size(self) -> None:
        png = eyecatch_png(label="ロト6", draw_no=2146, draw_date="2026-10-15")
        self.assertTrue(png.startswith(b"\x89PNG"))
        # 幅・高さは IHDR に入っている
        self.assertEqual(int.from_bytes(png[16:20], "big"), 1200)
        self.assertEqual(int.from_bytes(png[20:24], "big"), 630)

    @unittest.skipUnless(importlib.util.find_spec("fontTools"), "fontTools が無い")
    def test_font_has_every_glyph(self) -> None:
        # 抜き出したフォントに無い文字は豆腐になるので、使う文字をすべて確かめる
        from fontTools.ttLib import TTFont

        cmap = TTFont(FONT_PATH).getBestCmap()
        texts = ["LOTO アナリティクス", "結果は記事本文で", "抽選結果"]
        for label in ("ロト6", "ロト7", "ミニロト"):
            texts.extend(_eyecatch_lines(label, 1234, "2026-12-31"))
            texts.extend(_eyecatch_lines(label, 5678, "2026-01-09"))
        missing = {ch for text in texts for ch in text if ord(ch) not in cmap}
        self.assertEqual(missing, set())



if __name__ == "__main__":
    unittest.main()
