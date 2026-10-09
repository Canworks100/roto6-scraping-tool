/** フッターPR。catalog 未登録／全OFFなら何も出さない。 */

export type AffItem = {
  id: string;
  url: string;
  title: string;
  image?: string;
  price?: string;
  desc?: string;
  /** false で非表示。省略時は true */
  on?: boolean;
};

const CATALOG_URL = "/affiliate-items.json";

let catalogCache: AffItem[] | null = null;
let catalogTried = false;

function normalizeItem(row: unknown, index: number): AffItem | null {
  if (!row || typeof row !== "object") return null;
  const o = row as Record<string, unknown>;
  const url = typeof o.url === "string" ? o.url.trim() : "";
  const title = typeof o.title === "string" ? o.title.trim() : "";
  if (!url || !title) return null;
  const id =
    typeof o.id === "string" && o.id.trim()
      ? o.id.trim()
      : `item-${index + 1}`;
  return {
    id,
    url,
    title,
    image: typeof o.image === "string" && o.image.trim() ? o.image.trim() : undefined,
    price: typeof o.price === "string" && o.price.trim() ? o.price.trim() : undefined,
    desc: typeof o.desc === "string" && o.desc.trim() ? o.desc.trim() : undefined,
    on: o.on === false ? false : true,
  };
}

function parseCatalog(data: unknown): AffItem[] {
  if (!Array.isArray(data)) return [];
  return data
    .map((row, i) => normalizeItem(row, i))
    .filter((row): row is AffItem => row != null);
}

function loadItemsFromEnv(): AffItem[] {
  const json = import.meta.env.VITE_AMAZON_AFF_ITEMS?.trim();
  if (json) {
    try {
      return parseCatalog(JSON.parse(json) as unknown);
    } catch {
      /* ignore */
    }
  }
  const url = import.meta.env.VITE_AMAZON_AFF_URL?.trim();
  if (!url) return [];
  const title = import.meta.env.VITE_AMAZON_AFF_TITLE?.trim() || "Amazon.co.jp";
  return [
    {
      id: "env-1",
      url,
      title,
      image: import.meta.env.VITE_AMAZON_AFF_IMAGE?.trim() || undefined,
      price: import.meta.env.VITE_AMAZON_AFF_PRICE?.trim() || undefined,
      desc: import.meta.env.VITE_AMAZON_AFF_DESC?.trim() || undefined,
      on: true,
    },
  ];
}

async function loadCatalog(): Promise<AffItem[]> {
  if (catalogCache) return catalogCache;
  if (!catalogTried) {
    catalogTried = true;
    try {
      const res = await fetch(CATALOG_URL, { cache: "no-store" });
      if (res.ok) {
        const items = parseCatalog(await res.json());
        if (items.length) {
          catalogCache = items;
          return catalogCache;
        }
      }
    } catch {
      /* fall through */
    }
  }
  catalogCache = loadItemsFromEnv();
  return catalogCache;
}

function visibleItems(catalog: AffItem[]): AffItem[] {
  return catalog.filter((item) => item.on !== false);
}

function affCard(item: AffItem): string {
  const thumb = item.image
    ? `<img class="aff-thumb" src="${escAttr(item.image)}" alt="" width="72" height="72" loading="lazy" />`
    : `<span class="aff-thumb" aria-hidden="true"></span>`;
  const price = item.price ? `<p class="aff-price">${esc(item.price)}</p>` : "";
  const desc = item.desc ? `<p class="aff-desc">${esc(item.desc)}</p>` : "";
  return `<a class="aff-card" href="${escAttr(item.url)}" target="_blank" rel="noopener noreferrer sponsored">
    ${thumb}
    <span class="aff-body">
      <span class="aff-title">${esc(item.title)}</span>
      ${desc}
      ${price}
      <span class="aff-cta">Amazonで見る</span>
    </span>
  </a>`;
}

function renderFooterHtml(catalog: AffItem[]): string {
  const items = visibleItems(catalog);
  if (!items.length) return "";
  return `<aside class="aff-footer" aria-label="管理人のおすすめ書籍">
    <p class="aff-label">管理人のおすすめ書籍</p>
    <div class="aff-grid">${items.map(affCard).join("")}</div>
    <p class="aff-note">Amazonのアソシエイトとして、LOTO アナリティクスは適格販売により収入を得ています。</p>
  </aside>`;
}

/** shell 用。取得前は空スロットのみ。 */
export function affiliateFooter(): string {
  return `<div id="aff-slot"></div>`;
}

/** 各ページ描画後に呼ぶ。catalog を読んで枠を埋める。 */
export async function hydrateAffiliate(): Promise<void> {
  const slot = document.querySelector("#aff-slot");
  if (!slot) return;
  if (import.meta.env.DEV) {
    catalogCache = null;
    catalogTried = false;
  }
  const catalog = await loadCatalog();
  slot.innerHTML = renderFooterHtml(catalog);
}

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escAttr(s: string): string {
  return esc(s).replace(/'/g, "&#39;");
}
