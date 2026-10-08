import unittest

from loto6.eyecatch import eyecatch_svg


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


if __name__ == "__main__":
    unittest.main()
