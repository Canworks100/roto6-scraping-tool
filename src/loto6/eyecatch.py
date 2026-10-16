"""速報記事のアイキャッチ（OG向け SVG / PNG）。本数字は載せない。"""

from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

# 画像に使う文字だけを抜き出した Noto Sans JP（OFL）。文言を足したら作り直す
FONT_PATH = Path(__file__).resolve().parent / "fonts" / "NotoSansJP-subset.ttf"


def format_date_short(iso: str | None) -> str:
    if not iso:
        return ""
    parts = str(iso)[:10].split("-")
    if len(parts) != 3:
        return str(iso)[:10]
    return f"{int(parts[1])}月{int(parts[2])}日"


def eyecatch_svg(
    *,
    label: str,
    draw_no: int,
    draw_date: str | None,
    numbers: list[int] | None = None,
    bonus: int | None = None,
    bonus2: int | None = None,
) -> str:
    """1200×630。回号と日付のみ。当選番号は出さない（numbers 等は互換のため受けるが使わない）。"""
    del numbers, bonus, bonus2
    padded = f"{draw_no:04d}"
    date_s = format_date_short(draw_date)
    headline = f"第{padded}回 {label}"
    sub = "当選番号速報"
    date_line = f"{date_s}の抽選結果" if date_s else "抽選結果"
    font = "Hiragino Sans, Noto Sans JP, Yu Gothic, Meiryo, sans-serif"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="{escape(headline)} {escape(sub)}">
  <rect width="1200" height="630" fill="#ffffff"/>
  <rect x="0" y="0" width="1200" height="630" fill="none" stroke="#000000" stroke-width="8"/>
  <rect x="72" y="88" width="160" height="14" fill="#eeff00"/>
  <text x="72" y="160" font-family="{font}" font-size="36" font-weight="700" fill="#000000">LOTO アナリティクス</text>
  <text x="72" y="300" font-family="{font}" font-size="68" font-weight="700" fill="#000000">{escape(headline)}</text>
  <text x="72" y="380" font-family="{font}" font-size="44" font-weight="600" fill="#000000">{escape(sub)}</text>
  <rect x="72" y="408" width="96" height="10" fill="#eeff00"/>
  <text x="72" y="470" font-family="{font}" font-size="32" font-weight="500" fill="#555555">{escape(date_line)}</text>
  <text x="72" y="560" font-family="{font}" font-size="28" font-weight="500" fill="#555555">結果は記事本文で</text>
</svg>
"""


def _eyecatch_lines(label: str, draw_no: int, draw_date: str | None) -> tuple[str, str, str]:
    date_s = format_date_short(draw_date)
    return (
        f"第{draw_no:04d}回 {label}",
        "当選番号速報",
        f"{date_s}の抽選結果" if date_s else "抽選結果",
    )


def eyecatch_png(*, label: str, draw_no: int, draw_date: str | None) -> bytes:
    """eyecatch_svg と同じ見た目の 1200×630 PNG（検索結果・SNS で SVG が使えない所向け）。"""
    from PIL import Image, ImageDraw, ImageFont

    scale = 2  # 2倍で描いて縮小し、文字の輪郭をなめらかにする

    def s(v: float) -> int:
        return round(v * scale)

    def font(size: int, weight: str) -> ImageFont.FreeTypeFont:
        f = ImageFont.truetype(str(FONT_PATH), s(size))
        f.set_variation_by_name(weight)
        return f

    headline, sub, date_line = _eyecatch_lines(label, draw_no, draw_date)
    accent = (0xEE, 0xFF, 0x00)
    ink = (0, 0, 0)
    muted = (0x55, 0x55, 0x55)
    im = Image.new("RGB", (s(1200), s(630)), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, s(1200) - 1, s(630) - 1), outline=ink, width=s(8))
    d.rectangle((s(72), s(88), s(72 + 160), s(88 + 14)), fill=accent)
    # SVG の y は文字のベースライン
    d.text((s(72), s(160)), "LOTO アナリティクス", font=font(36, "Bold"), fill=ink, anchor="ls")
    d.text((s(72), s(300)), headline, font=font(68, "Bold"), fill=ink, anchor="ls")
    d.text((s(72), s(380)), sub, font=font(44, "Bold"), fill=ink, anchor="ls")
    d.rectangle((s(72), s(408), s(72 + 96), s(408 + 10)), fill=accent)
    d.text((s(72), s(470)), date_line, font=font(32, "Medium"), fill=muted, anchor="ls")
    d.text((s(72), s(560)), "結果は記事本文で", font=font(28, "Medium"), fill=muted, anchor="ls")
    im = im.resize((1200, 630), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
