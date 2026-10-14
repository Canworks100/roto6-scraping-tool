"""収集後の静的サイト再ビルドと配信同期。壊れた dist は出さない。"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("loto6")

DEFAULT_SITE_ORIGIN = "https://lottery-analytics.com"
REQUIRED_DIST_FILES = ("index.html", "robots.txt", "sitemap.xml", "news-sitemap.xml")
# tempfile.mkdtemp は 0700。rsync -a だと配信 root が nginx(www-data) から読めなくなる。
RSYNC_CHMOD = "D755,F644"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def publish_static(
    *,
    site_origin: str | None = None,
    www_dir: str | Path | None = None,
    web_dir: Path | None = None,
) -> None:
    """apps/web を一時ディレクトリへビルドし、検証後に www_dir へ同期する。失敗時は配信を触らない。"""
    origin = (site_origin or os.environ.get("SITE_ORIGIN") or DEFAULT_SITE_ORIGIN).rstrip("/")
    web = web_dir or (repo_root() / "apps" / "web")
    target = Path(www_dir or os.environ.get("LOTO_WWW_DIR") or "/var/www/loto-stg")
    if not web.is_dir():
        raise FileNotFoundError(f"web dir not found: {web}")
    if not (web / "package.json").is_file():
        raise FileNotFoundError(f"package.json missing: {web}")

    staging = Path(tempfile.mkdtemp(prefix="loto-dist-"))
    try:
        env = {
            **os.environ,
            "SITE_ORIGIN": origin,
            "VITE_SITE_ORIGIN": origin,
            "LOTO_DIST_DIR": str(staging),
        }
        logger.info("静的ビルド開始 origin=%s staging=%s", origin, staging)
        subprocess.run(
            ["npm", "ci"],
            cwd=web,
            env=env,
            check=True,
            timeout=600,
        )
        subprocess.run(
            ["npm", "run", "build"],
            cwd=web,
            env=env,
            check=True,
            timeout=900,
        )
        _assert_dist_ok(staging)
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "rsync",
                "-a",
                "--delete",
                f"--chmod={RSYNC_CHMOD}",
                f"{staging}/",
                f"{target}/",
            ],
            check=True,
            timeout=300,
        )
        try:
            _assert_www_readable(target)
        except Exception as exc:
            from loto6.notify import alert

            alert(f"静的同期後に www-data から読めません: {target} ({exc})")
            raise
        logger.info("静的同期完了 → %s", target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _assert_dist_ok(dist: Path) -> None:
    missing = [name for name in REQUIRED_DIST_FILES if not (dist / name).is_file()]
    if missing:
        raise RuntimeError(f"ビルド成果物が不完全です（欠け: {', '.join(missing)}）: {dist}")
    for name in REQUIRED_DIST_FILES:
        if (dist / name).stat().st_size < 16:
            raise RuntimeError(f"ビルド成果物が空です: {dist / name}")


def _assert_www_readable(target: Path) -> None:
    """nginx(www-data) がディレクトリを辿れ、index.html を読める権限か確認する。"""
    index = target / "index.html"
    if not index.is_file():
        raise RuntimeError(f"index.html がありません: {index}")
    dir_mode = target.stat().st_mode
    file_mode = index.stat().st_mode
    # other に x（辿り）と r（一覧）／ファイルは other に r
    if not (dir_mode & stat.S_IXOTH and dir_mode & stat.S_IROTH):
        raise RuntimeError(
            f"{target} が www-data から辿れません (mode={stat.filemode(dir_mode)})"
        )
    if not (file_mode & stat.S_IROTH):
        raise RuntimeError(
            f"{index} が www-data から読めません (mode={stat.filemode(file_mode)})"
        )
    # 可能なら実ユーザーでも確認（sudo 無しで失敗してもモード検査で足りる）
    for cmd in (
        ["sudo", "-n", "-u", "www-data", "test", "-x", str(target)],
        ["sudo", "-n", "-u", "www-data", "test", "-r", str(index)],
    ):
        try:
            subprocess.run(cmd, check=True, timeout=10, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            break


def publish_from_config(config: dict[str, Any]) -> None:
    publish = config.get("publish") or {}
    publish_static(
        site_origin=str(publish.get("site_origin") or DEFAULT_SITE_ORIGIN),
        www_dir=publish.get("www_dir") or os.environ.get("LOTO_WWW_DIR") or "/var/www/loto-stg",
    )
