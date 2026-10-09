"""抽せん結果ボードの数字を読む。

公開プレイヤーの画面に出る結果表（水色の表）だけを対象にする。
動画ファイルは保存しない。トークンや保護の回避はしない。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

DIGIT_W = 16
DIGIT_H = 20
# 本数字の揺れは 60 未満。次点との差が 8 未満のときは採用しない。
MAX_DISTANCE = 60
MIN_MARGIN = 8
# 金額の字は小さい。「1」は本数字より細く、距離 80・差 6 までを同じ数字とする。
AMOUNT_MAX_DISTANCE = 80
AMOUNT_MIN_MARGIN = 6
_UNREAD = object()

TEMPLATES = {
    "0": "00001111111000000001111111111000000111000011110000111000000111000111000000001110011100000000111111100000000011111110000000001111111000000000111111100000000011111110000000001111111000000000111111100000000011110110000000001111011100000000111001110000000011100011100000011100000111100111100000001111111100000000011111100000",
    "1": "00000000001111000000000011111111000000111111111100000011111111110000001111111111000000111111111100000011111111110000001111111111000000111111111100000011111111110000001111111111000000111111111100000011111111110000001111111111000000111111111100000011111111110000001111111111000000111111111100000011111111110000000011111100",
    "2": "00000111111100000001111101111100001111000011111000111000000011100111100000001111001100000000111000000000000111100000000000011110000000000011110000000000011111000000000011110000000000011110000000000011100000000000011100000000000011100000000000011110000000000011100000000000011111000000000011111111111111110111111111111111",
    "3": "00000111111100000011111001111100001110000011111001110000000111100110000000001110000000000000111000000000000111100000000000111100000000000111100000000000111100000000000000111100000000000001111000000000000011100000000000001111011000000000111111110000000011110111000000011110011111000111110000111111111110000000111111100000",
    "4": "00000000011110000000000011111000000000001111100000000001111110000000001111111000000001111111100000000111011110000000111000111000000111100011100000011100001110000011100000111000011110000111100001111110111111101111111111111111111111111111111100000000011111000000000000111000000000000011100000000000001110000000000000111000",
    "5": "00111111111111100111111111111110011111000000000001111000000000001111000000000000111100000000000011111000000000001111100000000000111111100111110011111100001111100000000000001111000000000000111100000000000011110000000000001111000000000000111111100000000011111111000000011110011110000011110000111111111110000000111111100000",
    "6": "00000001111100000000011111111100000111100011111000011100000000000111110000000000011110000000000001111000000000001111100000000000111111111111100011111110001111001111100000011111111110000000111111111000000011111111100000001111011110000000111101111000000011100011100000011110000111100011110000001111111110000000001111100000",
    "7": "11111111111111101111111111111111000000000011111100000000000111100000000000011110000000000001110000000000001111000000000000111100000000000011100000000000011110000000000001111000000000011111000000000001111100000000000111100000000000111110000000000011111000000000011111000000000001111100000000001111100000000000111110000000",
    "8": "00001111111000000011111011111000011110000011110001110000000111001111000000011110111100000001111001110000000111000111100000111100000111000111100000011111111100000011110001111000011110000001111011110000000111101111000000001111111000000000111111110000000011111111000000011110011111000111110000111111111110000000111111100000",
    "9": "00001100011000000011111001111000011110000011110011110000000111001111000000011110111100000000111011110000000011111111000000001111111100000001111111110000000111110111100001111111000111111111111100000000000111110000000000011110000000000001111000000000000111100111000000111100001111111111100000111111111100000000111111000000",
}


def _bits(text: str) -> np.ndarray:
    return np.fromiter((1 if ch == "1" else 0 for ch in text), dtype=np.uint8)


_TEMPLATE = {ch: _bits(text) for ch, text in TEMPLATES.items()}


@dataclass(frozen=True)
class BoardRead:
    numbers: tuple[int, ...]
    bonuses: tuple[int, ...]
    draw_no: int | None = None
    amounts: tuple[int | None, ...] | None = None
    carryover: int | None = None


def read_result_board(
    image: Image.Image,
    *,
    main_count: int,
    bonus_count: int,
    min_number: int,
    max_number: int,
    prize_grades: int = 0,
) -> BoardRead | None:
    """結果ボードなら本数字とボーナスを返す。それ以外の画面は None。"""
    rgb = np.asarray(image.convert("RGB"))
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        return None
    cyan = (rgb[:, :, 1] > 180) & (rgb[:, :, 2] > 180) & (rgb[:, :, 0] < 190)
    if float(cyan.mean()) < 0.2:
        return None
    white = (rgb[:, :, 0] > 210) & (rgb[:, :, 1] > 210) & (rgb[:, :, 2] > 210)
    gray = np.asarray(image.convert("L"))
    rows = _number_rows(white)
    main = _row_with_count(rows, main_count)
    if main is None:
        return None
    bonus_row = _bonus_row(rows, main[0], bonus_count)
    if bonus_row is None:
        return None
    numbers = _read_cells(gray, main[1])
    bonuses = _read_cells(gray, bonus_row)
    if numbers is None or bonuses is None:
        return None
    if not _valid(numbers, bonuses, main_count, bonus_count, min_number, max_number):
        return None
    amounts = None
    carryover = None
    if prize_grades > 0:
        parsed = _read_prize_table(gray, white, prize_grades, min_y=max(box[3] for box in bonus_row) + 4)
        if parsed is not None:
            amounts, carryover = parsed
    return BoardRead(
        numbers=tuple(numbers),
        bonuses=tuple(bonuses),
        draw_no=_read_draw_no(gray),
        amounts=amounts,
        carryover=carryover,
    )


def _valid(
    numbers: list[int],
    bonuses: list[int],
    main_count: int,
    bonus_count: int,
    min_number: int,
    max_number: int,
) -> bool:
    if len(numbers) != main_count or len(set(numbers)) != main_count:
        return False
    if len(bonuses) != bonus_count or len(set(bonuses)) != bonus_count:
        return False
    for value in (*numbers, *bonuses):
        if value < min_number or value > max_number:
            return False
    if set(numbers) & set(bonuses):
        return False
    return True


def _number_rows(white: np.ndarray) -> list[tuple[int, list[tuple[int, int, int, int]]]]:
    height = white.shape[0]
    # 数字の黒を横に埋めて、セルのある行を一塊にする。セル分割は元の白で行う。
    filled = white.copy()
    for shift in range(1, 25):
        filled[:, shift:] |= white[:, :-shift]
        filled[:, :-shift] |= white[:, shift:]
    bands: list[tuple[int, int]] = []
    start = None
    for y in range(height):
        active = _row_has_cell(filled[y])
        if active and start is None:
            start = y
        elif not active and start is not None:
            if y - start >= 28:
                bands.append((start, y - 1))
            start = None
    if start is not None and height - start >= 28:
        bands.append((start, height - 1))
    rows: list[tuple[int, list[tuple[int, int, int, int]]]] = []
    for y0, y1 in bands:
        cells = _cells_in_band(white, y0, y1)
        if cells:
            rows.append((y0, cells))
    return rows


def _row_has_cell(white_row: np.ndarray) -> bool:
    return bool(white_row.mean() > 0.08)


def _cells_in_band(white: np.ndarray, y0: int, y1: int) -> list[tuple[int, int, int, int]]:
    col = white[y0 : y1 + 1].mean(axis=0)
    borders: list[int] = []
    in_run = False
    run_start = 0
    for x, frac in enumerate(col):
        low = frac < 0.08
        if low and not in_run:
            run_start = x
            in_run = True
        elif not low and in_run:
            run_end = x - 1
            width = run_end - run_start
            if width <= 12 and run_start > 8:
                borders.append((run_start + run_end) // 2)
            elif width > 12 and run_start < 20 and run_end > 8:
                borders.append(run_end)
            in_run = False
    if in_run and run_start > 8:
        borders.append(run_start)
    cells: list[tuple[int, int, int, int]] = []
    for left, right in zip(borders, borders[1:]):
        cell_w = right - left
        if 70 <= cell_w <= 180:
            cells.append((left + 2, y0 + 2, right - 2, y1 - 2))
    return cells


def _row_with_count(
    rows: list[tuple[int, list[tuple[int, int, int, int]]]],
    count: int,
) -> tuple[int, list[tuple[int, int, int, int]]] | None:
    matched = [row for row in rows if len(row[1]) == count]
    if not matched:
        return None
    # 本数字の行は結果表の上のほうにある
    return min(matched, key=lambda row: row[0])


def _bonus_row(
    rows: list[tuple[int, list[tuple[int, int, int, int]]]],
    main_y: int,
    bonus_count: int,
) -> list[tuple[int, int, int, int]] | None:
    below = [row for row in rows if row[0] > main_y and len(row[1]) >= bonus_count]
    if not below:
        return None
    below.sort(key=lambda row: row[0])
    cells = below[0][1][:bonus_count]
    if len(cells) != bonus_count:
        return None
    return cells


def _read_cells(gray: np.ndarray, cells: list[tuple[int, int, int, int]]) -> list[int] | None:
    values: list[int] = []
    for box in cells:
        value = _read_two_digits(gray, box)
        if value is None:
            return None
        values.append(value)
    return values


def _read_two_digits(gray: np.ndarray, box: tuple[int, int, int, int]) -> int | None:
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        return None
    cell = gray[y0:y1, x0:x1]
    parts = _split_two(cell)
    if parts is None:
        return None
    chars: list[str] = []
    for part in parts:
        ch = _match_digit(part)
        if ch is None:
            return None
        chars.append(ch)
    return int("".join(chars))


def _split_two(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    ink = gray < 90
    col = ink.sum(axis=0)
    xs = np.flatnonzero(col > 0)
    if xs.size < 4:
        return None
    left = int(xs[0])
    right = int(xs[-1])
    span = right - left
    if span < 8:
        return None
    mid0 = left + span // 3
    mid1 = left + (2 * span) // 3
    split = mid0 + int(np.argmin(col[mid0 : mid1 + 1]))
    if col[split] > 2:
        return None
    return gray[:, left:split], gray[:, split + 1 : right + 1]


def _match_digit(
    gray: np.ndarray,
    *,
    max_distance: int = MAX_DISTANCE,
    min_margin: int = MIN_MARGIN,
) -> str | None:
    bits = _normalize(gray)
    if bits is None:
        return None
    ranked = sorted(
        ((int(np.count_nonzero(bits != tmpl)), ch) for ch, tmpl in _TEMPLATE.items()),
        key=lambda item: item[0],
    )
    best, ch = ranked[0]
    second = ranked[1][0]
    if best > max_distance or second - best < min_margin:
        return None
    return ch


def _read_prize_table(
    gray: np.ndarray,
    white: np.ndarray,
    prize_grades: int,
    *,
    min_y: int,
) -> tuple[tuple[int | None, ...], int | None] | None:
    """等級の当せん金額と、その次の行のキャリーオーバー。読めない画面は None。"""
    values: list[int | None] = []
    for y0, y1 in _white_bands(white):
        if y0 < min_y:
            continue
        amount = _read_amount(gray, y0, y1)
        if amount is _UNREAD:
            return None
        values.append(amount)
    if values and values[0] is None:
        values = values[1:]
    if len(values) < prize_grades:
        return None
    amounts = tuple(values[:prize_grades])
    if all(amount is None for amount in amounts):
        return None
    carry = values[prize_grades] if len(values) > prize_grades else None
    return amounts, carry


def _white_bands(white: np.ndarray) -> list[tuple[int, int]]:
    row = white.mean(axis=1)
    bands: list[tuple[int, int]] = []
    start = None
    for y, frac in enumerate(row):
        if frac > 0.12 and start is None:
            start = y
        elif frac <= 0.12 and start is not None:
            if y - start >= 28:
                bands.append((start, y - 1))
            start = None
    if start is not None and white.shape[0] - start >= 28:
        bands.append((start, white.shape[0] - 1))
    return bands


def _read_amount(gray: np.ndarray, y0: int, y1: int) -> int | None | object:
    width = gray.shape[1]
    x0 = int(width * 0.55)
    x1 = int(width * 0.97)
    if x1 <= x0 or y1 < y0:
        return None
    sub = gray[y0 : y1 + 1, x0:x1]
    chars: list[str | None] = []
    for left, top, right, bottom in _amount_blobs(sub < 80):
        if bottom - top + 1 < 14 or not 4 <= right - left + 1 <= 40:
            continue
        chars.append(
            _match_digit(
                sub[top : bottom + 1, left : right + 1],
                max_distance=AMOUNT_MAX_DISTANCE,
                min_margin=AMOUNT_MIN_MARGIN,
            )
        )
    while chars and chars[-1] is None:
        chars.pop()
    while chars and chars[0] is None:
        chars.pop(0)
    if not chars:
        return None
    if any(ch is None for ch in chars):
        return _UNREAD
    return int("".join(chars))


def _amount_blobs(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    raw: list[tuple[int, int, int, int]] = []
    ys, xs = np.where(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if seen[y, x]:
            continue
        stack = [(y, x)]
        seen[y, x] = True
        minx = maxx = x
        miny = maxy = y
        area = 0
        while stack:
            cy, cx = stack.pop()
            area += 1
            minx = min(minx, cx)
            maxx = max(maxx, cx)
            miny = min(miny, cy)
            maxy = max(maxy, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if area >= 12:
            raw.append((minx, miny, maxx, maxy))
    raw.sort()
    merged: list[list[int]] = []
    for left, top, right, bottom in raw:
        if merged and left <= merged[-1][2] + 4:
            prev = merged[-1]
            merged[-1] = [min(prev[0], left), min(prev[1], top), max(prev[2], right), max(prev[3], bottom)]
        else:
            merged.append([left, top, right, bottom])
    return [tuple(box) for box in merged]


def _normalize(gray: np.ndarray) -> np.ndarray | None:
    ink = gray < 90
    ys, xs = np.where(ink)
    if xs.size < 8:
        return None
    crop = ink[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1]
    img = Image.fromarray(np.where(crop, np.uint8(0), np.uint8(255)))
    small = np.asarray(img.resize((DIGIT_W, DIGIT_H), Image.Resampling.BOX))
    return (small < 128).astype(np.uint8).ravel()


def _read_draw_no(gray: np.ndarray) -> int | None:
    """表題の「第NNNN回」を読む。読めなければ None。"""
    height, width = gray.shape
    y0 = int(height * 0.04)
    y1 = int(height * 0.16)
    x0 = int(width * 0.28)
    x1 = int(width * 0.78)
    region = gray[y0:y1, x0:x1]
    ink = region < 70
    boxes = _ink_boxes(ink)
    digits: list[tuple[int, int, str]] = []
    for left, top, right, bottom in boxes:
        ch = _match_digit(region[top : bottom + 1, left : right + 1])
        if ch is None:
            continue
        digits.append((left, top, ch))
    if not digits:
        return None
    digits.sort(key=lambda item: (item[1], item[0]))
    lines: list[list[tuple[int, int, str]]] = []
    for left, top, ch in digits:
        if not lines or abs(top - lines[-1][0][1]) > 12:
            lines.append([(left, top, ch)])
        else:
            lines[-1].append((left, top, ch))
    best: str | None = None
    for line in lines:
        ordered = sorted(line, key=lambda item: item[0])
        text = "".join(item[2] for item in ordered)
        if text.isdigit() and 3 <= len(text) <= 4:
            if best is None or len(text) > len(best):
                best = text
    if best is None:
        return None
    return int(best)


def _ink_boxes(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    boxes: list[tuple[int, int, int, int]] = []
    ys, xs = np.where(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if seen[y, x]:
            continue
        stack = [(y, x)]
        seen[y, x] = True
        minx = maxx = x
        miny = maxy = y
        area = 0
        while stack:
            cy, cx = stack.pop()
            area += 1
            minx = min(minx, cx)
            maxx = max(maxx, cx)
            miny = min(miny, cy)
            maxy = max(maxy, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if area >= 25:
            boxes.append((minx, miny, maxx, maxy))
    return boxes
