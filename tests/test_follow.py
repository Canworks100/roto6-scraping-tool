import unittest

import pandas as pd

from loto6.analyze import _follow


def _frame(rows: list[tuple[int, list[int]]]) -> pd.DataFrame:
    data = []
    for draw_no, numbers in rows:
        row = {"draw_no": draw_no, "draw_date": f"2026-01-{draw_no:02d}"}
        for i, n in enumerate(numbers, start=1):
            row[f"n{i}"] = n
        data.append(row)
    return pd.DataFrame(data)


class FollowAnalyzeTest(unittest.TestCase):
    def test_include_streak2_streak3(self) -> None:
        # 1→2: 1が続く → 含む・2連続
        # 2→3: 1が3回続く → 含む・3連続
        # 3→4: 重なりなし → 含まない
        frame = _frame(
            [
                (1, [1, 2, 3, 4, 5, 6]),
                (2, [1, 7, 8, 9, 10, 11]),
                (3, [1, 12, 13, 14, 15, 16]),
                (4, [20, 21, 22, 23, 24, 25]),
            ]
        )
        follow = _follow(frame, 6, 1, 25)
        summary = {item["key"]: item for item in follow["summary"]}
        self.assertEqual(summary["any"]["draws"], 2)
        self.assertEqual(summary["none"]["draws"], 1)
        self.assertEqual(summary["streak2"]["draws"], 1)
        self.assertEqual(summary["streak3"]["draws"], 1)
        by1 = next(r for r in follow["by_number"] if r["number"] == 1)
        self.assertEqual(by1["without_prev"], 0)
        self.assertEqual(by1["with_prev"], 2)
        self.assertEqual(by1["streak2"], 1)
        self.assertEqual(by1["streak3"], 1)
        self.assertAlmostEqual(by1["with_prev_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
