#!/usr/bin/env bash
# 速報収集 → 変更時のみ静的再ビルド。複数 timer の衝突は flock で排他。
set -euo pipefail

GAME="${1:?usage: collect-and-publish.sh <loto6|loto7|miniloto>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${LOTO_PUBLISH_LOCK:-/var/lock/loto-collect-publish.lock}"
export SITE_ORIGIN="${SITE_ORIGIN:-https://lottery-analytics.com}"
export VITE_SITE_ORIGIN="${VITE_SITE_ORIGIN:-$SITE_ORIGIN}"
export LOTO_WWW_DIR="${LOTO_WWW_DIR:-/var/www/loto-stg}"
export PYTHONPATH="${PYTHONPATH:-$ROOT/src}"

cd "$ROOT"
# 収集とビルドをまとめて排他（同時実行で dist / rsync が壊れないように）
exec flock -w 1800 "$LOCK" \
  "$ROOT/.venv/bin/python" -m loto6 collect --game "$GAME" --latest --publish
