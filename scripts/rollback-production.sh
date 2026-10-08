#!/usr/bin/env bash
# Backup/ から本番へ差し戻す。明示許可後のみ実行すること。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${DEPLOY_HOST:-lottery-analytics}"
REMOTE_APP="${REMOTE_APP:-/opt/loto}"
REMOTE_WWW="${REMOTE_WWW:-/var/www/loto}"
DRY_RUN=0
STAMP="${1:-}"

if [[ "${STAMP}" == "--dry-run" ]]; then
  DRY_RUN=1
  STAMP="${2:-}"
elif [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

if [[ -z "${STAMP}" ]]; then
  # 最新の Backup/YYYYMMDD-HHMMSS を使う
  STAMP="$(ls -1 "${ROOT}/Backup" 2>/dev/null | sort | tail -1 || true)"
fi

BACKUP_DIR="${ROOT}/Backup/${STAMP}"
if [[ -z "${STAMP}" || ! -d "${BACKUP_DIR}" ]]; then
  echo "Backup が見つかりません: ${BACKUP_DIR}" >&2
  echo "使い方: ./scripts/rollback-production.sh [STAMP] [--dry-run]" >&2
  exit 1
fi

RSYNC_FLAGS=(-a --delete)
if [[ "${DRY_RUN}" -eq 1 ]]; then
  RSYNC_FLAGS+=(--dry-run -v)
  echo "[dry-run] リモート変更・再起動は行いません"
fi

echo "host=${HOST}"
echo "backup=${BACKUP_DIR}"
echo "dry_run=${DRY_RUN}"

if [[ -d "${BACKUP_DIR}/www" ]]; then
  echo "==> 静的を差し戻し"
  rsync "${RSYNC_FLAGS[@]}" -e "ssh" "${BACKUP_DIR}/www/" "${HOST}:${REMOTE_WWW}/"
fi

if [[ -d "${BACKUP_DIR}/app" ]]; then
  echo "==> アプリを差し戻し"
  rsync "${RSYNC_FLAGS[@]}" -e "ssh" \
    --exclude '.venv' --exclude 'node_modules' \
    "${BACKUP_DIR}/app/" "${HOST}:${REMOTE_APP}/"
fi

if [[ "${DRY_RUN}" -eq 0 ]]; then
  ssh "${HOST}" "systemctl restart loto-api"
fi

echo "差し戻し完了: ${STAMP}"
