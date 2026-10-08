/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SITE_ORIGIN?: string;
  /** 設定時のみフッターPRを表示（単品） */
  readonly VITE_AMAZON_AFF_URL?: string;
  readonly VITE_AMAZON_AFF_TITLE?: string;
  readonly VITE_AMAZON_AFF_IMAGE?: string;
  readonly VITE_AMAZON_AFF_PRICE?: string;
  readonly VITE_AMAZON_AFF_DESC?: string;
  /** JSON配列。設定時はこちらを優先 */
  readonly VITE_AMAZON_AFF_ITEMS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
