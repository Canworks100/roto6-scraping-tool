"""コマンドライン。

使い方:
  python -m loto6 app
  python -m loto6 collect --game loto6 --all
  python -m loto6 collect --game loto7 --all
  python -m loto6 migrate-legacy
  python -m loto6 import-raw
  python -m loto6 analyze
  python -m loto6 serve-api
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loto6.analyze import analyze, write_outputs
from loto6.config import abs_path, load_config
from loto6.scrape import collect, collect_latest, import_raw, setup_logging, years_ago
from loto6.storage import Store, migrate_legacy_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ロト収集・公開API・デスクトップ台帳")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("app", help="収支ノートをウィンドウで開く（デスクトップ台帳・従来DB）")

    collect_parser = sub.add_parser("collect", help="設定の collector.source に従い過去分・速報を収集する")
    collect_parser.add_argument("--game", default="loto6", choices=["loto6", "loto7", "miniloto"])
    collect_parser.add_argument("--years", type=int, default=None, help="何年分を集めるか（既定は設定ファイル）")
    collect_parser.add_argument("--all", action="store_true", help="第1回から最新回まで全件を取り込む")
    collect_parser.add_argument("--refresh", action="store_true", help="取得済みの回も上書きする")
    collect_parser.add_argument("--latest", action="store_true", help="直近数回だけ取り込む（速報用）")

    import_parser = sub.add_parser("import-raw", help="data/raw のCSVをデータベースへ入れる")
    import_parser.add_argument("--game", default="loto6", choices=["loto6", "loto7", "miniloto"])
    import_parser.add_argument("--dir", dest="raw_dir", default=None)
    import_parser.add_argument("--refresh", action="store_true")

    analyze_parser = sub.add_parser("analyze", help="蓄積データから出現傾向を出す")
    analyze_parser.add_argument("--game", default="loto6", choices=["loto6", "loto7", "miniloto"])
    analyze_parser.add_argument("--years", type=int, default=None)
    analyze_parser.add_argument("--start", default=None, help="YYYY-MM-DD")
    analyze_parser.add_argument("--end", default=None, help="YYYY-MM-DD")

    sub.add_parser("migrate-legacy", help="data/loto6.sqlite を data/loto.sqlite へ取り込む")

    serve = sub.add_parser("serve-api", help="公開 FastAPI を起動（開発用）")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    flash_parser = sub.add_parser("flash-articles", help="蓄積データから速報記事を自動生成する")
    flash_parser.add_argument(
        "--game",
        default="all",
        choices=["all", "loto6", "loto7", "miniloto"],
        help="対象種目（既定: 全種目）",
    )
    flash_parser.add_argument(
        "--missing-only",
        action="store_true",
        help="未生成の回だけ書き出す",
    )

    args = parser.parse_args(argv)
    config = load_config()
    config["_sqlite_path"] = abs_path(config, "storage.sqlite_path")
    config["_legacy_sqlite_path"] = abs_path(config, "storage.legacy_sqlite_path")
    config["_csv_path"] = abs_path(config, "storage.csv_path")
    setup_logging(abs_path(config, "storage.sqlite_path").parent.parent / "logs" / "loto6.log")

    if args.command == "app":
        from loto6.app import run

        # デスクトップ台帳は従来DBを維持
        return run(config["_legacy_sqlite_path"])
    if args.command == "migrate-legacy":
        count = migrate_legacy_file(config["_legacy_sqlite_path"], config["_sqlite_path"])
        print(f"移行完了: 新規 {count} 件 → {config['_sqlite_path']}")
        return 0
    if args.command == "serve-api":
        import uvicorn

        api_dir = str(Path(__file__).resolve().parents[2] / "apps" / "api")
        src_dir = str(Path(__file__).resolve().parents[1])
        if api_dir not in sys.path:
            sys.path.insert(0, api_dir)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        uvicorn.run("loto_api.main:app", host=args.host, port=args.port, reload=args.reload)
        return 0
    if args.command == "collect":
        from loto6.notify import alert

        source = str((config.get("collector") or {}).get("source") or "mizuho")
        try:
            if args.latest:
                result = collect_latest(config, game=args.game)
            elif args.all:
                result = collect(config, years=None, refresh=args.refresh, all_history=True, game=args.game)
            else:
                years = args.years if args.years is not None else int(config["lottery"]["years"])
                result = collect(config, years=years, refresh=args.refresh, all_history=False, game=args.game)
        except Exception as exc:  # noqa: BLE001
            alert(f"LOTO収集失敗 game={args.game} source={source} latest={args.latest}: {exc}")
            raise
        failed = int((result or {}).get("failed") or 0)
        if failed > 0:
            alert(
                f"LOTO収集で失敗あり game={args.game} source={source} "
                f"failed={failed} inserted={result.get('inserted')} "
                f"latest={bool(args.latest)}"
            )
            return 1
        return 0
    if args.command == "import-raw":
        raw_dir = Path(args.raw_dir) if args.raw_dir else abs_path(config, "storage.raw_dir")
        import_raw(config, raw_dir=raw_dir, refresh=args.refresh, game=args.game)
        return 0
    if args.command == "flash-articles":
        from loto6.flash_article import ensure_missing_articles, refresh_all_articles
        from loto6.games import game_ids, get_game

        targets = game_ids(config) if args.game == "all" else [args.game]
        store = Store(config["_sqlite_path"])
        try:
            for game in targets:
                g = get_game(config, game)
                count = ensure_missing_articles(store, g) if args.missing_only else refresh_all_articles(store, g)
                print(f"{game}: 速報記事 {count} 件")
        finally:
            store.close()
        return 0

    start, end = _analysis_range(args, config)
    store = Store(config["_sqlite_path"])
    try:
        rows = store.load_draws(start, end, game=args.game)
    finally:
        store.close()
    if not rows:
        print("分析できるデータがありません。先に collect または migrate-legacy を実行してください。", file=sys.stderr)
        return 1
    from loto6.games import get_game

    g = get_game(config, args.game)
    config = dict(config)
    config["_game"] = args.game
    config["lottery"] = {
        **dict(config.get("lottery") or {}),
        "max_number": int(g["max_number"]),
        "main_count": int(g["main_count"]),
        "min_number": int(g["min_number"]),
        "bonus_count": int(g["bonus_count"]),
        "game": args.game,
    }
    result = analyze(rows, config)
    summary = write_outputs(result, abs_path(config, "analysis.output_dir"))
    print(summary.read_text(encoding="utf-8"))
    return 0


def _analysis_range(args: argparse.Namespace, config: dict) -> tuple[str | None, str | None]:
    if args.start or args.end:
        return args.start, args.end
    if args.years is not None:
        return years_ago(args.years), None
    return None, None


if __name__ == "__main__":
    raise SystemExit(main())
