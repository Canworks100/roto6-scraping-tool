/**
 * アフィリエイト短縮URLからタイトル・画像・価格を取り、.env.local の
 * VITE_AMAZON_AFF_ITEMS を書き換える（ローカル用）。
 *
 * 使い方:
 *   node scripts/fetch-amazon-aff.mjs https://link.amazon/... ...
 */
import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");
const catalogPath = resolve(root, "public/affiliate-items.json");

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";

async function fetchText(url) {
  const res = await fetch(url, {
    redirect: "follow",
    headers: {
      "User-Agent": UA,
      "Accept-Language": "ja-JP,ja;q=0.9",
      Accept: "text/html,application/xhtml+xml",
      Referer: "https://www.amazon.co.jp/",
    },
  });
  const html = await res.text();
  return { url: res.url, html };
}

function pick(html, re) {
  const m = html.match(re);
  return m ? m[1].trim() : "";
}

function toSl300(url) {
  if (!url) return "";
  return url.replace(/\._SL\d+_\./, "._SL300_.").replace(/\._SX\d+_\./, "._SL300_.");
}

async function resolveItem(shortUrl) {
  const landed = await fetchText(shortUrl);
  const asin =
    pick(landed.url, /\/dp\/([A-Z0-9]{10})/i) ||
    pick(landed.html, /\/dp\/([A-Z0-9]{10})/i);
  if (!asin) throw new Error(`ASIN不明: ${shortUrl}`);

  const page = await fetchText(`https://www.amazon.co.jp/dp/${asin}`);
  const title =
    pick(page.html, /id="productTitle"[^>]*>\s*([^<]+)/) ||
    pick(page.html, /property="og:title"\s+content="([^"]+)"/) ||
    asin;
  let image =
    pick(page.html, /"hiRes":"(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/) ||
    pick(page.html, /"large":"(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/) ||
    pick(page.html, /property="og:image"\s+content="([^"]+)"/);
  image = toSl300(image);
  const price = pickRetailPrice(page.html);

  const id = asin.toLowerCase();
  return {
    id,
    on: true,
    url: shortUrl,
    title,
    ...(image ? { image } : {}),
    ...(price ? { price } : {}),
  };
}

/** Audible会員表示の安値より、単行本・Kindleの価格を優先する */
function pickRetailPrice(html) {
  const swatch = pick(html, /id="tmmSwatches"([\s\S]*?)<\/ul>/) || html;
  const text = swatch
    .replace(/<script[\s\S]*?<\/script>/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ");

  const tankobon = text.match(/単行本[^￥¥]{0,40}[￥¥]\s*([\d,]+)/);
  if (tankobon) return formatYen(tankobon[1]);

  const kindle = text.match(/Kindle版[^￥¥]{0,40}[￥¥]\s*([\d,]+)/);
  if (kindle) return formatYen(kindle[1]);

  // 単行本ASINへ辿れる場合
  const pb = html.match(/\/gp\/offer-listing\/(\d{9}[\dX])\//i);
  // fallback: 買い箱。ただし Audible ページの極安は避ける
  const off = pick(html, /id="corePrice[^"]*"[\s\S]*?<span class="a-offscreen">([^<]+)<\/span>/);
  const n = parseYen(off);
  const isAudible = /\/Audible-|オーディブル|聴き放題/.test(html.slice(0, 8000));
  if (n != null && !(isAudible && n < 500)) return formatYen(String(n));

  const whole = pick(html, /class="a-price-whole">([^<]+)/);
  const wn = parseYen(whole ? `¥${whole}` : "");
  if (wn != null && !(isAudible && wn < 500)) return formatYen(String(wn));

  void pb;
  return "";
}

function parseYen(s) {
  if (!s) return null;
  const m = String(s).replace(/,/g, "").match(/[￥¥]\s*(\d+)/);
  return m ? Number(m[1]) : null;
}

function formatYen(digits) {
  const n = Number(String(digits).replace(/,/g, ""));
  if (!Number.isFinite(n)) return "";
  return `¥${n.toLocaleString("ja-JP")}`;
}

const links = process.argv.slice(2);
if (!links.length) {
  console.error("Usage: node scripts/fetch-amazon-aff.mjs <link>...");
  process.exit(1);
}

const prevOn = new Map();
if (existsSync(catalogPath)) {
  try {
    const prev = JSON.parse(readFileSync(catalogPath, "utf8"));
    if (Array.isArray(prev)) {
      for (const row of prev) {
        if (row && typeof row.url === "string") prevOn.set(row.url, row.on !== false);
      }
    }
  } catch {
    /* ignore */
  }
}

const items = [];
for (const link of links) {
  process.stderr.write(`fetch ${link}\n`);
  const item = await resolveItem(link);
  if (prevOn.has(item.url)) item.on = prevOn.get(item.url);
  items.push(item);
}

writeFileSync(catalogPath, `${JSON.stringify(items, null, 2)}\n`);
console.log(JSON.stringify(items, null, 2));
console.log(`wrote ${catalogPath}`);
