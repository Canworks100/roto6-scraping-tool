# CLAUDE.md

LOTO アナリティクス（https://lottery-analytics.com）。ロト6・ロト7・ミニロトの当せん番号を収集し、公開サイトで履歴・分析・予想を出す。詳細は `README.md`、運用は `deploy/README.md`。

## 応答ルール
- 日本語。結論から、簡潔に（前置き・締めの挨拶なし）
- 既定は短く。「詳細」と言われたときだけ広げる
- 曖昧な指示は妥当な仮定で進め、仮定を一言添える

## 構成
| パス | 内容 |
| --- | --- |
| `apps/web/` | 公開フロント（Vite + TS）。`index.html` が全ページ共通テンプレート |
| `apps/web/scripts/prerender.mjs` | ビルド時に静的HTMLを生成（SEO・法務ページ本文もここ） |
| `apps/web/src/legal.ts` | 法務ページのクライアント側本文。`prerender.mjs` と内容を揃える |
| `apps/api/` | FastAPI |
| `src/loto6/` | 収集・CLI・速報記事・通知・静的公開 |
| `config.yaml` | 種目定義・収集元・レート制限 |
| `deploy/`, `scripts/` | nginx/systemd、本番デプロイ・差し戻し |

## コマンド
```bash
# テスト（Python）
PYTHONPATH=src python -m unittest discover -s tests
# フロントのビルド（型チェック + プリレンダー込み）
cd apps/web && npm ci && npm run build
```
変更後は該当するテスト・ビルドを通してから commit する。

## 禁止・要許可
- 本番反映（`scripts/deploy-production.sh` 等）・ステージング反映は明示許可があるときだけ
- `.secrets`・認証情報・`*.env` をコミットしない
- 収集はレート制限（`config.yaml` の `rate_limit`）を守る。間隔を縮めない
- ステージングに本番の `robots.txt` / `sitemap.xml` を置かない

## 規約
- コミットメッセージは日本語1文で「〜する。」形式（例: `楽天の速報取得を20:15開始にする。`）
- 法務・プライバシー文言を変えたら `prerender.mjs` と `src/legal.ts` の両方を直す
- 計測は GTM（`GTM-5J394WHV`）経由。GA4 等のタグはコードでなく GTM 側で管理する
