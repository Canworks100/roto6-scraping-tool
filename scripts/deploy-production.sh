#!/usr/bin/env bash
# バックアップしてから本番へ転送する。明示許可後のみ実行すること。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${DEPLOY_HOST:-lottery-analytics}"
REMOTE_APP="${REMOTE_APP:-/opt/loto}"
REMOTE_WWW="${REMOTE_WWW:-/var/www/loto-stg}"
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
# VPS 上の /opt/loto・/var/www は loto 所有。canworks は sudo rsync で書く。
RSYNC_PATH=(--rsync-path="sudo rsync")
SSH=(ssh "${HOST}")
if [[ "${DRY_RUN}" -eq 1 ]]; then
  RSYNC_FLAGS+=(--dry-run -v)
  echo "[dry-run] リモート変更・再起動は行いません"
fi

echo "==> リモート現状を Backup/ へ取得"
rsync "${RSYNC_FLAGS[@]}" "${RSYNC_PATH[@]}" -e "ssh" \
  "${HOST}:${REMOTE_WWW}/" "${BACKUP_DIR}/www/" || true
rsync "${RSYNC_FLAGS[@]}" "${RSYNC_PATH[@]}" -e "ssh" \
  --exclude '.venv' --exclude 'node_modules' --exclude 'apps/web/node_modules' \
  "${HOST}:${REMOTE_APP}/" "${BACKUP_DIR}/app/" || true
if [[ "${DRY_RUN}" -eq 0 ]]; then
  "${SSH[@]}" "sudo cp -a ${REMOTE_APP}/data/loto.sqlite ${REMOTE_APP}/data/loto.sqlite.bak-${STAMP} && sudo chown loto:loto ${REMOTE_APP}/data/loto.sqlite.bak-${STAMP}" || true
fi

# 静的サイトは手元ではビルドしない。速報記事（/<game>/flash/<回>）は本番DBの全回から作るため、
# 手元のDBで作ると記事ページが消える（2026-10-14 に 4420→169 URL になり記事が404になった）。
BEFORE_URLS="$("${SSH[@]}" "grep -c '<loc>' ${REMOTE_WWW}/sitemap.xml" 2>/dev/null || echo 0)"
echo "==> 現在のサイトマップ URL 数: ${BEFORE_URLS}"

echo "==> アプリ同期"
rsync "${RSYNC_FLAGS[@]}" "${RSYNC_PATH[@]}" -e "ssh" \
  --exclude '.venv' --exclude 'node_modules' --exclude 'apps/web/node_modules' \
  --exclude 'apps/web/dist' --exclude 'apps/web/.env.local' --exclude 'Backup' --exclude '.git' \
  --exclude '.cache' --exclude '.local' --exclude '.npm' \
  --exclude 'data/*.sqlite' --exclude 'data/*.sqlite-*' --exclude 'data/*.sqlite.bak-*' \
  "${ROOT}/" "${HOST}:${REMOTE_APP}/"
if [[ "${DRY_RUN}" -eq 0 ]]; then
  "${SSH[@]}" "sudo chown -R loto:loto ${REMOTE_APP} && sudo chmod +x ${REMOTE_APP}/scripts/*.sh || true"
fi

echo "==> 静的配信（本番サーバー上で本番DBからビルド）"
if [[ "${DRY_RUN}" -eq 0 ]]; then
  "${SSH[@]}" "cd ${REMOTE_APP}/apps/web && sudo -u loto -H npm ci --no-audit --no-fund"
  "${SSH[@]}" "sudo -u loto -H env SITE_ORIGIN=${SITE_ORIGIN} VITE_SITE_ORIGIN=${VITE_SITE_ORIGIN} LOTO_WWW_DIR=${REMOTE_WWW} ${REMOTE_APP}/scripts/publish-static.sh"
  "${SSH[@]}" "sudo -u www-data test -x ${REMOTE_WWW} && sudo -u www-data test -r ${REMOTE_WWW}/index.html" \
    || { echo "ERROR: ${REMOTE_WWW} が www-data から読めません"; exit 1; }
  "${SSH[@]}" "sudo systemctl restart loto-api"
  AFTER_URLS="$("${SSH[@]}" "grep -c '<loc>' ${REMOTE_WWW}/sitemap.xml" 2>/dev/null || echo 0)"
  echo "==> サイトマップ URL 数: ${BEFORE_URLS} → ${AFTER_URLS}"
  if [[ "${BEFORE_URLS}" -gt 0 && "${AFTER_URLS}" -lt $(( BEFORE_URLS * 9 / 10 )) ]]; then
    echo "ERROR: ページ数が1割以上減りました。記事が消えていないか確認してください（配信前の状態は ${BACKUP_DIR}/www）"
    exit 1
  fi
else
  echo "[dry-run] 本番サーバーでの npm ci / publish-static をスキップ"
fi

echo "完了: backup=${BACKUP_DIR}"
