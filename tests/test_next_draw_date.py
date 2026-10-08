import unittest

from loto6.games import next_draw_date


class NextDrawDateTest(unittest.TestCase):
    def test_loto6_monday_to_thursday(self) -> None:
        self.assertEqual(next_draw_date("loto6", "2026-10-05"), "2026-10-08")

    def test_loto6_thursday_to_monday(self) -> None:
        self.assertEqual(next_draw_date("loto6", "2026-10-08"), "2026-10-12")

    def test_loto7_friday_to_friday(self) -> None:
        self.assertEqual(next_draw_date("loto7", "2026-10-02"), "2026-10-09")

    def test_miniloto_tuesday_to_tuesday(self) -> None:
        self.assertEqual(next_draw_date("miniloto", "2026-09-29"), "2026-10-06")
