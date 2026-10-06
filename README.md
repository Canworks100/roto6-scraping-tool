# LOTOデータベース — 公開サイト＋デスクトップ台帳

みずほ銀行の当せん番号案内から種目別に全回を収集し、**公開サイト（FastAPI + Vite/TS）**で履歴・数字検索・出現傾向・口数指定の頻度ベース組み合わせ生成を提供する。購入台帳は従来どおりローカル専用。

対象ページ:

- [当せん番号案内（ロト6）](https://www.mizuhobank.co.jp/takarakuji/check/loto/loto6/index.html)
- [先月以前の当せん番号](https://www.mizuhobank.co.jp/takarakuji/check/loto/backnumber/index.html)

月別ページとバックナンバー詳細は、公式スクリプトが次のCSVを読んで表を作っている。このツールはそのCSVを取得する。

- 直近の回号一覧: `/retail/takarakuji/loto/loto6/csv/loto6.csv`
- 各回: `/retail/takarakuji/loto/loto6/csv/A102{回号4桁}.CSV`

取得済みの回は保存しない。失敗した回はログに残し、再実行で続きから取る。

## 公開サイト（ローカル開発）

```bash
# 1) 旧DBがあればマルチゲームDBへ
PYTHONPATH=src python -m loto6 migrate-legacy

# 2) API
PYTHONPATH=src:apps/api .venv/bin/uvicorn loto_api.main:app --reload --host 127.0.0.1 --port 8000
# または
PYTHONPATH=src python -m loto6 serve-api --reload

# 3) UI
cd apps/web && npm install && npm run dev
```

- API: `/api/games`, `/api/{game}/history|search|trends`, `POST /api/{game}/generate`
- DB: `data/loto.sqlite`（`game` + `draw_no`）
- VPS 手順（本番反映は明示許可後）: `deploy/README.md`

### 収集（種目別）

```bash
PYTHONPATH=src python -m loto6 collect --game loto6 --all
PYTHONPATH=src python -m loto6 collect --game loto7 --all
PYTHONPATH=src python -m loto6 collect --game miniloto --all
```

## 収支ノート（デスクトップ・別系統）

デスクトップの `loto6-app` をダブルクリックするか、次でウィンドウが開きます。

```bash
./loto6-app
# または
PYTHONPATH=src python -m loto6 app
```

買った回・数字・口数・金額を記録すると、取り込み済みの当せん結果から等級と当選額を計算し、損益を出します。データは **`data/loto6.sqlite`（従来DB）** に残ります。公開用の `data/loto.sqlite` とは分離しています。

## 公式サイトの購入履歴

「公式サイトから取り込む」を押すと、Chromeで[宝くじ公式サイトのマイページ](https://www.takarakuji-official.jp/mypage/)が開きます。そこでログインし、購入履歴を表示すると、ロト6の回号・数字・口数を記録します。同じ口は二重に入れません。メールアドレスとパスワードは公式サイトの画面にだけ入力し、このアプリには保存しません。2回目以降は、同じChromeにログインが残っていればそのまま取り込めます。

みずほダイレクトで買った分は、銀行の購入明細照会にあります。そちらのログイン情報をアプリに預ける取り込みはしません。

## 準備

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 分析（CLI）

```bash
PYTHONPATH=src python -m loto6 analyze --game loto6
```

## 設定

種目定義は `config.yaml` の `games.*`。公開レート制限は `public.*`。

## 出力

| パス | 内容 |
| --- | --- |
| `data/loto.sqlite` | 公開・マルチゲームDB |
| `data/loto6.sqlite` | デスクトップ台帳用（従来） |
| `apps/web/dist/` | 公開フロントのビルド成果物 |
| `logs/loto6.log` | 取得ログ |

## テスト

```bash
PYTHONPATH=src python -m unittest discover -s tests
```
