"""宝くじ公式サイトの購入履歴から、ロト6の口を読み取る。"""

from __future__ import annotations

import re
from datetime import date

from loto6.parser import parse_japanese_date

DRAW_IN_TITLE = re.compile(r"ロト\s*[6６]\s*[（(]\s*第\s*(\d+)\s*回\s*[）)]")
PURCHASED_AT = re.compile(r"購入日時\s*[:：]\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
# 2桁を先に取る。さもないと 32 が 3 と 2 に割れる。
BALL = r"(?:[1-3]\d|4[0-3]|[1-9])"
SIX = rf"({BALL}(?:[ \t　]+{BALL}){{5}})"
ENTRY_LINE = re.compile(
    rf"(?:^|\n)\s*[A-E]\s+{SIX}[\s\S]{{0,60}}?購入口数\s*(\d+)\s*口",
    re.MULTILINE,
)
FALLBACK_ENTRY = re.compile(rf"{SIX}[\s\S]{{0,40}}?購入口数\s*(\d+)\s*口")


def parse_detail_page(text: str) -> list[dict]:
    """購入履歴詳細ページから、申込数字ごとの口を返す。抽せん数字は入れない。"""
    text = text.replace("\u3000", " ")
    if not DRAW_IN_TITLE.search(text):
        return []
    if "申込数字" not in text:
        return []
    draw_no = int(DRAW_IN_TITLE.search(text).group(1))
    purchased_on = _purchase_date(text)
    section = text
    start = text.find("申込数字")
    if start >= 0:
        section = text[start:]
    end_markers = ["お支払い方法", "合計　購入口数", "合計 購入口数", "再購入"]
    end = len(section)
    for marker in end_markers:
        pos = section.find(marker)
        if 0 <= pos < end:
            end = pos
    section = section[:end]
    found: list[dict] = []
    seen: set[tuple[int, ...]] = set()
    for match in ENTRY_LINE.finditer(section):
        numbers = [int(value) for value in match.group(1).split()]
        ticket_count = int(match.group(2))
        key = tuple(sorted(numbers))
        if len(key) != 6 or len(set(key)) != 6 or key in seen:
            continue
        seen.add(key)
        found.append(
            {
                "draw_no": draw_no,
                "numbers": list(numbers),
                "ticket_count": ticket_count,
                "purchased_on": purchased_on,
            }
        )
    if not found:
        for match in FALLBACK_ENTRY.finditer(section):
            numbers = [int(value) for value in match.group(1).split()]
            ticket_count = int(match.group(2))
            key = tuple(sorted(numbers))
            if len(key) != 6 or len(set(key)) != 6 or key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "draw_no": draw_no,
                    "numbers": list(numbers),
                    "ticket_count": ticket_count,
                    "purchased_on": purchased_on,
                }
            )
    return found


def parse_purchase_page(text: str) -> list[dict]:
    """詳細ページならそこを読む。一覧だけで数字がある場合の予備。"""
    detail = parse_detail_page(text)
    if detail:
        return detail
    return _parse_flat_list(text)


def list_has_loto6(text: str) -> bool:
    return bool(DRAW_IN_TITLE.search(text.replace("\u3000", " ")))


def _parse_flat_list(text: str) -> list[dict]:
    text = text.replace("\u3000", " ")
    marks = list(re.finditer(r"第\s*(\d+)\s*回", text))
    current = None
    found: list[dict] = []
    seen: set[tuple[int, tuple[int, ...]]] = set()
    number_group = re.compile(rf"(?<!\d){SIX}(?!\d)")
    for index, mark in enumerate(marks):
        next_start = marks[index + 1].start() if index + 1 < len(marks) else min(len(text), mark.end() + 900)
        label = text[max(0, mark.start() - 80) : mark.end() + 40]
        body = text[mark.end() : next_start]
        if re.search(r"ロト\s*[6６]", label + body):
            current = "loto6"
        elif re.search(r"ロト\s*[7７]|ミニロト|ナンバーズ|ビンゴ", label + body):
            current = "other"
        if current != "loto6":
            continue
        draw_no = int(mark.group(1))
        purchased_on = _date_in(body) or _date_in(label)
        for group in number_group.finditer(body):
            if "購入口数" not in body[group.end() : group.end() + 30] and "口" not in body[group.end() : group.end() + 12]:
                # 一覧に数字が並ぶだけのときは口数1とみなす
                ticket_count = 1
            else:
                count_match = re.search(r"(\d+)\s*口", body[group.end() : group.end() + 24])
                ticket_count = int(count_match.group(1)) if count_match else 1
            numbers = [int(value) for value in group.group(1).split()]
            key = (draw_no, tuple(sorted(numbers)))
            if key in seen or len(set(numbers)) != 6:
                continue
            seen.add(key)
            found.append(
                {
                    "draw_no": draw_no,
                    "numbers": numbers,
                    "ticket_count": ticket_count,
                    "purchased_on": purchased_on,
                }
            )
    return found


def _purchase_date(text: str) -> str | None:
    matched = PURCHASED_AT.search(text)
    if matched:
        return f"{int(matched.group(1)):04d}-{int(matched.group(2)):02d}-{int(matched.group(3)):02d}"
    return _date_in(text)


def _date_in(window: str) -> str | None:
    matched = re.search(r"(?:令和|平成|昭和)?\d+年\d+月\d+日|\d{4}[/-]\d{1,2}[/-]\d{1,2}", window)
    if not matched:
        return None
    raw = matched.group(0).replace("/", "-")
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", raw):
            year, month, day = raw.split("-")
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return parse_japanese_date(matched.group(0))
    except ValueError:
        return None


def fallback_date(draw_date: str | None) -> str:
    if draw_date:
        return draw_date
    return date.today().isoformat()
