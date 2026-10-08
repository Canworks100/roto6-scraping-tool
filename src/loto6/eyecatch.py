"""速報記事のアイキャッチ（OG向け SVG）。本数字は載せない。"""

from __future__ import annotations

from xml.sax.saxutils import escape


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
