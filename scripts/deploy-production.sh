#!/usr/bin/env bash
# バックアップしてから本番へ転送する。明示許可後のみ実行すること。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${DEPLOY_HOST:-lottery-analytics}"
REMOTE_APP="${REMOTE_APP:-/opt/loto}"
REMOTE_WWW="${REMOTE_WWW:-/var/www/loto}"
SITE_ORIGIN="${SITE_ORIGIN:-https://lottery-analytics.com}"
VITE_SITE_ORIGIN="${VITE_SITE_ORIGIN:-$SITE_ORIGIN}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${ROOT}/Backup/${STAMP}"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

echo "host=${HOST}"
echo "site_origin=${SITE_ORIGIN}"
echo "backup=${BACKUP_DIR}"
echo "dry_run=${DRY_RUN}"

mkdir -p "${BACKUP_DIR}"

RSYNC_FLAGS=(-a --delete)
SSH=(ssh "${HOST}")
if [[ "${DRY_RUN}" -eq 1 ]]; then
  RSYNC_FLAGS+=(--dry-run -v)
  echo "[dry-run] リモート変更・再起動は行いません"
fi

echo "==> リモート現状を Backup/ へ取得"
rsync "${RSYNC_FLAGS[@]}" -e "ssh" \
  "${HOST}:${REMOTE_WWW}/" "${BACKUP_DIR}/www/" || true
rsync "${RSYNC_FLAGS[@]}" -e "ssh" \
  --exclude '.venv' --exclude 'node_modules' --exclude 'apps/web/node_modules' \
  "${HOST}:${REMOTE_APP}/" "${BACKUP_DIR}/app/" || true

echo "==> フロントビルド"
cd "${ROOT}/apps/web"
if [[ "${DRY_RUN}" -eq 0 ]]; then
  export SITE_ORIGIN VITE_SITE_ORIGIN
  npm ci
  npm run build
else
  echo "[dry-run] npm ci / npm run build をスキップ"
fi

echo "==> アプリ同期"
rsync "${RSYNC_FLAGS[@]}" -e "ssh" \
  --exclude '.venv' --exclude 'node_modules' --exclude 'apps/web/node_modules' \
  --exclude 'apps/web/dist' --exclude 'Backup' --exclude '.git' \
  --exclude 'data/*.sqlite' --exclude 'data/*.sqlite-*' \
  "${ROOT}/" "${HOST}:${REMOTE_APP}/"

echo "==> 静的配信"
if [[ "${DRY_RUN}" -eq 0 ]]; then
  rsync -a --delete -e "ssh" "${ROOT}/apps/web/dist/" "${HOST}:${REMOTE_WWW}/"
  "${SSH[@]}" "systemctl restart loto-api"
else
  rsync "${RSYNC_FLAGS[@]}" -e "ssh" "${ROOT}/apps/web/dist/" "${HOST}:${REMOTE_WWW}/" || \
    echo "[dry-run] dist が無い場合はビルド後に再実行"
fi

echo "完了: backup=${BACKUP_DIR}"
