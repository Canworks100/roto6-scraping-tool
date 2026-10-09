# VPS デプロイ手順（本番反映は明示許可後のみ）

公開サイト構成: Cloudflare → nginx（TLS）→ 静的 `apps/web/dist` ＋ `/api` → uvicorn FastAPI。収集は systemd timer で Web と分離。

## 環境

| 環境 | URL |
| --- | --- |
| ローカル | http://127.0.0.1:5174 （API: :8000） |
| ステージング | https://stg.lottery-analytics.com |
| 本番 | https://lottery-analytics.com |

| 項目 | 値 |
| --- | --- |
| VPS | Conoha `160.251.237.42` |
| SSH | オリジン IP へ直接（Cloudflare プロキシ経由では不可） |
| アプリ | `/opt/loto/`（venv・`data/loto.sqlite`） |
| 静的 | `/var/www/loto-stg/`（本番 nginx root。旧 `/var/www/loto/` は使わない） |
| 実行ユーザー | `loto` |

## 必要なもの

- SSH 鍵（リポジトリ外。例: 手元 `.secrets/conoha-ssh-key.pem`）
- Cloudflare にドメイン `lottery-analytics.com` を追加済みであること
- Node.js / Python（ローカルでビルドする場合）

## ローカルからの SSH

`~/.ssh/config` 例（鍵はリポジトリ外。WSL では `~/.ssh/lottery-analytics_conoha.pem` に配置）:

```
Host lottery-analytics
  HostName 160.251.237.42
  User canworks
  IdentityFile ~/.ssh/lottery-analytics_conoha.pem
  IdentitiesOnly yes
```

```bash
ssh lottery-analytics
```

Web は Cloudflare 経由、SSH は常に上記オリジン IP。

`Permission denied (publickey)` のときは、対応する公開鍵（`ssh-keygen -y -f …pem`）を Conoha の SSH Key / サーバの `~/.ssh/authorized_keys` に登録する。ポート 22 までの到達は可能でも、鍵がサーバ側に無いと入れない。

## Cloudflare（DNS）

| 種別 | 名前 | 内容 | プロキシ |
| --- | --- | --- | --- |
| A | `@` | `160.251.237.42` | Proxied |
| A | `www` | `160.251.237.42` | Proxied |
| A | `stg` | `160.251.237.42` | Proxied |

- SSL/TLS: オリジン証明書取得後は **Full (strict)**。取得前に Flexible は使わない
- ステージングは nginx で noindex（`deploy/nginx/loto-staging.conf`）。本番の `robots.txt` / `sitemap.xml` をステージングへコピーしない

## ステージング

1. `deploy/nginx/loto-staging.conf` を配置（`stg.lottery-analytics.com`）
2. 静的を `/var/www/loto-stg/` へ
3. トップと下層で `X-Robots-Tag: noindex, nofollow` と `robots.txt`（`Disallow: /`）を確認

反映は明示許可後のみ。

## 本番

主コマンドは次の2本（明示許可後のみ実行）。

```bash
# バックアップ → 本番へ転送
./scripts/deploy-production.sh

# Backup/ から差し戻す
./scripts/rollback-production.sh
```

| 用途 | コマンド |
| --- | --- |
| 転送内容の確認のみ | `./scripts/deploy-production.sh --dry-run` |
| 差し戻しの確認のみ | `./scripts/rollback-production.sh --dry-run` |

ビルド時オリジン:

```bash
export SITE_ORIGIN=https://lottery-analytics.com
export VITE_SITE_ORIGIN=https://lottery-analytics.com
```

### 初回セットアップ概要（許可後）

1. ユーザー `loto` を作成し、リポジトリを `/opt/loto` に配置
2. `python3 -m venv /opt/loto/.venv` → `pip install -r requirements.txt -r apps/api/requirements.txt`
3. 必要なら `migrate-legacy` → 各種目 `collect --all` → `flash-articles`
4. `apps/web` で上記オリジン付き `npm run build` → `dist` を `/var/www/loto/`
5. `deploy/systemd/*` と `deploy/nginx/loto.conf` を配置して enable
   - 速報＋静的再公開（抽せん曜日・夜複数回）:
     `loto-collect-latest-loto6.timer`（月木）/ `loto-collect-latest-loto7.timer`（金）/ `loto-collect-latest-miniloto.timer`（火）
     → `collect-and-publish.sh`（`flock` 排他、変更時だけ `SITE_ORIGIN` 付きビルド → `/var/www/loto-stg/`）
   - 中継の読み取り（抽せん曜日 18:40、19:05まで）: `loto-live-read-loto6.timer`（月木）/ `loto-live-read-loto7.timer`（金）/ `loto-live-read-miniloto.timer`（火）。反映後に `sudo -u loto /opt/loto/.venv/bin/playwright install chromium` してからタイマーを有効にする
   - 23:00 番号未取得チェック: `loto-draw-miss-loto6|loto7|miniloto.timer`
   - 失敗通知: `/etc/vps-backup/discord.env` の `DISCORD_WEBHOOK_URL`（#vps-監視）。互換で `/etc/loto/alert.env` の `LOTO_ALERT_WEBHOOK` も可。値はリポジトリに書かない
   - みずほ夜間 `loto-collect@*.timer` は `disable --now`（または mask）。service は no-op
   - 過去金額の欠けは初回のみ `python -m loto6 backfill-prizes --game all`（事前に DB バックアップ）
6. certbot で TLS。HSTS は証明書取得後に有効化。Cloudflare を Full (strict) へ
7. ファイアウォールは 22/80/443（SSH は鍵認証）
8. 方針の詳細は `deploy/SECURITY.md`

### 収集元

`config.yaml` の `collector.source`:

- `rakuten`（既定）… 楽天×宝くじ。販売実績は null（画面は「未取得」）
- `mizuho` … レガシー（BrowserClient）。VPS では 403 のため通常使わない

## バックアップ・監視

- 日次で `data/loto.sqlite`（WAL なら `sqlite3 .backup`）
- `journalctl -u loto-api -u loto-collect@loto6`
- nginx access / error

**本番への反映・証明書取得・公開は、ユーザーの明示許可があるまで行わない。**
