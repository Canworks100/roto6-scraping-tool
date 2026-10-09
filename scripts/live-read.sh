#!/usr/bin/env bash
# 抽せん中の公開中継を見て、確定したときだけ速報を出す。公開フラグは config.yaml。
set -euo pipefail

GAME="${1:?usage: live-read.sh <loto6|loto7|miniloto>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${LOTO_PUBLISH_LOCK:-/var/lock/loto-collect-publish.lock}"
export SITE_ORIGIN="${SITE_ORIGIN:-https://lottery-analytics.com}"
export VITE_SITE_ORIGIN="${VITE_SITE_ORIGIN:-$SITE_ORIGIN}"
export LOTO_WWW_DIR="${LOTO_WWW_DIR:-/var/www/loto-stg}"
export PYTHONPATH="${PYTHONPATH:-$ROOT/src}"

cd "$ROOT"
exec flock -w 1800 "$LOCK" \
  "$ROOT/.venv/bin/python" -m loto6 live-read --game "$GAME"
