#!/usr/bin/env bash
# 静的サイトだけ再ビルド・同期（手動・補完後用）。flock で排他。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${LOTO_PUBLISH_LOCK:-/var/lock/loto-collect-publish.lock}"
export SITE_ORIGIN="${SITE_ORIGIN:-https://lottery-analytics.com}"
export VITE_SITE_ORIGIN="${VITE_SITE_ORIGIN:-$SITE_ORIGIN}"
export LOTO_WWW_DIR="${LOTO_WWW_DIR:-/var/www/loto-stg}"
export PYTHONPATH="${PYTHONPATH:-$ROOT/src}"

cd "$ROOT"
exec flock -w 1800 "$LOCK" \
  "$ROOT/.venv/bin/python" -m loto6 publish-static
