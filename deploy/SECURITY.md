# 公開面セキュリティ方針

- 読み取り専用: tickets / import / shutdown / 任意SQL は公開 API に出さない
- 入力検証: game・数字・limit/offset・生成口数を Pydantic で制限
- レート制限: 検索 60req/min、生成 20req/min（アプリ＋ nginx `limit_req`）
- セキュアヘッダ: CSP / X-Content-Type-Options / Referrer-Policy / Permissions-Policy /（TLS後）HSTS
- CORS: 既定は同一オリジンのみ（`public.cors_origins` が空なら CORS を開かない）
- 秘密情報: リポジトリに置かない。VPS の env / ファイル権限
- 依存更新: 定期的に `pip audit` / `npm audit`。本番は非 root（`loto`）で systemd 起動
- 収集分離: `loto-collect@.service` は Web と別プロセス
