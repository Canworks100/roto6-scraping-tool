import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from loto6.notify import _payload_for, alert
from loto6.parser import Draw
from loto6.publish import _assert_www_readable
from loto6.storage import Store, _same_official


class WwwReadableTest(unittest.TestCase):
    def test_rejects_700_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.html"
            index.write_text("<!doctype html><title>x</title>", encoding="utf-8")
            os.chmod(root, 0o700)
            os.chmod(index, 0o644)
            with self.assertRaises(RuntimeError):
                _assert_www_readable(root)

    def test_accepts_755_and_644(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.html"
            index.write_text("<!doctype html><title>x</title>", encoding="utf-8")
            os.chmod(root, 0o755)
            os.chmod(index, 0o644)
            _assert_www_readable(root)


class NotifyTest(unittest.TestCase):
    def test_discord_payload(self) -> None:
        payload = _payload_for(
            "https://discord.com/api/webhooks/1/abc",
            "hello",
            "#vps-監視",
        )
        self.assertIn("content", payload)
        self.assertNotIn("text", payload)
        self.assertIn("#vps-監視", payload["content"])

    def test_slack_payload(self) -> None:
        payload = _payload_for("https://hooks.slack.com/services/x", "hello", "#vps-監視")
        self.assertIn("text", payload)

    def test_alert_without_env(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(alert("ping"))


class OfficialSameTest(unittest.TestCase):
    def test_refresh_noop_when_same(self) -> None:
        path = Path("/tmp/loto-same-official-test.sqlite")
        path.unlink(missing_ok=True)
        store = Store(path)
        try:
            draw = Draw(
                draw_no=1,
                draw_date="2026-01-01",
                numbers=[1, 2, 3, 4, 5, 6],
                bonus=7,
                prizes={1: (1, 100), 2: (2, 50), 3: (3, 10), 4: (4, 5), 5: (5, 1)},
                carryover_amount=0,
                sales_amount=None,
                source_url="https://example.test",
                game="loto6",
            )
            self.assertTrue(store.save(draw, stage="official"))
            self.assertFalse(store.save(draw, refresh=True, stage="official"))
            richer = Draw(
                draw_no=1,
                draw_date="2026-01-01",
                numbers=[1, 2, 3, 4, 5, 6],
                bonus=7,
                prizes={1: (1, 200), 2: (2, 50), 3: (3, 10), 4: (4, 5), 5: (5, 1)},
                carryover_amount=0,
                sales_amount=None,
                source_url="https://example.test",
                game="loto6",
            )
            self.assertTrue(store.save(richer, refresh=True, stage="official"))
            row = store.get_draw("loto6", 1)
            self.assertEqual(int(row["prize1_amount"]), 200)
            self.assertTrue(_same_official(row, richer))
        finally:
            store.close()
            path.unlink(missing_ok=True)


class RakutenFixturePrizesTest(unittest.TestCase):
    def test_month_fixture_has_grades_and_carry(self) -> None:
        from loto6.parser import parse_rakuten_month_html

        html = (Path(__file__).parent / "fixtures" / "rakuten_month_loto6.html").read_text(
            encoding="utf-8"
        )
        draws = parse_rakuten_month_html(html, source_url="https://example.test/month")
        self.assertEqual(draws[-1].prizes[1], (1, 491_368_200))
        self.assertEqual(draws[0].carryover_amount, 234_869_815)
        self.assertIsNone(draws[-1].sales_amount)

    def test_miniloto_month_bonus_in_parentheses(self) -> None:
        from loto6.parser import parse_rakuten_month_html

        html = (Path(__file__).parent / "fixtures" / "rakuten_month_miniloto.html").read_text(
            encoding="utf-8"
        )
        draws = parse_rakuten_month_html(
            html,
            source_url="https://example.test/mini",
            game="miniloto",
            main_count=5,
            bonus_count=1,
            min_number=1,
            max_number=31,
            prize_grades=4,
        )
        self.assertEqual([d.draw_no for d in draws], [1402, 1403])
        self.assertEqual(draws[0].numbers, [1, 4, 20, 25, 29])
        self.assertEqual(draws[0].bonus, 22)
        self.assertEqual(draws[0].prizes[1], (7, 23_075_100))
        self.assertEqual(draws[0].prizes[4], (50_177, 1000))


if __name__ == "__main__":
    unittest.main()
