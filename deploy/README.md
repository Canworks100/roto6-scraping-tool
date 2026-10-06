# VPS デプロイ手順（本番反映は明示許可後のみ）

公開サイト構成: nginx（TLS）→ 静的 `apps/web/dist` ＋ `/api` → uvicorn FastAPI。収集は systemd timer で Web と分離。`collect --latest` は抽せん後の番号案内を先に拾い、みずほCSVが出ていれば金額を足して速報記事にする。

## ディレクトリ例

- `/var/www/loto/` … フロント `dist/`
- `/opt/loto/` … アプリ・venv・`data/loto.sqlite`
- 実行ユーザー: `loto`（DB も同ユーザー所有）

## 初回セットアップ概要

1. 非 root ユーザー `loto` を作成し、リポジトリを `/opt/loto` に配置
2. `python3 -m venv /opt/loto/.venv` → `pip install -r requirements.txt -r apps/api/requirements.txt`
3. `python -m loto6 migrate-legacy`（既存がある場合）→ 各種目 `collect --all` → `python -m loto6 flash-articles`（速報記事の一括自動生成）
4. `cd apps/web && npm ci && npm run build` → `dist` を `/var/www/loto/` へ
5. 本ディレクトリの `systemd/*.service` / `*.timer` と `nginx/loto.conf` を配置
   ```bash
   sudo cp deploy/systemd/loto-api.service /etc/systemd/system/
   sudo cp deploy/systemd/loto-collect@.service /etc/systemd/system/
   sudo cp deploy/systemd/loto-collect@.timer /etc/systemd/system/
   sudo cp deploy/systemd/loto-collect-latest@.service /etc/systemd/system/
   sudo cp deploy/systemd/loto-collect-latest@.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now loto-api
   sudo systemctl enable --now loto-collect@loto6.timer
   sudo systemctl enable --now loto-collect@loto7.timer
   sudo systemctl enable --now loto-collect@miniloto.timer
   sudo systemctl enable --now loto-collect-latest@loto6.timer
   sudo systemctl enable --now loto-collect-latest@loto7.timer
   sudo systemctl enable --now loto-collect-latest@miniloto.timer
   ```
6. certbot で TLS。HSTS は証明書取得後に有効化
7. ファイアウォールは 22/80/443 のみ（SSH は鍵認証）
8. 詳細なセキュリティ方針は `deploy/SECURITY.md`

## デプロイ（スクリプト化想定）

```bash
# 許可後のみ本番で実行
cd /opt/loto
git pull
. .venv/bin/activate
pip install -r requirements.txt -r apps/api/requirements.txt
cd apps/web && npm ci && npm run build
rsync -a --delete dist/ /var/www/loto/
sudo systemctl restart loto-api
```

## バックアップ

- 日次で `data/loto.sqlite` をコピー（WAL なら `sqlite3 .backup` 推奨）
- 可能ならオフサイトへ

## 監視

- `journalctl -u loto-api -u loto-collect@loto6`
- nginx access / error ログ

**本番への反映・証明書取得・公開は、ユーザーの明示許可があるまで行わない。**
