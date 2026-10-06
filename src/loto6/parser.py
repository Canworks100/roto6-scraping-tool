"""当せんCSVと描画後HTMLのパース。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

ERA_BASE = {"令和": 2018, "平成": 1988, "昭和": 1925}
ZEN = "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ　"
HAN = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
GRADE_LABELS = {
    "1等": 1,
    "2等": 2,
    "3等": 3,
    "4等": 4,
    "5等": 5,
    "6等": 6,
}


class ParseError(ValueError):
    """1回分のデータを解釈できなかった。"""


@dataclass
class Draw:
    draw_no: int
    draw_date: str
    numbers: list[int]
    bonus: int
    bonus2: int | None = None
    prizes: dict[int, tuple[int | None, int | None]] = field(default_factory=dict)
    sales_amount: int | None = None
    carryover_amount: int | None = None
    source_url: str = ""
    game: str = "loto6"

    def as_row(self) -> dict[str, int | str | None]:
        row: dict[str, int | str | None] = {
            "game": self.game,
            "draw_no": self.draw_no,
            "draw_date": self.draw_date,
            "bonus": self.bonus,
            "bonus2": self.bonus2,
            "sales_amount": self.sales_amount,
            "carryover_amount": self.carryover_amount,
            "source_url": self.source_url,
        }
        for i in range(1, 8):
            row[f"n{i}"] = self.numbers[i - 1] if i <= len(self.numbers) else None
        for grade in range(1, 7):
            count, amount = self.prizes.get(grade, (None, None))
            row[f"prize{grade}_count"] = count
            row[f"prize{grade}_amount"] = amount
        return row


def zen_to_han(text: str) -> str:
    return text.translate(str.maketrans(ZEN, HAN))


def decode_body(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
        if "第" in text or "本数字" in text:
            return text
    except UnicodeDecodeError:
        pass
    return data.decode("cp932")


def parse_japanese_date(text: str) -> str:
    """和暦または西暦を YYYY-MM-DD にする。"""
    cleaned = zen_to_han(text).replace(" ", "").replace("元年", "1年")
    era = re.search(r"(令和|平成|昭和)(\d+)年(\d+)月(\d+)日", cleaned)
    if era:
        year = ERA_BASE[era.group(1)] + int(era.group(2))
        month = int(era.group(3))
        day = int(era.group(4))
        return f"{year:04d}-{month:02d}-{day:02d}"
    western = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", cleaned)
    if western:
        return f"{int(western.group(1)):04d}-{int(western.group(2)):02d}-{int(western.group(3)):02d}"
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", cleaned)
    if iso:
        return iso.group(0)
    slash = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", cleaned)
    if slash:
        return f"{int(slash.group(1)):04d}-{int(slash.group(2)):02d}-{int(slash.group(3)):02d}"
    raise ParseError(f"日付を解釈できません: {text}")


def parse_yen(text: str) -> int | None:
    cleaned = zen_to_han(text).replace(",", "").replace(" ", "")
    if "該当なし" in cleaned or cleaned == "":
        return None
    matched = re.search(r"-?\d+", cleaned)
    if not matched:
        return None
    return int(matched.group(0))


def parse_winners(text: str) -> int | None:
    cleaned = zen_to_han(text).replace(",", "").replace(" ", "")
    if "該当なし" in cleaned or cleaned == "":
        return None
    matched = re.search(r"\d+", cleaned)
    if not matched:
        return None
    return int(matched.group(0))


def _grade_of(label: str) -> int | None:
    cleaned = zen_to_han(label).strip()
    return GRADE_LABELS.get(cleaned)


def _split_csv_line(line: str) -> list[str]:
    return [part.strip() for part in line.split(",")]


def parse_draw_csv(
    data: bytes | str,
    source_url: str = "",
    *,
    game: str = "loto6",
    main_count: int = 6,
    bonus_count: int = 1,
    min_number: int = 1,
    max_number: int = 43,
    prize_grades: int = 5,
) -> Draw:
    text = decode_body(data) if isinstance(data, bytes) else data
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    lines = [zen_to_han(line) for line in text.split("\n") if line.strip()]
    if len(lines) < 4:
        raise ParseError("行数が足りません")

    draw_no = None
    draw_date = None
    numbers: list[int] = []
    bonuses: list[int] = []
    prizes: dict[int, tuple[int | None, int | None]] = {}
    sales_amount = None
    carryover_amount = None

    for line in lines:
        cols = _split_csv_line(line)
        head = cols[0]
        if head.startswith("第") and "回" in head and draw_no is None:
            matched = re.search(r"第(\d+)回", head)
            if not matched or len(cols) < 3:
                continue
            draw_no = int(matched.group(1))
            draw_date = parse_japanese_date(cols[2])
            continue
        if head == "本数字":
            numbers, bonuses = _parse_main_and_bonus_cols(cols, bonus_count)
            continue
        grade = _grade_of(head)
        if grade and len(cols) >= 3 and not cols[1].startswith("申込"):
            prizes[grade] = (parse_winners(cols[1]), parse_yen(cols[2]))
            continue
        if head == "販売実績額" and len(cols) >= 2:
            sales_amount = parse_yen(cols[1])
            continue
        if head == "キャリーオーバー" and len(cols) >= 2:
            carryover_amount = parse_yen(cols[1])

    if draw_no is None or draw_date is None or not bonuses:
        raise ParseError("回別・抽せん日・ボーナス数字のいずれかがありません")
    _validate_numbers(
        numbers,
        bonuses,
        main_count=main_count,
        min_number=min_number,
        max_number=max_number,
    )
    for grade in range(1, prize_grades + 1):
        prizes.setdefault(grade, (None, None))
    return Draw(
        draw_no=draw_no,
        draw_date=draw_date,
        numbers=numbers,
        bonus=bonuses[0],
        bonus2=bonuses[1] if len(bonuses) > 1 else None,
        prizes=prizes,
        sales_amount=sales_amount,
        carryover_amount=carryover_amount,
        source_url=source_url,
        game=game,
    )


def _parse_main_and_bonus_cols(cols: list[str], bonus_count: int) -> tuple[list[int], list[int]]:
    try:
        bonus_at = next(i for i, col in enumerate(cols) if col.startswith("ボーナス"))
    except StopIteration as exc:
        raise ParseError("ボーナス数字がありません") from exc
    numbers = [int(value) for value in cols[1:bonus_at] if re.fullmatch(r"\d+", value)]
    bonuses: list[int] = []
    for col in cols[bonus_at + 1 :]:
        if col.startswith("ボーナス"):
            continue
        if re.fullmatch(r"\d+", col):
            bonuses.append(int(col))
        if len(bonuses) >= bonus_count:
            break
    if len(bonuses) < bonus_count:
        raise ParseError(f"ボーナス数字が{bonus_count}個ありません: {cols}")
    return numbers, bonuses[:bonus_count]


def _validate_numbers(
    numbers: list[int],
    bonuses: list[int] | int,
    *,
    main_count: int = 6,
    min_number: int = 1,
    max_number: int = 43,
) -> None:
    if isinstance(bonuses, int):
        bonuses = [bonuses]
    if len(numbers) != main_count or len(set(numbers)) != main_count:
        raise ParseError(f"本数字が{main_count}個の重複なしではありません: {numbers}")
    if any(number < min_number or number > max_number for number in numbers):
        raise ParseError(f"本数字が範囲外です: {numbers}")
    for bonus in bonuses:
        if bonus < min_number or bonus > max_number or bonus in numbers:
            raise ParseError(f"ボーナス数字が不正です: {bonus}")
    if len(set(bonuses)) != len(bonuses):
        raise ParseError(f"ボーナス数字が重複しています: {bonuses}")


def parse_summary_csv(data: bytes | str) -> list[tuple[int, str]]:
    """loto6.csv（直近分の回号一覧）から (回, 日付) を新しい順で返す。"""
    text = decode_body(data) if isinstance(data, bytes) else data
    text = zen_to_han(text).replace("\r\n", "\n").replace("\r", "\n")
    found: list[tuple[int, str]] = []
    for line in text.split("\n"):
        if not line.startswith("第"):
            continue
        cols = _split_csv_line(line)
        matched = re.search(r"第(\d+)回", cols[0])
        if not matched or len(cols) < 3:
            continue
        found.append((int(matched.group(1)), parse_japanese_date(cols[2])))
    return found


def parse_html_tables(html: str, selectors: dict[str, str], source_url: str = "") -> list[Draw]:
    """月別ページをJS描画したあとの表を読む。"""
    soup = BeautifulSoup(html, "html.parser")
    draws: list[Draw] = []
    for table in soup.select(selectors["draw_table"]):
        draw_no_text = _text(table.select_one(selectors["draw_number"]))
        date_text = _text(table.select_one(selectors["draw_date"]))
        if not draw_no_text or not date_text:
            continue
        matched = re.search(r"第(\d+)回", zen_to_han(draw_no_text))
        if not matched:
            continue
        numbers = [_int_from_text(node.get_text()) for node in table.select(selectors["main_number"])]
        bonus_text = _text(table.select_one(selectors["bonus_number"]))
        bonus = _int_from_text(bonus_text)
        prizes: dict[int, tuple[int | None, int | None]] = {}
        for row in table.select(selectors["prize_row"]):
            cells = row.find_all(["th", "td"])
            if len(cells) < 3:
                continue
            grade = _grade_of(cells[0].get_text())
            if grade is None:
                continue
            prizes[grade] = (parse_winners(cells[1].get_text()), parse_yen(cells[2].get_text()))
        for grade in range(1, 6):
            prizes.setdefault(grade, (None, None))
        sales = parse_yen(_text(table.select_one(selectors["sales"])))
        carryover = parse_yen(_text(table.select_one(selectors["carryover"])))
        _validate_numbers(numbers, bonus, main_count=len(numbers) or 6)
        draws.append(
            Draw(
                draw_no=int(matched.group(1)),
                draw_date=parse_japanese_date(date_text),
                numbers=numbers,
                bonus=bonus,
                prizes=prizes,
                sales_amount=sales,
                carryover_amount=carryover,
                source_url=source_url,
            )
        )
    return draws


def parse_rakuten_lastresults(
    html: str,
    source_url: str = "",
    *,
    game: str = "loto6",
    main_count: int = 6,
    bonus_count: int = 1,
    min_number: int = 1,
    max_number: int = 43,
) -> list[Draw]:
    """楽天×宝くじの直近10回ポップアップから、本数字とボーナスだけ読む。"""
    soup = BeautifulSoup(html, "html.parser")
    draws: list[Draw] = []
    for row in soup.select("table.loto-popup-table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        head = zen_to_han(cells[0].get_text(" ", strip=True))
        matched = re.search(r"第(\d+)回", head)
        if not matched:
            continue
        try:
            draw_date = parse_japanese_date(head)
        except ParseError:
            continue
        mains = [int(node.get_text()) for node in cells[1].select("li") if re.fullmatch(r"\d+", zen_to_han(node.get_text().strip()))]
        bonuses = [int(node.get_text()) for node in cells[2].select("li") if re.fullmatch(r"\d+", zen_to_han(node.get_text().strip()))]
        if len(mains) != main_count or len(bonuses) < bonus_count:
            continue
        try:
            _validate_numbers(
                mains,
                bonuses[:bonus_count],
                main_count=main_count,
                min_number=min_number,
                max_number=max_number,
            )
        except ParseError:
            continue
        draws.append(
            Draw(
                draw_no=int(matched.group(1)),
                draw_date=draw_date,
                numbers=mains,
                bonus=bonuses[0],
                bonus2=bonuses[1] if bonus_count > 1 else None,
                prizes={grade: (None, None) for grade in range(1, 7)},
                source_url=source_url,
                game=game,
            )
        )
    draws.sort(key=lambda item: item.draw_no)
    return draws


def parse_static_backnumber_html(
    html: str,
    source_url: str = "",
    *,
    game: str = "loto6",
    main_count: int = 6,
    bonus_count: int = 1,
    min_number: int = 1,
    max_number: int = 43,
) -> list[Draw]:
    """静的バックナンバーHTML（複数回分）を読む。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.section__table.sp-only")
    if not tables:
        tables = soup.select("table.section__table")
    draws: list[Draw] = []
    for table in tables:
        fields: dict[str, str] = {}
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            key = zen_to_han(_text(cells[0])).replace(" ", "")
            value = zen_to_han(_text(cells[1]))
            if key:
                fields[key] = value
        draw_text = fields.get("回") or fields.get("回別") or ""
        date_text = fields.get("抽せん日") or fields.get("抽選日") or ""
        main_text = fields.get("本数字") or ""
        bonus_text = fields.get("ボーナス数字") or fields.get("ボーナス") or ""
        matched = re.search(r"第(\d+)回", draw_text)
        if not matched or not date_text or not main_text or not bonus_text:
            continue
        numbers = [int(value) for value in re.findall(r"\d+", main_text)][:main_count]
        bonus_nums = [int(value) for value in re.findall(r"\d+", bonus_text)][:bonus_count]
        if len(bonus_nums) < bonus_count:
            continue
        _validate_numbers(
            numbers,
            bonus_nums,
            main_count=main_count,
            min_number=min_number,
            max_number=max_number,
        )
        prizes = {grade: (None, None) for grade in range(1, 6)}
        draws.append(
            Draw(
                draw_no=int(matched.group(1)),
                draw_date=parse_japanese_date(date_text),
                numbers=numbers,
                bonus=bonus_nums[0],
                bonus2=bonus_nums[1] if len(bonus_nums) > 1 else None,
                prizes=prizes,
                source_url=source_url,
                game=game,
            )
        )
    draws.sort(key=lambda item: item.draw_no)
    return draws


