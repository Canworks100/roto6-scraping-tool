"""購入シミュレーターの単体テスト。"""

from __future__ import annotations

import random
import unittest

from loto6.simu import DETAIL_THRESHOLD, SimuError, max_tickets_for, run_simu, unit_price_for


def _loto6() -> dict:
    return {
        "id": "loto6",
        "label": "ロト6",
        "min_number": 1,
        "max_number": 43,
        "main_count": 6,
        "bonus_count": 1,
        "prize_grades": 5,
        "unit_price": 200,
        "simu_grade1_base": 200_000_000,
        "simu_prizes": {2: 10_000_000, 3: 300_000, 4: 6800, 5: 1000},
    }


def _loto7() -> dict:
    return {
        "id": "loto7",
        "label": "ロト7",
        "min_number": 1,
        "max_number": 37,
        "main_count": 7,
        "bonus_count": 2,
        "prize_grades": 6,
        "unit_price": 300,
        "simu_grade1_base": 400_000_000,
        "simu_prizes": {2: 10_000_000, 3: 1_000_000, 4: 50_000, 5: 7000, 6: 1000},
    }


class SimuTests(unittest.TestCase):
    def test_unit_price(self) -> None:
        self.assertEqual(unit_price_for(_loto6()), 200)
        self.assertEqual(unit_price_for(_loto7()), 300)
        self.assertEqual(max_tickets_for(_loto6()), 1_000_000)
        self.assertEqual(max_tickets_for(_loto7()), 666_666)

    def test_grade1_split_two_winners(self) -> None:
        g = _loto6()
        # 抽せんを固定: 本 1-6、ボーナス 7
        rng = random.Random(0)

        def fixed_draw(_game, rng=None):
            return [1, 2, 3, 4, 5, 6], [7]

        import loto6.simu as simu_mod

        original = simu_mod.draw_winning
        simu_mod.draw_winning = fixed_draw  # type: ignore[assignment]
        try:
            result = run_simu(
                g,
                tickets=[[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]],
                random_count=0,
                carryover_amount=0,
                rng=rng,
            )
        finally:
            simu_mod.draw_winning = original  # type: ignore[assignment]
        self.assertEqual(result["by_grade"][0]["grade"], 1)
        self.assertEqual(result["by_grade"][0]["count"], 2)
        each = 200_000_000 // 2
        self.assertEqual(result["by_grade"][0]["amount_each"], each)
        self.assertEqual(result["prize_total"], each * 2)
        self.assertEqual(result["cost"], 400)
        self.assertEqual(len(result["details"]), 2)

    def test_random_only(self) -> None:
        result = run_simu(
            _loto6(),
            tickets=[],
            random_count=10,
            carryover_amount=1_000_000,
            rng=random.Random(1),
        )
        self.assertEqual(result["ticket_count"], 10)
        self.assertEqual(result["hand_count"], 0)
        self.assertEqual(result["random_count"], 10)
        self.assertEqual(result["cost"], 2000)
        self.assertEqual(result["carryover_amount"], 1_000_000)
        self.assertEqual(result["grade1_pool"], 201_000_000)
        self.assertFalse(result["winners_only"])

    def test_hybrid_and_winners_only(self) -> None:
        result = run_simu(
            _loto6(),
            tickets=[[1, 2, 3, 4, 5, 6]],
            random_count=DETAIL_THRESHOLD,
            carryover_amount=0,
            rng=random.Random(2),
        )
        self.assertEqual(result["ticket_count"], DETAIL_THRESHOLD + 1)
        self.assertTrue(result["winners_only"])
        for row in result["details"]:
            self.assertIsNotNone(row["grade"])

    def test_over_limit(self) -> None:
        with self.assertRaises(SimuError):
            run_simu(
                _loto6(),
                tickets=[],
                random_count=1_000_001,
                carryover_amount=0,
                rng=random.Random(3),
            )

    def test_loto7_price(self) -> None:
        result = run_simu(
            _loto7(),
            tickets=[[1, 2, 3, 4, 5, 6, 7]],
            random_count=0,
            carryover_amount=None,
            rng=random.Random(4),
        )
        self.assertEqual(result["unit_price"], 300)
        self.assertEqual(result["cost"], 300)


if __name__ == "__main__":
    unittest.main()
