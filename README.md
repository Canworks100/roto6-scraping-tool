# LOTO アナリティクス — 公開サイト＋デスクトップ台帳

みずほ銀行の当せん番号案内から種目別に全回を収集し、公開サイト（FastAPI + Vite/TS）で履歴・数字検索・出現傾向・口数指定の頻度ベース組み合わせ生成を提供する。購入台帳は従来どおりローカル専用。

## 環境

| 環境 | URL |
| --- | --- |
| ローカル | http://127.0.0.1:5174 （API: http://127.0.0.1:8000） |
| ステージング | https://stg.lottery-analytics.com （noindex） |
| 本番 | https://lottery-analytics.com |

VPS: Conoha `160.251.237.42`。DNS / CDN は Cloudflare。詳細は `deploy/README.md`。

## 必要なもの

- Python 3.11+、Node.js 20+、npm
- ローカル開発用の venv / `npm install`
- 本番・ステージング操作時: SSH（鍵はリポジトリ外の `.secrets`）

## ローカル

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# 旧DBがあればマルチゲームDBへ
PYTHONPATH=src python -m loto6 migrate-legacy

# API
PYTHONPATH=src:apps/api .venv/bin/uvicorn loto_api.main:app --reload --host 127.0.0.1 --port 8000

# UI（別ターミナル）
cd apps/web && npm install && npm run dev
```

収集:

```bash
PYTHONPATH=src python -m loto6 collect --game loto6 --all
PYTHONPATH=src python -m loto6 collect --game loto7 --all
PYTHONPATH=src python -m loto6 collect --game miniloto --all
```

分析・テスト:

```bash
PYTHONPATH=src python -m loto6 analyze --game loto6
PYTHONPATH=src python -m unittest discover -s tests
```

## ステージング

- ホスト: `stg.lottery-analytics.com`
- nginx: `deploy/nginx/loto-staging.conf`（`Disallow: /` と `X-Robots-Tag: noindex, nofollow`）
- 本番の `robots.txt` / `sitemap.xml` をコピーしない
- 反映は明示許可後のみ

## 本番

本番反映は明示許可があるときだけ実行する。手順の主コマンドは次の2本。

```bash
# バックアップ → 本番へ転送
./scripts/deploy-production.sh

# Backup/ から差し戻す
./scripts/rollback-production.sh
```

初回セットアップ・Cloudflare・SSH は `deploy/README.md`。

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `apps/web/` | 公開フロント（Vite/TS） |
| `apps/api/` | FastAPI |
| `src/` | 収集・CLI・デスクトップ台帳 |
| `data/loto.sqlite` | 公開・マルチゲームDB |
| `data/loto6.sqlite` | デスクトップ台帳用（従来） |
| `deploy/` | nginx / systemd / セキュリティ方針 |
| `scripts/` | 本番デプロイ・差し戻し |
| `logs/loto6.log` | 取得ログ |

## 収支ノート（デスクトップ・別系統）

```bash
./loto6-app
# または
PYTHONPATH=src python -m loto6 app
```

データは `data/loto6.sqlite`。公開用 `data/loto.sqlite` とは分離。

## 設定

種目定義は `config.yaml` の `games.*`。公開レート制限は `public.*`。
