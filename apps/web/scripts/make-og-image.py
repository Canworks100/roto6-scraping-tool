"""OGP 画像（public/og-image.png, 1200x630）を作る。

使い方:
  python apps/web/scripts/make-og-image.py [フォントのパス]

フォントは Noto Sans JP の可変フォント（NotoSansJP-VF.ttf）を使う。
省略時は環境変数 OG_FONT、次に Windows の Fonts フォルダを見る。
"""

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
SCALE = 2  # 2倍で描いて縮小し、輪郭をなめらかにする

BG = (11, 18, 32)
INK = (255, 255, 255)
SUB = (169, 180, 200)
LINE = (51, 65, 85)
ACCENT = (238, 255, 0)
BALL_INK = (0, 0, 0)

OUT = Path(__file__).resolve().parents[1] / "public" / "og-image.png"


def font_path() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return os.environ.get("OG_FONT") or "/mnt/c/Windows/Fonts/NotoSansJP-VF.ttf"


def font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(font_path(), size * SCALE)
    f.set_variation_by_name(weight)
    return f


def s(v: float) -> int:
    return round(v * SCALE)


def ball(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, num: int, accent: bool) -> None:
    fill = ACCENT if accent else INK
    d.ellipse((s(cx - r), s(cy - r), s(cx + r), s(cy + r)), fill=fill)
    d.text((s(cx), s(cy)), f"{num:02d}", font=font(round(r * 0.78), "Black"), fill=BALL_INK, anchor="mm")


def main() -> None:
    im = Image.new("RGB", (s(W), s(H)), BG)
    d = ImageDraw.Draw(im)

    # 右側：抽せん球（一部をはみ出させて奥行きを出す）
    balls = [
        (850, 120, 62, 6, False),
        (990, 70, 50, 13, False),
        (1120, 150, 70, 21, True),
        (930, 250, 74, 27, True),
        (1080, 320, 58, 34, False),
        (820, 380, 52, 43, False),
        (980, 450, 66, 9, True),
        (1150, 480, 52, 38, False),
        (860, 560, 46, 17, False),
    ]
    for cx, cy, r, num, accent in balls:
        ball(d, cx, cy, r, num, accent)

    # 左上：サイト名
    x = 72
    d.rectangle((s(x), s(78), s(x + 56), s(86)), fill=ACCENT)
    d.text((s(x), s(104)), "LOTO アナリティクス", font=font(36), fill=INK)

    # 見出し
    head = font(84, "Black")
    y1, y2 = 200, 310
    d.text((s(x), s(y1)), "当せん番号を、", font=head, fill=INK)
    w = d.textlength("データ", font=head)
    d.text((s(x), s(y2)), "データ", font=head, fill=ACCENT)
    d.text((s(x) + w, s(y2)), "で読む。", font=head, fill=INK)

    # 機能
    chip_font = font(22)
    cx = x
    cy = 448
    for label in ["最新結果", "出現回数の分析", "次回予想", "シミュレーター"]:
        tw = d.textlength(label, font=chip_font) / SCALE
        d.rounded_rectangle((s(cx), s(cy), s(cx + tw + 32), s(cy + 44)), radius=s(22), outline=LINE, width=s(2))
        d.text((s(cx + 16), s(cy + 22)), label, font=chip_font, fill=INK, anchor="lm")
        cx += tw + 32 + 10

    # 下部
    d.line((s(x), s(540), s(700), s(540)), fill=LINE, width=s(2))
    d.text((s(x), s(570)), "ロト6・ロト7・ミニロト", font=font(24, "Medium"), fill=SUB, anchor="lm")
    d.text((s(700), s(570)), "lottery-analytics.com", font=font(24), fill=INK, anchor="rm")

    im.resize((W, H), Image.LANCZOS).save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
