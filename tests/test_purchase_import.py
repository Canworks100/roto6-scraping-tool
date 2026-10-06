import unittest

from loto6.purchase_import import list_has_loto6, parse_detail_page, parse_purchase_page

DETAIL = """
購入履歴詳細
購入日時： 2026/10/05 12:37
ロト6（第2143回）
抽せん日 2026/10/05
1口 200円
宝くじの結果
５等 2口
抽せん数字
本数字
1 7 8 29 40 43
ボーナス数字
15
申込数字
お気に入り数字に登録
A
1 2 4 15 21 32
購入口数 1口
ハズレ
B
2 14 26 30 39 43
購入口数 1口
ハズレ
C
5 10 18 28 37 38
購入口数 1口
ハズレ
D
7 8 10 25 28 29
購入口数 1口
５等	1,000円
E
1 7 8 18 33 35
購入口数 1口
５等	1,000円
合計　購入口数 5口	1,000円
お支払い方法
クレジットカード決済
"""

LIST_ONLY = """
購入履歴
購入済み
ロト6（第2143回）
抽せん日 2026/10/05
1口 200円 購入口数 5口 購入金額 1,000円
詳細を見る
ロト6（第2142回）
詳細を見る
"""


class PurchaseParseTest(unittest.TestCase):
    def test_detail_reads_entries_not_winning_numbers(self) -> None:
        items = parse_detail_page(DETAIL)
        self.assertEqual(len(items), 5)
        self.assertEqual(items[0]["draw_no"], 2143)
        self.assertEqual(items[0]["purchased_on"], "2026-10-05")
        self.assertEqual(items[0]["numbers"], [1, 2, 4, 15, 21, 32])
        self.assertEqual(items[3]["numbers"], [7, 8, 10, 25, 28, 29])
        self.assertTrue(all(item["ticket_count"] == 1 for item in items))
        winning = [1, 7, 8, 29, 40, 43]
        self.assertFalse(any(item["numbers"] == winning for item in items))

    def test_list_without_numbers_is_empty_but_detectable(self) -> None:
        self.assertTrue(list_has_loto6(LIST_ONLY))
        self.assertEqual(parse_purchase_page(LIST_ONLY), [])
        self.assertEqual(parse_detail_page(LIST_ONLY), [])


if __name__ == "__main__":
    unittest.main()
