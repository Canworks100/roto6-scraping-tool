"""速報記事の公開日時を、記録から分かる実際の時刻に直す（一度きりの補正用）。

使い方:
    PYTHONPATH=src python scripts/backfill_flash_published.py times.json [--db data/loto.sqlite] [--dry-run]

times.json は {"loto6": {"2146": "2026-10-15T19:00:06+09:00", ...}, ...}。
今の記録より早い時刻のときだけ書き換える（遅い時刻では上書きしない）。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from loto6.storage import Store


def _to_utc(iso: str) -> str:
    parsed = datetime.fromisoformat(iso)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("times", type=Path)
    parser.add_argument("--db", type=Path, default=Path("data/loto.sqlite"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    times = json.loads(args.times.read_text(encoding="utf-8"))
    store = Store(args.db)
    changed = 0
    try:
        for game, by_no in times.items():
            for draw_no, iso in by_no.items():
                if store.set_flash_published_at(game, int(draw_no), _to_utc(iso)):
                    changed += 1
        if args.dry_run:
            store.conn.rollback()
        else:
            store.conn.commit()
    finally:
        store.close()
    print(f"{'(dry-run) ' if args.dry_run else ''}公開日時を直した記事: {changed}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
