import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from loto6.live_board import TEMPLATES, BoardRead, read_result_board
from loto6.live_watch import parse_backnumber, parse_live_watch, settle
from loto6.parser import Draw
from loto6.rakuten_collect import _note_live_mismatch
from loto6.storage import Store

DIGIT_H = 20
DIGIT_W = 16


def _stamp(canvas: np.ndarray, digit: str, x: int, y: int, scale: int = 3) -> None:
    grid = np.fromiter((int(ch) for ch in TEMPLATES[digit]), dtype=np.uint8).reshape(DIGIT_H, DIGIT_W)
    for row in range(DIGIT_H):
        for col in range(DIGIT_W):
            color = (0, 0, 0) if grid[row, col] else (255, 255, 255)
            canvas[
                y + row * scale : y + (row + 1) * scale,
                x + col * scale : x + (col + 1) * scale,
            ] = color


def _amount_band(canvas: np.ndarray, top: int, text: str | None) -> None:
    canvas[top : top + 46, 700:1240] = (255, 255, 255)
    if not text:
        return
    scale = 2
    digit_w = DIGIT_W * scale
    x = 760
    for ch in text:
        _stamp(canvas, ch, x, top + 3, scale)
        x += digit_w + 8


def _board(pairs: list[str], bonuses: list[str]) -> Image.Image:
    canvas = np.full((720, 1280, 3), (100, 220, 220), dtype=np.uint8)
    scale = 3
    digit_w = DIGIT_W * scale
    gap = 10
    pad = 12
    cell_w = pad * 2 + digit_w * 2 + gap
    cell_h = DIGIT_H * scale + pad * 2

    def paint_row(values: list[str], top: int, left: int) -> None:
        for index, text in enumerate(values):
            x0 = left + index * (cell_w + 6)
            canvas[top : top + cell_h, x0 : x0 + cell_w] = (255, 255, 255)
            _stamp(canvas, text[0], x0 + pad, top + pad, scale)
            _stamp(canvas, text[1], x0 + pad + digit_w + gap, top + pad, scale)

    paint_row(pairs, 180, 80)
    paint_row(bonuses, 180 + cell_h + 16, 80)
    return Image.fromarray(canvas)


class BoardReadTests(unittest.TestCase):
    def test_reads_stamped_board(self) -> None:
        image = _board(["02", "03", "04", "05", "06", "07"], ["08"])
        found = read_result_board(image, main_count=6, bonus_count=1, min_number=1, max_number=43)
        self.assertEqual(found, BoardRead((2, 3, 4, 5, 6, 7), (8,)))

    def test_rejects_plain_frame(self) -> None:
        image = Image.fromarray(np.zeros((720, 1280, 3), dtype=np.uint8))
        self.assertIsNone(read_result_board(image, main_count=6, bonus_count=1, min_number=1, max_number=43))

    def test_rejects_duplicate(self) -> None:
        image = _board(["02", "02", "04", "05", "06", "07"], ["08"])
        self.assertIsNone(read_result_board(image, main_count=6, bonus_count=1, min_number=1, max_number=43))


class CatalogTests(unittest.TestCase):
    def test_backnumber_and_live_caption(self) -> None:
        html = """
        <h3 id="loto6"></h3>
        <tr><td class="num-area">第2144回</td><td>2026年10月8日</td>
        <td><a href="https://api01-platform.stream.co.jp/apiservice/plt3/abc">視聴する</a></td></tr>
        <h3 id="mini_loto"></h3>
        """
        rows = parse_backnumber(html)["loto6"]
        self.assertEqual(rows[0]["draw_no"], 2144)
        self.assertEqual(rows[0]["draw_date"], "2026-10-08")
        live = '<a href="https://api01-platform.stream.co.jp/apiservice/plt3/xyz">再生</a><div>ロト６第2145回</div>'
        url, draw_no = parse_live_watch(live, "loto6")
        self.assertEqual(draw_no, 2145)
        self.assertTrue(url and url.endswith("xyz"))


class SettleTests(unittest.TestCase):
    def test_needs_one_repeated_reading(self) -> None:
        a = BoardRead((1, 2, 3, 4, 5, 6), (7,))
        b = BoardRead((1, 2, 3, 4, 5, 8), (9,))
        self.assertEqual(settle([a, a, a], 3), a)
        self.assertIsNone(settle([a, a, a, b, b, b], 3))
        self.assertIsNone(settle([a, a], 3))

    def test_publish_needs_the_same_amounts(self) -> None:
        rich = BoardRead((1, 2, 3, 4, 5, 6), (7,), amounts=(200, 5700), carryover=300)
        other = BoardRead((1, 2, 3, 4, 5, 6), (7,), amounts=(200, 5800), carryover=300)
        plain = BoardRead((1, 2, 3, 4, 5, 6), (7,))
        self.assertEqual(settle([rich, rich, rich], 3, require_prizes=True), rich)
        self.assertIsNone(settle([rich, rich, rich, other, other, other], 3, require_prizes=True))
        self.assertIsNone(settle([plain, plain, plain], 3, require_prizes=True))


class PrizeAmountTests(unittest.TestCase):
    def test_reads_grade_amounts_and_carry(self) -> None:
        image = _board(["02", "03", "04", "05", "06", "07"], ["08"])
        canvas = np.asarray(image).copy()
        _amount_band(canvas, 430, None)
        _amount_band(canvas, 490, "200")
        _amount_band(canvas, 550, "5700")
        _amount_band(canvas, 610, "300")
        found = read_result_board(
            Image.fromarray(canvas),
            main_count=6,
            bonus_count=1,
            min_number=1,
            max_number=43,
            prize_grades=2,
        )
        assert found is not None
        self.assertEqual(found.numbers, (2, 3, 4, 5, 6, 7))
        self.assertEqual(found.amounts, (200, 5700))
        self.assertEqual(found.carryover, 300)


class LiveStoreTests(unittest.TestCase):
    def test_live_does_not_overwrite_official_and_mismatch_notifies(self) -> None:
        path = Path("/tmp/loto-live-stage.sqlite")
        path.unlink(missing_ok=True)
        store = Store(path)
        official = Draw(
            draw_no=10,
            draw_date="2026-09-01",
            numbers=[1, 2, 3, 4, 5, 6],
            bonus=7,
            prizes={grade: (1, 1000) for grade in range(1, 6)},
            game="loto6",
        )
        self.assertTrue(store.save(official, stage="official"))
        live = Draw(
            draw_no=10,
            draw_date="2026-09-01",
            numbers=[8, 9, 10, 11, 12, 13],
            bonus=14,
            prizes={grade: (None, None) for grade in range(1, 6)},
            game="loto6",
        )
        self.assertFalse(store.save(live, stage="live"))
        fresh = Draw(
            draw_no=11,
            draw_date="2026-09-04",
            numbers=[8, 9, 10, 11, 12, 13],
            bonus=14,
            prizes={grade: (None, None) for grade in range(1, 6)},
            game="loto6",
        )
        self.assertTrue(store.save(fresh, stage="live"))
        rakuten = Draw(
            draw_no=11,
            draw_date="2026-09-04",
            numbers=[1, 2, 3, 4, 5, 6],
            bonus=7,
            prizes={grade: (1, 1000) for grade in range(1, 6)},
            game="loto6",
        )
        with patch("loto6.notify.alert", return_value=True) as alert:
            _note_live_mismatch(store, "loto6", rakuten)
            _note_live_mismatch(store, "loto6", rakuten)
        alert.assert_called_once()
        self.assertIn("第11回", alert.call_args.args[0])
        store.close()
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
