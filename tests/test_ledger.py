import json
import threading
import unittest
import urllib.request
from pathlib import Path

from loto6.app import _listen
from loto6.config import load_config
from loto6.ledger import Ledger, LedgerError, judge
from loto6.official import OfficialImport


class JudgeTest(unittest.TestCase):
    def test_grades(self) -> None:
        main = [1, 7, 8, 29, 40, 43]
        self.assertEqual(judge([1, 7, 8, 29, 40, 43], main, 15)[0], 1)
        self.assertEqual(judge([1, 7, 8, 29, 40, 15], main, 15)[0], 2)
        self.assertEqual(judge([1, 7, 8, 29, 40, 16], main, 15)[0], 3)
        self.assertEqual(judge([1, 7, 8, 29, 2, 3], main, 15)[0], 4)
        self.assertEqual(judge([1, 7, 8, 2, 3, 4], main, 15)[0], 5)
        self.assertIsNone(judge([2, 3, 4, 5, 6, 9], main, 15)[0])
        self.assertEqual(judge([1, 7, 2, 3, 4, 15], main, 15)[0], None)


class LedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path("/tmp/loto6-ledger-test.sqlite")
        self.path.unlink(missing_ok=True)
        self.ledger = Ledger(self.path)
        self.ledger.conn.execute(
            """
            CREATE TABLE draws (
                draw_no INTEGER PRIMARY KEY,
                draw_date TEXT,
                n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER, n6 INTEGER,
                bonus INTEGER,
                prize1_amount INTEGER, prize2_amount INTEGER, prize3_amount INTEGER,
                prize4_amount INTEGER, prize5_amount INTEGER
            )
            """
        )
        self.ledger.conn.execute(
            """
            INSERT INTO draws VALUES (2143, '2026-10-05', 1, 7, 8, 29, 40, 43, 15,
                491368200, 7695200, 358200, 7400, 1000)
            """
        )
        self.ledger.conn.commit()

    def tearDown(self) -> None:
        self.ledger.close()
        self.path.unlink(missing_ok=True)

    def test_fifth_prize_is_multiplied_and_miss_is_loss(self) -> None:
        hit = self.ledger.add_ticket(self._payload([1, 7, 8, 2, 3, 4], ticket_count=2))
        miss = self.ledger.add_ticket(self._payload([2, 3, 4, 5, 6, 9], draw_no=2143))
        self.assertEqual(hit["status"], "5等")
        self.assertEqual(hit["prize"], 2000)
        self.assertEqual(hit["profit"], 1600)
        self.assertEqual(miss["status"], "はずれ")
        self.assertEqual(miss["profit"], -200)
        summary = self.ledger.summary()
        self.assertEqual(summary["ticket_count"], 3)
        self.assertEqual(summary["purchase_total"], 600)
        self.assertEqual(summary["prize_total"], 2000)
        self.assertEqual(summary["profit"], 1400)
        self.assertEqual(summary["hit_count"], 2)
        self.assertEqual(summary["series"][-1]["profit"], 1400)

    def test_pending_draw_is_not_in_profit(self) -> None:
        self.ledger.add_ticket(self._payload([1, 2, 3, 4, 5, 6], draw_no=3000))
        summary = self.ledger.summary()
        self.assertEqual(summary["profit"], 0)
        self.assertEqual(summary["pending_cost"], 200)
        self.assertEqual(summary["purchase_total"], 200)
        self.assertEqual(self.ledger.list_tickets()[0]["status"], "未抽せん")

    def test_override_and_update_and_reject_duplicate_numbers(self) -> None:
        saved = self.ledger.add_ticket(self._payload([1, 2, 3, 4, 5, 6], draw_no=3000, prize_override=500))
        self.assertEqual(saved["status"], "手入力")
        self.assertEqual(saved["profit"], 300)
        updated = self.ledger.update_ticket(saved["id"], self._payload([1, 7, 8, 29, 40, 43]))
        self.assertEqual(updated["status"], "1等")
        with self.assertRaises(LedgerError):
            self.ledger.add_ticket(self._payload([1, 1, 2, 3, 4, 5]))
        self.ledger.delete_ticket(updated["id"])
        self.assertEqual(self.ledger.list_tickets(), [])

    def test_search_numbers_finds_subset(self) -> None:
        self.ledger.conn.execute(
            """
            INSERT INTO draws VALUES (2142, '2026-10-01', 2, 14, 20, 21, 31, 39, 36,
                NULL, 7046300, 299500, 8500, 1000)
            """
        )
        self.ledger.conn.commit()
        hit = self.ledger.search_numbers([1, 7, 8])
        self.assertEqual(hit["total"], 1)
        self.assertEqual(hit["items"][0]["draw_no"], 2143)
        self.assertEqual(hit["items"][0]["match_count"], 3)
        miss = self.ledger.search_numbers([1, 7, 2])
        self.assertEqual(miss["total"], 0)
        one = self.ledger.search_numbers([2])
        self.assertEqual(one["total"], 1)
        self.assertEqual(one["number_stats"][0]["count"], 1)

    def test_http_roundtrip(self) -> None:
        server = _listen(self.ledger, load_config(), OfficialImport())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            body = json.dumps(self._payload([1, 7, 8, 29, 2, 3])).encode()
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/tickets",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                saved = json.load(response)
            self.assertEqual(saved["status"], "4等")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/summary") as response:
                summary = json.load(response)
            self.assertEqual(summary["prize_total"], 7400)
        finally:
            server.shutdown()
            server.server_close()

    def _payload(self, numbers: list[int], draw_no: int = 2143, ticket_count: int = 1, prize_override=None) -> dict:
        return {
            "draw_no": draw_no,
            "numbers": numbers,
            "ticket_count": ticket_count,
            "unit_price": 200,
            "purchased_on": "2026-10-01",
            "note": "",
            "prize_override": prize_override,
        }


if __name__ == "__main__":
    unittest.main()
