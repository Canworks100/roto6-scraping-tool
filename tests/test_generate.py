"""組み合わせ生成の単体テスト。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from loto6.generate import generate_combos
from loto6.parser import Draw
from loto6.storage import Store


class GenerateTests(unittest.TestCase):
    def test_hot_mode_unique_combos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "t.sqlite")
            start = date(2020, 1, 1)
            for i in range(1, 31):
                nums = [((i + j - 1) % 43) + 1 for j in range(6)]
                # 重複が出たらずらす
                seen: list[int] = []
                for n in nums:
                    while n in seen:
                        n = (n % 43) + 1
                    seen.append(n)
                bonus = next(x for x in range(1, 44) if x not in seen)
                store.save(
                    Draw(
                        draw_no=i,
                        draw_date=(start + timedelta(days=i)).isoformat(),
                        numbers=sorted(seen),
                        bonus=bonus,
                        game="loto6",
                    )
                )
            result = generate_combos(
                store,
                game="loto6",
                main_count=6,
                max_number=43,
                tickets=5,
                mode="hot",
                seed=1,
            )
            store.close()
            self.assertEqual(len(result["combos"]), 5)
            keys = [tuple(c["numbers"]) for c in result["combos"]]
            self.assertEqual(len(keys), len(set(keys)))
            for combo in result["combos"]:
                self.assertEqual(len(combo["numbers"]), 6)
                self.assertEqual(len(set(combo["numbers"])), 6)


if __name__ == "__main__":
    unittest.main()
