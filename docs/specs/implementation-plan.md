# 実装計画

根拠: `docs/specs/analysis.md`、`docs/specs/seo-strategy.md`。判定は表示確認（改修）。本番反映は含めない。

主戦は「ロト6 予想」「ロト7 予想」「ミニロト 予想」。着地 `/loto6/generate` `/loto7/generate` `/miniloto/generate`。分析は中位の受け皿。買い方・FAQは出さない。

## 完了済み

- ホームは `/loto6` のページ一覧。種目はヘッダー切替
- 予想ページの title / h1 / ナビ名
- 収集データ（3種目全回）と公開 API・画面の既存機能

## 工程

依存は 1 → 2 → 3。4 は 2 のあと。5 は 3・4 と並行可だが、主戦3URLは 1 の直後に出す。

### 1. 予想3URLをインデックスできるHTMLにする

変更前: SPA のまま。初回HTMLの title はハブ用。  
変更後: ビルドで3種目の `/generate` に `{種目} 予想` の title・h1 が入る。`sitemap.xml` に3URL。canonical はパラメータなし。

触るもの: `apps/web` のプリレンダー、`index.html` のルート別 title、`public/sitemap.xml` またはビルド生成、`robots.txt`（本番用。ステージングは Disallow）。

判定: ビルド成果物の `/loto6/generate/index.html` を開き、title と h1 が「ロト6 予想」。ロト7・ミニロトも同様。curl で sitemap に3URL。

### 2. 集計と API

変更前: `trends?years=` のみ。画面に出ない pairs / odd_even / sums。ボーナスは `bonus` だけ。  
変更後: `period`（all / draws50 / 100 / 500 / years5 / years10）。frequency に期待・本+ボーナス・最長連休・連続。`bonus2` をボーナス回数に含める。shape / follow を返す。

触るもの: `src/loto6/analyze.py`、`apps/api/loto_api/main.py`、`tests/`。

判定: ロト6 `period=all` で開催回数が DB 件数と一致。ロト7のボーナス回数が `bonus`+`bonus2`。不正 `period` は 400。

### 3. 分析画面

変更前: `/freq` は10年・本数字のみ。pairs / shape / grid / follow なし。  
変更後: 仕様どおり5画面。ナビに追加。期間切替は `?period=`。機能ページに免責を置かない。title は戦略の表（「予想」は付けない）。

順:

1. `/freq`（棒・本／ボーナス切替・期待・連休列）
2. `/pairs`
3. `/shape`
4. `/grid`（history API）
5. `/follow`

触るもの: `apps/web/src/main.ts` `api.ts` `seo.ts` `styles.css`。ハブのページ一覧。

判定: 種目3 × `all` と `draws50`。出現の切替、奇偶の合計＝開催、出目表の最新行＝最新結果、前後の重なり合計＝開催−1。PC とスマホ。

### 4. 数字ページ

変更前: なし。  
変更後: `GET /api/{game}/numbers/{n}` と `/{game}/n/{nn}`。出現表・同時出現の数字からリンク。範囲外は 404。

判定: 01、最大数字、0 と max+1 が 404。ロト6 の 06。

### 5. 残りのインデックス

変更前: ハブ・最新・速報・数字ページが SPA。  
変更後: 戦略のプリレンダー対象（ハブ、latest、history、freq、pairs、shape、grid、follow、ranks、search、generate、flash 一覧、直近50速報、数字全件）。全速報は sitemap のみ可。`?period=` は canonical なし。

判定: 静的トップと下層で title が経路と一致。ステージングなら noindex。本番の robots は許可＋Sitemap。

## 出さない

- 予想投稿、購入、セット球、ガイド／FAQ
- 本番デプロイ（許可があるまで）
- 金額ランキングと予想ツールの中身の作り直し

## ローカル確認

API `http://127.0.0.1:8000`、UI `http://127.0.0.1:5174`。主戦は `/loto6/generate`。分析は `/loto6/freq` から。
