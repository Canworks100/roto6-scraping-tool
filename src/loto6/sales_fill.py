"""販売実績だけを公開結果ページから補う。番号が一致した回だけ書く。"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from loto6.client import FetchError
from loto6.games import get_game
from loto6.parser import ParseError, parse_yen, zen_to_han
from loto6.storage import Store

logger = logging.getLogger("loto6")

SALES_URL = {
    "loto6": "https://loto6.jp/databases/resultsearch/{draw_no}",
    "loto7": "https://loto7.jp/databases/resultsearch/{draw_no}",
    "miniloto": "https://www.luckydayloto.com/miniloto/draw/{draw_no}/",
}
# これより前は販売実績のページが無い回がある。直近の欠けだけを見る。
SALES_FLOOR = {"loto6": 461, "loto7": 1, "miniloto": 521}
LOOKBACK = 40
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


@dataclass(frozen=True)
class SalesRead:
    draw_no: int
    numbers: list[int]
    bonuses: list[int]
    sales_amount: int


def parse_sales_page(html: str, *, main_count: int, bonus_count: int) -> SalesRead:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if heading is None:
        raise ParseError("見出しがありません")
    matched = re.search(r"第(\d+)回", zen_to_han(heading.get_text(" ", strip=True)))
    if not matched:
        raise ParseError("回号がありません")
    draw_no = int(matched.group(1))
    if soup.select_one("table.resultsearch"):
        numbers, bonuses, sales = _parse_resultsearch(soup, bonus_count)
    else:
        numbers, bonuses, sales = _parse_luckyday(soup, main_count, bonus_count)
    if len(numbers) != main_count or len(bonuses) != bonus_count or sales is None:
        raise ParseError(f"販売実績を読めません: numbers={numbers} bonuses={bonuses} sales={sales}")
    return SalesRead(draw_no=draw_no, numbers=numbers, bonuses=bonuses, sales_amount=sales)


def fill_missing_sales(config: dict, game: str, store: Store) -> dict[str, int | list[int]]:
    """直近で販売実績が空の回だけ埋める。番号が違うページは書かない。"""
    game_def = get_game(config, game)
    main_count = int(game_def["main_count"])
    bonus_count = int(game_def["bonus_count"])
    latest = store.latest_draw(game)
    if latest is None:
        return {"filled": 0, "failed": 0, "checked": 0, "draw_nos": []}
    floor = max(int(latest["draw_no"]) - LOOKBACK, SALES_FLOOR.get(game, 1))
    missing = store.draw_nos_missing_sales(game, floor)
    filled = failed = 0
    filled_nos: list[int] = []
    for index, draw_no in enumerate(missing):
        if index:
            time.sleep(1)
        try:
            html = _fetch(SALES_URL[game].format(draw_no=draw_no))
            read = parse_sales_page(html, main_count=main_count, bonus_count=bonus_count)
        except (FetchError, ParseError, requests.RequestException) as exc:
            failed += 1
            logger.warning("[%s] 販売実績 第%s回を読めません: %s", game, draw_no, exc)
            continue
        row = store.get_draw(game, draw_no)
        if read.draw_no != draw_no or row is None or not _same_numbers(row, read, main_count, bonus_count):
            failed += 1
            logger.error("[%s] 販売実績 第%s回は番号が一致しないので書きません", game, draw_no)
            continue
        if store.set_sales_amount(game, draw_no, read.sales_amount):
            filled += 1
            filled_nos.append(draw_no)
            logger.info("[%s] 販売実績 第%s回 %s円", game, draw_no, read.sales_amount)
    return {"filled": filled, "failed": failed, "checked": len(missing), "draw_nos": filled_nos}


def _fetch(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": _UA}, timeout=30)
    if response.status_code != 200 or not response.text:
        raise FetchError(f"HTTP {response.status_code} {url}")
    return response.text


def _parse_resultsearch(soup: BeautifulSoup, bonus_count: int) -> tuple[list[int], list[int], int | None]:
    table = soup.select_one("table.resultsearch")
    if table is None:
        raise ParseError("結果表がありません")
    rows = _table_rows(table)
    numbers: list[int] = []
    bonuses: list[int] = []
    sales: int | None = None
    index = 0
    while index < len(rows):
        labels, values = rows[index]
        label = labels[0] if labels else ""
        if label == "本数字" and not values:
            index += 1
            if index < len(rows):
                numbers = _digits(rows[index][1])
        elif label.startswith("ボーナス") and not values:
            index += 1
            if index < len(rows):
                bonuses = _digits(rows[index][1])[:bonus_count]
        elif label.startswith("ボーナス"):
            bonuses = _digits(values)[:bonus_count]
        elif label == "販売実績額" and values:
            sales = parse_yen(values[0])
        index += 1
    return numbers, bonuses, sales


def _parse_luckyday(soup: BeautifulSoup, main_count: int, bonus_count: int) -> tuple[list[int], list[int], int | None]:
    tables = soup.select("table")
    if len(tables) < 2:
        raise ParseError("結果表がありません")
    number_rows = _table_rows(tables[0])
    digits: list[int] = []
    for _labels, values in number_rows:
        digits.extend(_digits(values))
    numbers = digits[:main_count]
    bonuses = digits[main_count : main_count + bonus_count]
    sales: int | None = None
    for tr in tables[1].select("tr"):
        cells = [zen_to_han(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if cells and cells[0] == "販売実績額":
            sales = parse_yen(cells[-1])
    return numbers, bonuses, sales


def _table_rows(table) -> list[tuple[list[str], list[str]]]:
    rows: list[tuple[list[str], list[str]]] = []
    for tr in table.select("tr"):
        labels: list[str] = []
        values: list[str] = []
        for cell in tr.find_all(["th", "td"]):
            text = zen_to_han(cell.get_text(" ", strip=True))
            if cell.name == "th":
                labels.append(text)
            else:
                values.append(text)
        rows.append((labels, values))
    return rows


def _digits(values: list[str]) -> list[int]:
    found: list[int] = []
    for value in values:
        if re.fullmatch(r"\d+", value):
            found.append(int(value))
    return found


def _same_numbers(row, read: SalesRead, main_count: int, bonus_count: int) -> bool:
    numbers = [int(row[f"n{i}"]) for i in range(1, main_count + 1)]
    bonuses = [int(row["bonus"])]
    if bonus_count > 1 and row["bonus2"] is not None:
        bonuses.append(int(row["bonus2"]))
    return sorted(numbers) == sorted(read.numbers) and sorted(bonuses) == sorted(read.bonuses)
