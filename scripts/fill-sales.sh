#!/usr/bin/env bash
# 販売実績が空の直近回だけ補い、書けたときだけ静的再ビルド。収集タイマーと flock を共有する。
set -euo pipefail

GAME="${1:?usage: fill-sales.sh <loto6|loto7|miniloto>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${LOTO_PUBLISH_LOCK:-/var/lock/loto-collect-publish.lock}"
export SITE_ORIGIN="${SITE_ORIGIN:-https://lottery-analytics.com}"
export VITE_SITE_ORIGIN="${VITE_SITE_ORIGIN:-$SITE_ORIGIN}"
export LOTO_WWW_DIR="${LOTO_WWW_DIR:-/var/www/loto-stg}"
export PYTHONPATH="${PYTHONPATH:-$ROOT/src}"

cd "$ROOT"
exec flock -w 1800 "$LOCK" \
  "$ROOT/.venv/bin/python" -m loto6 fill-sales --game "$GAME" --publish