def discover_archive_links(html: str, base_url: str, game: str = "loto6") -> list[str]:
    """バックナンバー索引から種目の月別・詳細URLを集める。"""
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        if not _is_game_archive(href, game):
            continue
        url = href if href.startswith("http") else base_url.rstrip("/") + "/" + href.lstrip("/")
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
    return found


def draw_numbers_from_links(urls: list[str], game: str = "loto6") -> list[int]:
    """detail.html?fromto=1701_1720&type=loto6 の回号を展開する。"""
    numbers: set[int] = set()
    type_token = f"type={game}"
    for url in urls:
        if type_token not in url or "fromto=" not in url:
            continue
        matched = re.search(r"fromto=(\d+)_(\d+)", url)
        if not matched:
            continue
        start, end = int(matched.group(1)), int(matched.group(2))
        numbers.update(range(start, end + 1))
    return sorted(numbers)


def _is_game_archive(href: str, game: str) -> bool:
    if f"type={game}" in href:
        return True
    if re.search(rf"{game}/index\.html\?year=\d+&month=\d+", href):
        return True
    # ミニロト早期は loto0xxx.html、ロト6は loto6xxxx.html、ロト7は loto7xxxx.html
    if game == "miniloto" and re.search(r"/backnumber/loto\d+\.html", href) and "loto6" not in href and "loto7" not in href:
        return True
    if game != "miniloto" and re.search(rf"/backnumber/{game}\d+\.html", href):
        return True
    return False


def _text(node) -> str:
    if node is None:
        return ""
    return node.get_text(" ", strip=True)


def _int_from_text(text: str) -> int:
    matched = re.search(r"\d+", zen_to_han(text))
    if not matched:
        raise ParseError(f"数字がありません: {text}")
    return int(matched.group(0))
