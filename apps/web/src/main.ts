import "./styles.css";
import * as api from "./api";
import type { DrawItem, GameInfo, PairRow, PrizeRankGroup, PrizeRankItem, TrendsPayload } from "./api";
import {
  absoluteUrl,
  drawResultJsonLd,
  eyecatchApiPath,
  eyecatchPath,
  flashNewsHeadline,
  flashNewsJsonLd,
  gameLabel,
  PAGE_LEAD,
  setBreadcrumbJsonLd,
  setJsonLd,
  setSeo,
  type BreadcrumbItem,
} from "./seo";
import { isLegalPage, legalHtml } from "./legal";
import { guideHtml, guideTitle, isGuideSlug } from "./guides";
import { loadFavorites, saveFavorites } from "./favorites";
import { affiliateFooter, hydrateAffiliate } from "./affiliate";
import { runSimu, SimuError, type SimuGameDef } from "./simu";

const root = document.querySelector("#app")!;
let games: GameInfo[] = [];
let selected: number[] = [];
let historyOffset = 0;
let historyTotal = 0;
let flashOffset = 0;
let flashTotal = 0;
let renderSeq = 0;

function paint(seq: number, html: string): boolean {
  if (seq !== renderSeq) return false;
  root.innerHTML = html;
  bindLinks();
  return true;
}

type Route = { game?: string; view: string; drawNo?: number; number?: number };

function parseRoute(): Route {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { view: "home" };
  if (parts[0] === "simu") return { view: "simu" };
  if (isLegalPage(parts[0])) return { view: parts[0] };
  if (parts[1] === "flash") {
    const raw = parts[2] ? Number(parts[2]) : undefined;
    return { game: parts[0], view: "flash", drawNo: raw && Number.isFinite(raw) ? raw : undefined };
  }
  if (parts[1] === "n") {
    const raw = parts[2] ? Number(parts[2]) : NaN;
    return { game: parts[0], view: "number", number: Number.isFinite(raw) ? raw : undefined };
  }
  if (parts[1] === "guide") {
    return { game: parts[0], view: "guide", number: undefined, drawNo: undefined };
  }
  let view = parts[1] || "hub";
  if (view === "trends") view = "freq";
  return { game: parts[0], view };
}

/** グローバルナビ（種目共通） */
const GAME_PAGES: [string, string][] = [
  ["latest", "最新結果"],
  ["generate", "次回予想"],
  ["history", "結果一覧"],
  ["analyze", "分析"],
  ["combo", "予想診断"],
  ["simu", "シミュレーター"],
];

const ANALYSIS_PAGES: [string, string, string][] = [
  ["freq", "出現回数", "よく出る数字をランキングで見られます。"],
  ["pairs", "組み合わせ", "3個以上一緒に出やすい組を回数順にまとめます。"],
  ["shape", "奇数偶数", "奇数偶数の分かれ方と合計の出方を見られます。"],
  ["grid", "出目表", "直近の本数字を表で縦に並べて追えます。"],
  ["follow", "前回を含む回数", "前回と同じ数字がまた出た回数を数字ごとに見られます。"],
];

const RESULT_LINKS: [string, string][] = [
  ["latest", "最新結果"],
  ["flash", "速報"],
  ["history", "結果一覧"],
  ["ranks", "金額ランキング"],
  ["search", "数字検索"],
];

const PREDICT_LINKS: [string, string][] = [
  ["generate", "次回予想"],
  ["combo", "予想診断"],
];

function navHighlight(view?: string): string | undefined {
  if (!view) return view;
  if (view === "flash") return "latest";
  if (view === "ranks" || view === "search") return "history";
  if (
    view === "freq" ||
    view === "pairs" ||
    view === "shape" ||
    view === "grid" ||
    view === "follow" ||
    view === "trends"
  ) {
    return "analyze";
  }
  return view;
}

const VIEW_CRUMB_LABEL: Record<string, string> = {
  analyze: "分析",
  freq: "出現回数",
  pairs: "組み合わせ",
  shape: "奇数偶数",
  grid: "出目表",
  follow: "前回を含む回数",
  latest: "最新結果",
  generate: "次回予想",
  history: "結果一覧",
  combo: "予想診断",
  simu: "ロト購入シミュレーター",
  flash: "速報",
  ranks: "金額ランキング",
  search: "数字検索",
};

const ANALYZE_LEAF = new Set(["freq", "pairs", "shape", "grid", "follow"]);

type CrumbOpts = { drawNo?: number; number?: number; guideSlug?: string };

function crumbTrail(game: string, view: string, opts: CrumbOpts = {}): BreadcrumbItem[] {
  const info = games.find((g) => g.id === game);
  const label = info?.label || gameLabel(game);
  const items: BreadcrumbItem[] = [
    { name: "ホーム", path: "/" },
    { name: label, path: `/${game}` },
  ];
  if (view === "hub") return items;
  if (view === "guide") {
    const slug = opts.guideSlug;
    const title = slug && isGuideSlug(slug) ? guideTitle(slug) : "ガイド";
    items.push({ name: title });
    return items;
  }
  if (view === "number") {
    const n = opts.number;
    items.push({ name: "分析", path: viewPath(game, "analyze") });
    items.push({ name: "出現回数", path: viewPath(game, "freq") });
    items.push({ name: n != null ? pad2(n) : "数字" });
    return items;
  }
  if (ANALYZE_LEAF.has(view)) {
    items.push({ name: "分析", path: viewPath(game, "analyze") });
    items.push({ name: VIEW_CRUMB_LABEL[view] || view });
    return items;
  }
  if (view === "analyze") {
    items.push({ name: "分析" });
    return items;
  }
  if (view === "flash" && opts.drawNo != null) {
    items.push({ name: "速報", path: viewPath(game, "flash") });
    items.push({ name: formatDraw(opts.drawNo) });
    return items;
  }
  const leaf = VIEW_CRUMB_LABEL[view];
  if (leaf) {
    items.push({ name: leaf });
    return items;
  }
  return items;
}

function crumbHtml(items: BreadcrumbItem[]): string {
  if (items.length < 2) return "";
  const parts = items.map((it, i) => {
    const last = i === items.length - 1;
    if (last || !it.path) return `<span aria-current="page">${esc(it.name)}</span>`;
    return `<a href="${it.path}" data-link>${esc(it.name)}</a>`;
  });
  return `<nav class="crumb" aria-label="パンくず">${parts.join("<span aria-hidden=\"true\"> / </span>")}</nav>`;
}

function relatedBox(game: string, links: [string, string][]): string {
  if (!links.length) return "";
  return `<div class="box"><h2>関連</h2><div class="inner related-links">
    ${links.map(([id, label]) => `<p><a href="${viewPath(game, id)}" data-link>${label}</a></p>`).join("")}
  </div></div>`;
}

function relatedFor(view: string, game: string, label: string): string {
  const analyzeTop: [string, string] = ["analyze", `${label}の分析`];
  if (view === "freq") {
    return relatedBox(game, [analyzeTop, ["pairs", "組み合わせ"], ["shape", "奇数偶数"]]);
  }
  if (view === "pairs") {
    return relatedBox(game, [analyzeTop, ["freq", "出現回数"], ["shape", "奇数偶数"]]);
  }
  if (view === "shape") {
    return relatedBox(game, [analyzeTop, ["freq", "出現回数"], ["pairs", "組み合わせ"]]);
  }
  if (view === "grid") {
    return relatedBox(game, [analyzeTop, ["freq", "出現回数"], ["follow", "前回を含む回数"]]);
  }
  if (view === "follow") {
    return relatedBox(game, [analyzeTop, ["freq", "出現回数"], ["grid", "出目表"]]);
  }
  if (view === "analyze") {
    return relatedBox(game, [
      ["freq", "出現回数"],
      ["pairs", "組み合わせ"],
      ["generate", "次回予想"],
    ]);
  }
  if (view === "history") {
    return relatedBox(game, [
      ["ranks", "金額ランキング"],
      ["search", "数字検索"],
      ["latest", "最新結果"],
    ]);
  }
  if (view === "ranks") {
    return relatedBox(game, [
      ["history", "結果一覧"],
      ["search", "数字検索"],
      ["latest", "最新結果"],
    ]);
  }
  if (view === "search") {
    return relatedBox(game, [
      ["history", "結果一覧"],
      ["ranks", "金額ランキング"],
      ["latest", "最新結果"],
    ]);
  }
  if (view === "latest") {
    return relatedBox(game, [
      ["flash", "速報"],
      ["history", "結果一覧"],
      ["generate", "次回予想"],
    ]);
  }
  if (view === "flash") {
    return relatedBox(game, [
      ["latest", "最新結果"],
      ["history", "結果一覧"],
    ]);
  }
  if (view === "generate") {
    return relatedBox(game, [
      ["combo", "予想診断"],
      ["latest", "最新結果"],
    ]);
  }
  if (view === "combo") {
    return `<div class="box"><h2>関連</h2><div class="inner related-links">
      <p><a href="${viewPath(game, "generate")}" data-link>次回予想</a></p>
      <p><a href="${viewPath(game, "latest")}" data-link>最新結果</a></p>
      <p><a href="/simu?game=${encodeURIComponent(game)}" data-link>ロト購入シミュレーター</a></p>
    </div></div>`;
  }
  return "";
}

function viewPath(game: string, view: string, drawNo?: number): string {
  if (view === "home") return "/";
  if (view === "hub") return `/${game}`;
  if (view === "flash") return drawNo ? `/${game}/flash/${drawNo}` : `/${game}/flash`;
  if (view === "number" && drawNo) return `/${game}/n/${pad2(drawNo)}`;
  return `/${game}/${view}`;
}

if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}

/** リンク遷移の描画が終わるまで、先頭へ戻す */
let scrollToTopOnPaint = false;

function scrollPageTop() {
  window.scrollTo(0, 0);
}

function navigate(path: string) {
  history.pushState({}, "", path);
  scrollToTopOnPaint = true;
  void render();
}

function esc(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function formatDate(iso: string | null | undefined): string {
  if (!iso || iso === "undefined") return "—";
  const matched = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!matched) return iso;
  return `${matched[1]}年${Number(matched[2])}月${Number(matched[3])}日`;
}

function formatDraw(n: number | null | undefined): string {
  if (n == null) return "—";
  return `第${String(n).padStart(4, "0")}回`;
}

function formatYen(n: number | null | undefined): string {
  if (n == null) return "未取得";
  return `${n.toLocaleString("ja-JP")}円`;
}

function formatCountOrMissing(n: number | null | undefined): string {
  if (n == null) return "未取得";
  return formatCount(n);
}

function formatYenOku(n: number): string {
  const oku = Math.floor(n / 100_000_000);
  const man = Math.floor((n % 100_000_000) / 10_000);
  const rest = n % 10_000;
  let out = "";
  if (oku) out += `${oku}億`;
  if (man) out += `${man}万`;
  if (rest || !out) out += `${rest}`;
  return `${out}円`;
}

function carryBanner(label: string, amount: number): string {
  return `<div class="co-banner">
    <p class="co-banner-name">${esc(label)}</p>
    <p class="co-banner-lab">キャリーオーバー<br />発生中</p>
    <p class="co-banner-amt">${formatYenOku(amount)}</p>
  </div>`;
}

function formatCount(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toLocaleString("ja-JP")}口`;
}

function formatRank(n: number): string {
  return `${n}位`;
}

function formatTimes(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toLocaleString("ja-JP")}回`;
}

function prizeHeaders(grades: number): string {
  return Array.from({ length: grades }, (_, i) => `<th class="num">${i + 1}等</th>`).join("");
}

function prizeCells(item: DrawItem, grades: number): string {
  const byGrade = new Map((item.prizes || []).map((p) => [p.grade, p]));
  return Array.from({ length: grades }, (_, i) => {
    const prize = byGrade.get(i + 1);
    return `<td class="prize"><span>${formatCount(prize?.count)}</span><small>${formatYen(prize?.amount)}</small></td>`;
  }).join("");
}

function carryCell(item: DrawItem): string {
  const amount = item.carryover_amount;
  if (amount == null) return `<td class="num">—</td>`;
  const on = amount > 0 ? " carry-on" : "";
  return `<td class="num${on}">${formatYen(amount)}</td>`;
}

function numberBalls(numbers: number[], highlight: number[] = []): string {
  const hi = new Set(highlight);
  return `<span class="balls"><span class="balls-main">${numbers
    .map((n) => `<span class="ball${hi.has(n) ? " match" : ""}">${pad2(n)}</span>`)
    .join("")}</span></span>`;
}

function ballsHtml(item: DrawItem, highlight: number[] = []): string {
  const hi = new Set(highlight);
  const mains = item.numbers
    .map((n) => `<span class="ball${hi.has(n) ? " match" : ""}">${pad2(n)}</span>`)
    .join("");
  const bonus =
    item.bonus2 != null
      ? `<span class="bonus" title="ボーナス">${pad2(item.bonus)}</span><span class="bonus" title="ボーナス">${pad2(item.bonus2)}</span>`
      : `<span class="bonus" title="ボーナス">${pad2(item.bonus)}</span>`;
  return `<span class="balls"><span class="balls-main">${mains}</span><span class="bonus-group"><span class="bonus-lab">ボーナス</span>${bonus}</span></span>`;
}

function drawRow(item: DrawItem, highlight: number[] = [], extra = "", game?: string): string {
  const drawCell = game
    ? `<td class="num"><a href="/${game}/flash/${item.draw_no}" data-link>${formatDraw(item.draw_no)}</a></td>`
    : `<td class="num">${formatDraw(item.draw_no)}</td>`;
  return `<tr>
    ${drawCell}
    <td>${formatDate(item.draw_date)}</td>
    <td class="nums">${ballsHtml(item, highlight)}</td>
    ${extra}
  </tr>`;
}

function pageLinks(game: string, activeView?: string): string {
  const highlight = navHighlight(activeView);
  return GAME_PAGES.map(([id, label]) => {
    const on = highlight === id;
    const href = id === "simu" ? "/simu" : viewPath(game, id);
    return `<a href="${href}" class="${on ? "active" : ""}"${on ? ' aria-current="page"' : ""} data-link>${label}</a>`;
  }).join("");
}

let pagesNavScroll = 0;

function rememberPagesNav() {
  const nav = document.querySelector(".nav-pages");
  if (nav) pagesNavScroll = nav.scrollLeft;
}

function restorePagesNav() {
  const nav = document.querySelector(".nav-pages");
  if (!nav) return;
  const apply = () => {
    nav.scrollLeft = pagesNavScroll;
  };
  apply();
  requestAnimationFrame(apply);
  nav.addEventListener(
    "scroll",
    () => {
      pagesNavScroll = nav.scrollLeft;
    },
    { passive: true },
  );
}

function howto(text: string): string {
  return `<p class="howto">${text}</p>`;
}

function crumbOptsFromLocation(view?: string): CrumbOpts {
  const parts = location.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
  const opts: CrumbOpts = {};
  if (view === "flash" && parts[1] === "flash" && parts[2]) {
    const n = Number(parts[2]);
    if (Number.isFinite(n)) opts.drawNo = n;
  }
  if (view === "number" && parts[1] === "n" && parts[2]) {
    const n = Number(parts[2]);
    if (Number.isFinite(n)) opts.number = n;
  }
  if (view === "guide" && parts[1] === "guide" && parts[2]) {
    opts.guideSlug = parts[2];
  }
  return opts;
}

function shell(inner: string, activeGame?: string, activeView?: string): string {
  rememberPagesNav();
  const switchView = activeView && activeView !== "home" ? activeView : "hub";
  const onSimu = activeView === "simu";
  const gameLinks = games
    .map((g) => {
      const href = onSimu
        ? `/simu?game=${encodeURIComponent(g.id)}`
        : activeGame
          ? viewPath(g.id, switchView === "number" ? "hub" : switchView === "flash" ? "flash" : switchView)
          : `/${g.id}`;
      const on = activeGame === g.id;
      return `<a href="${href}" class="${on ? "active" : ""}"${on ? ' aria-current="page"' : ""} data-link>${g.label}</a>`;
    })
    .join("");
  const navGame = activeGame || games[0]?.id || "loto6";
  const pages = activeGame || onSimu ? pageLinks(navGame, activeView) : "";
  const pagesNav = pages ? `<nav class="nav-pages" aria-label="ページ">${pages}</nav>` : "";
  const showCrumb =
    !!activeView &&
    activeView !== "home" &&
    !isLegalPage(activeView) &&
    (onSimu || !!activeGame);
  let crumbs: BreadcrumbItem[] = [];
  if (onSimu) {
    crumbs = [
      { name: "ホーム", path: "/" },
      { name: "ロト購入シミュレーター" },
    ];
  } else if (showCrumb && activeGame) {
    crumbs = crumbTrail(activeGame, activeView === "trends" ? "freq" : activeView, crumbOptsFromLocation(activeView));
  }
  setBreadcrumbJsonLd(crumbs.length ? crumbs : null);
  const crumbNav = crumbHtml(crumbs);
  const marqueeA = "LOTO ANALYTICS · 当選番号 · 出現回数 · FLASH · ";
  const marqueeB = "ロト6 · ロト7 · ミニロト · 次回予想 · 速報 · ";
  return `
    <div class="bg-marquee" aria-hidden="true">
      <div class="bg-marquee-row">
        <div class="bg-marquee-track">${`<span>${marqueeA}</span>`.repeat(4)}</div>
      </div>
      <div class="bg-marquee-row bg-marquee-row--rev">
        <div class="bg-marquee-track">${`<span>${marqueeB}</span>`.repeat(4)}</div>
      </div>
    </div>
    <header class="site-head">
      <div class="topbar">
        <a class="brand" href="/" data-link>LOTO <span>アナリティクス</span></a>
        <nav class="nav-games" aria-label="ロト">${gameLinks}</nav>
      </div>
      ${pagesNav}
    </header>
    <main class="body">${crumbNav}${inner}</main>
    <footer class="footer">
      ${affiliateFooter()}
      <nav class="footer-nav">
        <a href="/about" data-link>このサイトについて</a>
        <a href="/disclaimer" data-link>免責事項</a>
        <a href="/privacy" data-link>プライバシーポリシー</a>
        <a href="/terms" data-link>利用規約</a>
        <a href="/contact" data-link>お問い合わせ</a>
      </nav>
      <p class="copy">© 2026 LOTO アナリティクス</p>
    </footer>
  `;
}

function renderNotFound(message = "お探しのページは見つかりませんでした。") {
  setSeo(location.pathname, {
    noindex: true,
    title: "ページが見つかりません｜LOTO アナリティクス",
    description:
      "お探しのページは見つかりませんでした。トップからロト6・ロト7・ミニロトの各ページへお進みください。",
  });
  setJsonLd(null);
  root.innerHTML = shell(
    `<div class="box"><h1>ページが見つかりません</h1><p class="muted">${esc(message)}</p>
     <p class="flash-actions"><a class="btn btn-primary" href="/" data-link>トップへ</a></p></div>`,
  );
  bindLinks();
}

async function render() {
  const seq = ++renderSeq;
  const pathParts = location.pathname.replace(/\/+$/, "").split("/").filter(Boolean);

  // `/trends` → `/freq`（正規URLへ）
  if (pathParts[1] === "trends") {
    const dest = location.hash === "#amount" ? `/${pathParts[0]}/ranks` : `/${pathParts[0]}/freq`;
    history.replaceState({}, "", dest);
  }

  // `/n/1` → `/n/01`
  if (pathParts[1] === "n" && pathParts[2] && !/^\d{2}$/.test(pathParts[2])) {
    const n = Number(pathParts[2]);
    if (Number.isFinite(n) && n >= 1) {
      history.replaceState({}, "", `/${pathParts[0]}/n/${pad2(n)}`);
    }
  }

  const route = parseRoute();

  if (isLegalPage(route.view)) {
    setSeo(location.pathname);
    setJsonLd(null);
    paint(seq, shell(legalHtml(route.view), undefined, route.view));
    return;
  }

  if (!games.length) {
    try {
      games = (await api.listGames()).games;
    } catch (err) {
      paint(seq, shell(`<p class="error">${(err as Error).message}</p>`));
      return;
    }
  }
  if (seq !== renderSeq) return;

  if (route.view === "simu") {
    setSeo(location.pathname);
    setJsonLd(null);
    await renderSimu(seq);
    return;
  }

  if (route.view === "home") {
    await renderHome(seq);
    return;
  }

  const game = route.game;
  const info = games.find((g) => g.id === game);
  if (!game || !info) {
    renderNotFound("指定したロトが見つかりません。");
    return;
  }

  const allowed = [
    "hub",
    "latest",
    "flash",
    "history",
    "search",
    "analyze",
    "freq",
    "pairs",
    "shape",
    "grid",
    "follow",
    "ranks",
    "generate",
    "trends",
    "number",
    "combo",
    "guide",
  ];
  if (!allowed.includes(route.view)) {
    renderNotFound();
    return;
  }
  const view = route.view === "trends" ? "freq" : route.view;

  setSeo(location.pathname);
  setJsonLd(null);

  try {
    if (view === "hub") await renderHub(game, info, seq);
    else if (view === "latest") await renderLatest(game, info, seq);
    else if (view === "flash") await renderFlash(game, info, route.drawNo);
    else if (view === "history") await renderHistory(game, info);
    else if (view === "search") await renderSearch(game, info);
    else if (view === "combo") await renderCombo(game, info);
    else if (view === "analyze") await renderAnalyze(game, info);
    else if (view === "freq") await renderFreq(game, info);
    else if (view === "pairs") await renderPairs(game, info);
    else if (view === "shape") await renderShape(game, info);
    else if (view === "grid") await renderGrid(game, info);
    else if (view === "follow") await renderFollow(game, info);
    else if (view === "number") await renderNumber(game, info, route.number);
    else if (view === "ranks") await renderRanks(game, info);
    else if (view === "guide") await renderGuide(game, info);
    else await renderGenerate(game, info);
  } catch (err) {
    if (seq !== renderSeq) return;
    const msg = (err as Error).message || "";
    if (/404|見つかり|not found/i.test(msg)) {
      renderNotFound(msg);
      return;
    }
    paint(seq, shell(`<p class="error">${esc(msg)}</p>`, game, view));
  }
}

async function renderGuide(game: string, info: GameInfo) {
  const slug = location.pathname.split("/").filter(Boolean)[2] || "";
  if (!isGuideSlug(slug)) {
    renderNotFound("指定したガイドが見つかりません。");
    return;
  }
  setSeo(location.pathname);
  root.innerHTML = shell(
    `${guideHtml(info.label, slug)}
    <div class="box"><h2>関連</h2><div class="inner">
      <p><a href="/${game}/guide/how-to-buy" data-link>${info.label} 買い方</a></p>
      <p><a href="/${game}/guide/odds" data-link>${info.label} 確率</a></p>
      <p><a href="/${game}/guide/faq" data-link>${info.label} FAQ</a></p>
      <p><a href="/${game}" data-link>${info.label}トップ</a></p>
    </div></div>`,
    game,
    "hub",
  );
  bindLinks();
}

const HOME_QUICK: [string, string][] = [
  ["latest", "最新結果"],
  ["generate", "次回予想"],
  ["freq", "出現回数"],
  ["history", "結果一覧"],
  ["flash", "速報"],
];

function gameChipNav(game: string, label: string, compact = false): string {
  const items = compact ? HOME_QUICK : GAME_PAGES;
  const pages = items
    .map(([id, title]) => `<a href="${viewPath(game, id)}" data-link>${title}</a>`)
    .join("");
  return `<nav class="chip-nav" aria-label="${esc(label)}のページ">${pages}</nav>`;
}

function hubSection(title: string, linksHtml: string): string {
  return `<section class="game-block-sec hub-sec">
    <h3>${esc(title)}</h3>
    <ul class="hub-link-list">${linksHtml}</ul>
  </section>`;
}

function hubLink(game: string, id: string, title: string, note?: string): string {
  const noteHtml = note ? `<span class="hub-link-note">${esc(note)}</span>` : "";
  return `<li><a href="${viewPath(game, id)}" data-link>${esc(title)}</a>${noteHtml}</li>`;
}

function homeGameCardHtml(opts: {
  game: string;
  label: string;
  latest: DrawItem | null;
  pick: api.WeekPick | null;
}): string {
  const { game, label, latest, pick } = opts;
  const latestLine = latest
    ? `${formatDraw(latest.draw_no)}（${formatDate(latest.draw_date)}）`
    : "—";
  const nextLine = pick
    ? `${formatDraw(pick.next_draw_no)}（${formatDate(pick.next_draw_date)}）`
    : "—";
  return `<article class="home-card">
    <h2 class="home-card-lab"><a href="/${game}" data-link>${esc(label)}</a></h2>
    <section class="home-card-feat">
      <p class="home-card-k"><span>最新の当選番号</span></p>
      <p class="home-card-v">${esc(latestLine)}</p>
      <div class="home-card-balls">${latest ? ballsHtml(latest) : "—"}</div>
      <p class="home-card-more"><a href="${viewPath(game, "latest")}" data-link>最新結果をみる</a></p>
    </section>
    <section class="home-card-feat">
      <p class="home-card-k"><span>次回予想</span></p>
      <p class="home-card-v">${esc(nextLine)}</p>
      <div class="home-card-balls">${pick ? numberBalls(pick.next) : "—"}</div>
      <p class="home-card-more"><a href="${viewPath(game, "generate")}" data-link>次回予想をみる</a></p>
    </section>
    <div class="home-card-more-nav">${gameChipNav(game, label, true)}</div>
  </article>`;
}

function gameBlockHtml(opts: {
  game: string;
  label: string;
  headingLevel: "h1" | "h2";
  latest: DrawItem | null;
  pick: api.WeekPick | null;
}): string {
  const { game, label, headingLevel: H, latest, pick } = opts;
  const latestLine = latest
    ? `${formatDraw(latest.draw_no)}（${formatDate(latest.draw_date)}）`
    : "—";
  const nextLine = pick
    ? `${formatDraw(pick.next_draw_no)}（抽せん日 ${formatDate(pick.next_draw_date)}）`
    : "—";
  const resultLinks = RESULT_LINKS.map(([id, title]) => hubLink(game, id, title)).join("");
  const analyzeLinks =
    hubLink(game, "analyze", "分析トップ", "出現・組み合わせなど") +
    hubLink(game, "freq", "出現回数") +
    hubLink(game, "pairs", "組み合わせ");
  const predictLinks = PREDICT_LINKS.map(([id, title]) => hubLink(game, id, title)).join("");
  const simuLinks = `<li><a href="/simu?game=${encodeURIComponent(game)}" data-link>ロト購入シミュレーター</a><span class="hub-link-note">疑似購入で速攻結果</span></li>`;
  const guides = `<section class="game-block-sec hub-sec">
    <h3>ガイド</h3>
    <ul class="hub-link-list">
      <li><a href="/${game}/guide/how-to-buy" data-link>買い方</a></li>
      <li><a href="/${game}/guide/odds" data-link>確率</a></li>
      <li><a href="/${game}/guide/faq" data-link>FAQ</a></li>
    </ul>
  </section>`;
  return `<article class="game-block box">
    <${H} class="game-block-title">${esc(label)}</${H}>
    <section class="game-block-sec">
      <h3>${esc(label)}｜最新の当選番号</h3>
      <p class="muted">${esc(latestLine)}</p>
      <div class="flash-balls">${latest ? ballsHtml(latest) : "—"}</div>
    </section>
    <section class="game-block-sec">
      <h3>${esc(label)}｜次回予想</h3>
      <p class="muted">${esc(nextLine)}</p>
      <div class="flash-balls">${pick ? numberBalls(pick.next) : "—"}</div>
    </section>
    ${hubSection("結果", resultLinks)}
    ${hubSection("分析", analyzeLinks)}
    ${hubSection("予想", predictLinks)}
    ${hubSection("シミュレーター", simuLinks)}
    ${guides}
  </article>`;
}

async function loadLatestAndPick(game: string): Promise<{
  latest: DrawItem | null;
  pick: api.WeekPick | null;
}> {
  let latest: DrawItem | null = null;
  let pick: api.WeekPick | null = null;
  try {
    latest = (await api.latest(game)).item;
  } catch {
    /* keep null */
  }
  try {
    pick = await api.weekPick(game);
  } catch {
    /* keep null */
  }
  return { latest, pick };
}

async function renderHome(seq: number) {
  setSeo("/");
  setJsonLd(null);
  const cards = [];
  const hubLinks = [];
  for (const g of games) {
    if (seq !== renderSeq) return;
    const { latest, pick } = await loadLatestAndPick(g.id);
    cards.push(
      homeGameCardHtml({
        game: g.id,
        label: g.label,
        latest,
        pick,
      }),
    );
    hubLinks.push(
      `<li><a href="/${g.id}" data-link>${esc(g.label)}のページへ</a></li>`,
    );
  }
  paint(
    seq,
    shell(
      `
    <section class="home-fv">
      <header class="hub-head">
        <h1 class="hub-title">LOTO アナリティクス</h1>
        <p class="hub-lead">${esc(PAGE_LEAD.home)}</p>
      </header>
      <div class="home-kpi">${cards.join("")}</div>
    </section>
    <section class="box home-dirs">
      <h2>くじ種別</h2>
      <div class="inner"><ul class="hub-link-list">${hubLinks.join("")}</ul></div>
    </section>
  `,
      undefined,
      "home",
    ),
  );
}

async function renderAnalyze(game: string, info: GameInfo) {
  setSeo(`/${game}/analyze`);
  const items = ANALYSIS_PAGES.map(
    ([id, title, blurb]) =>
      `<li class="analyze-item">
        <a href="${viewPath(game, id)}" data-link>${esc(title)}</a>
        <p class="muted">${esc(blurb)}</p>
      </li>`,
  ).join("");
  root.innerHTML = shell(
    `<div class="box">
      <h1>${info.label} 分析</h1>
      ${howto("出現の様子や組み合わせなど、傾向を見るページへの入口です。")}
      <ul class="analyze-list">${items}</ul>
    </div>
    ${relatedFor("analyze", game, info.label)}`,
    game,
    "analyze",
  );
  bindLinks();
}

async function renderHub(game: string, info: GameInfo, seq: number) {
  setSeo(`/${game}`);
  const { latest, pick } = await loadLatestAndPick(game);
  if (seq !== renderSeq) return;
  paint(
    seq,
    shell(
      `
    <section class="hub">
      ${gameBlockHtml({
        game,
        label: info.label,
        headingLevel: "h1",
        latest,
        pick,
      })}
    </section>
  `,
      game,
      "hub",
    ),
  );
}

async function renderLatest(game: string, info: GameInfo, seq: number) {
  const { item } = await api.latest(game);
  if (seq !== renderSeq) return;
  const prizes = (item.prizes || []).filter((p) => p.grade <= info.prize_grades);
  let pick: api.WeekPick | null = null;
  try {
    pick = await api.weekPick(game);
  } catch {
    pick = null;
  }
  if (seq !== renderSeq) return;
  setSeo(`/${game}/latest`);
  setJsonLd(
    drawResultJsonLd({
      label: info.label,
      drawNo: item.draw_no,
      drawDate: item.draw_date,
      numbers: item.numbers,
      url: absoluteUrl(`/${game}/latest`),
    }),
  );
  paint(
    seq,
    shell(
      `
    <div class="flash">
      <p class="flash-kicker">最新結果</p>
      <h1 class="flash-title">${info.label} 当選番号</h1>
      <p class="muted">${formatDraw(item.draw_no)}（${formatDate(item.draw_date)}）</p>
      <div class="flash-balls">${ballsHtml(item)}</div>
      ${
        prizes.some((p) => p.amount != null || p.count != null)
          ? `<dl class="flash-prizes">${prizes
              .map(
                (p) => `<div>
              <dt>${p.grade}等</dt>
              <dd><strong>${p.amount == null ? "—" : formatYen(p.amount)}</strong>${p.count == null ? "" : `<span>${formatCount(p.count)}</span>`}</dd>
            </div>`,
              )
              .join("")}</dl>`
          : ""
      }
      <ul class="flash-meta">
        ${item.sales_amount == null ? "" : `<li>販売実績 ${formatYen(item.sales_amount)}</li>`}
        <li>キャリーオーバー ${formatYen(item.carryover_amount)}</li>
      </ul>
      <p class="flash-actions">
        <a class="btn btn-primary" href="/${game}/flash/${item.draw_no}" data-link>この回の速報</a>
        <a class="btn btn-ghost" href="/${game}/flash" data-link>速報一覧</a>
        <a class="btn btn-ghost" href="/${game}" data-link>${info.label}</a>
      </p>
    </div>
    <div class="box">
      <h2>${info.label}｜次回予想</h2>
      <div class="inner">
        ${
          pick
            ? `<p class="muted">${formatDraw(pick.next_draw_no)}（抽せん日 ${formatDate(pick.next_draw_date)}）</p>
               <div class="flash-balls">${numberBalls(pick.next)}</div>
               <p class="flash-actions">
                 <a class="btn btn-primary" href="/${game}/generate" data-link>口数で作成</a>
                 <a class="btn btn-ghost" href="/${game}/generate" data-link>次回予想ページ</a>
               </p>`
            : `<p class="muted">次回予想を読み込めませんでした。</p>
               <p class="flash-actions"><a class="btn btn-primary" href="/${game}/generate" data-link>次回予想ページ</a></p>`
        }
      </div>
    </div>
    ${relatedFor("latest", game, info.label)}
  `,
      game,
      "latest",
    ),
  );
}

async function renderFlash(game: string, info: GameInfo, drawNo?: number) {
  if (drawNo) {
    await renderFlashArticle(game, info, drawNo);
    return;
  }
  flashOffset = 0;
  const page = await api.articles(game, 20, 0);
  flashTotal = page.total;
  flashOffset = page.items.length;
  root.innerHTML = shell(
    `
    <div class="box">
      <h1>${info.label} 速報</h1>
      <div class="article-list" id="flash-list">${page.items.map((item) => flashListRow(game, item)).join("")}</div>
      ${
        flashOffset < flashTotal
          ? `<div class="inner"><button type="button" class="btn more" id="more-flash">さらに表示（${flashOffset}/${flashTotal}）</button></div>`
          : ""
      }
    </div>
    ${relatedFor("flash", game, info.label)}
  `,
    game,
    "flash",
  );
  document.querySelector("#more-flash")?.addEventListener("click", async () => {
    const more = await api.articles(game, 20, flashOffset);
    flashOffset += more.items.length;
    document.querySelector("#flash-list")!.insertAdjacentHTML(
      "beforeend",
      more.items.map((item) => flashListRow(game, item)).join(""),
    );
    const btn = document.querySelector("#more-flash") as HTMLButtonElement | null;
    if (btn) {
      if (flashOffset >= flashTotal) btn.remove();
      else btn.textContent = `さらに表示（${flashOffset}/${flashTotal}）`;
    }
    bindLinks();
  });
  bindLinks();
}

function flashListRow(game: string, item: api.FlashListItem): string {
  const eye = eyecatchApiPath(game, item.draw_no);
  const headline = flashNewsHeadline(gameLabel(game), item.draw_no, item.draw_date);
  return `<a class="article-tease" href="/${game}/flash/${item.draw_no}" data-link>
    <img class="article-tease-eye" src="${eye}" alt="" width="240" height="126" loading="lazy" />
    <span class="article-tease-body">
      <span class="article-tease-meta">${formatDate(item.draw_date)}</span>
      <strong>${esc(headline)}</strong>
      <p class="article-tease-hint">抽選結果・当せん金額は記事で</p>
    </span>
  </a>`;
}

async function renderFlashArticle(game: string, info: GameInfo, drawNo: number) {
  const article = await api.article(game, drawNo);
  const item = article.item;
  const prizes = (item.prizes || []).filter((p) => p.grade <= info.prize_grades);
  const notes = article.observations.map((line) => `<li>${esc(line)}</li>`).join("");
  const prev = article.prev_draw_no
    ? `<a class="btn btn-ghost" href="/${game}/flash/${article.prev_draw_no}" data-link>前の回</a>`
    : `<span>前の回</span>`;
  const next = article.next_draw_no
    ? `<a class="btn btn-ghost" href="/${game}/flash/${article.next_draw_no}" data-link>次の回</a>`
    : `<span>次の回</span>`;
  const headline = flashNewsHeadline(info.label, drawNo, article.draw_date);
  const eyeApi = eyecatchApiPath(game, drawNo);
  const eyeStatic = eyecatchPath(game, drawNo);
  const eyeForMeta = import.meta.env.DEV ? eyeApi : eyeStatic;
  const desc = `${headline}。本数字と当せん金額を掲載。`;
  setSeo(`/${game}/flash/${drawNo}`, {
    drawDate: article.draw_date,
    ogType: "article",
    image: eyeForMeta,
    publishedTime: `${String(article.draw_date).slice(0, 10)}T12:00:00+09:00`,
  });
  setJsonLd(
    flashNewsJsonLd({
      label: info.label,
      drawNo,
      drawDate: article.draw_date,
      numbers: item.numbers,
      url: absoluteUrl(`/${game}/flash/${drawNo}`),
      image: eyeForMeta,
      description: desc,
    }),
  );
  root.innerHTML = shell(
    `
    <article class="post">
      <p class="flash-kicker">速報</p>
      <figure class="post-eyecatch">
        <img src="${eyeApi}" alt="${esc(headline)}" width="1200" height="630" />
      </figure>
      <h1 class="post-title">${esc(headline)}</h1>
      <p class="flash-date">${formatDate(article.draw_date)}</p>
      <p class="post-lead">${esc(article.lead)}</p>
      <div class="flash-balls">${ballsHtml(item)}</div>
      ${
        prizes.some((p) => p.amount != null || p.count != null)
          ? `<dl class="flash-prizes">${prizes
              .map(
                (p) => `<div>
              <dt>${p.grade}等</dt>
              <dd><strong>${p.amount == null ? "—" : formatYen(p.amount)}</strong>${p.count == null ? "" : `<span>${formatCount(p.count)}</span>`}</dd>
            </div>`,
              )
              .join("")}</dl>`
          : ""
      }
      ${article.carry_text ? `<p class="post-carry">${esc(article.carry_text)}</p>` : ""}
      <ul class="flash-meta">
        ${item.sales_amount == null ? "" : `<li>販売実績 ${formatYen(item.sales_amount)}</li>`}
        <li>キャリーオーバー ${formatYen(item.carryover_amount)}</li>
      </ul>
      ${notes ? `<h3 class="post-h">この回の特徴</h3><ul class="post-notes">${notes}</ul>` : ""}
      <p class="flash-actions">
        ${prev}
        ${next}
        <a class="btn btn-primary" href="/${game}/flash" data-link>速報一覧</a>
        <a class="btn btn-ghost" href="/${game}/latest" data-link>最新結果</a>
        <a class="btn btn-ghost" href="/${game}/history" data-link>結果一覧</a>
        <a class="btn btn-ghost" href="/${game}" data-link>${info.label}</a>
      </p>
    </article>
  `,
    game,
    "flash",
  );
  bindLinks();
}

function historyQueryFromUrl(): api.HistoryQuery {
  const qs = new URLSearchParams(location.search);
  const period = qs.get("period") || "all";
  const sort = qs.get("sort") === "oldest" ? "oldest" : "newest";
  const from = qs.get("from") || undefined;
  const to = qs.get("to") || undefined;
  return { period, sort, from, to };
}

function historyUrl(game: string, q: api.HistoryQuery): string {
  const params = new URLSearchParams();
  if (q.period && q.period !== "all") params.set("period", q.period);
  if (q.sort && q.sort !== "newest") params.set("sort", q.sort);
  if (q.from) params.set("from", q.from);
  if (q.to) params.set("to", q.to);
  const s = params.toString();
  return s ? `/${game}/history?${s}` : `/${game}/history`;
}

async function renderHistory(game: string, info: GameInfo) {
  const grades = info.prize_grades;
  const q = historyQueryFromUrl();
  const periodKeys: [string, string][] = [
    ["all", "全期間"],
    ["years1", "過去1年"],
    ["years3", "過去3年"],
    ["years5", "過去5年"],
    ["years10", "過去10年"],
    ["draws100", "直近100回"],
    ["draws500", "直近500回"],
  ];

  const loadPage = async (offset: number) =>
    api.history(game, { ...q, limit: 40, offset });

  historyOffset = 0;
  const page = await loadPage(0);
  historyTotal = page.total;
  historyOffset = page.items.length;

  const periodBarHtml = `<div class="period-bar" id="hist-period">
    ${periodKeys
      .map(([id, label]) => {
        const active = !q.from && !q.to && (q.period || "all") === id ? "active" : "";
        return `<a href="${historyUrl(game, { ...q, period: id, from: undefined, to: undefined })}" class="${active}" data-link>${label}</a>`;
      })
      .join("")}
  </div>`;

  root.innerHTML = shell(
    `
    <div class="box">
      <h1>${info.label} 当選番号一覧</h1>
      ${howto("抽せん日や期間で絞り込み、新しい順・古い順に並べ替えられます。回号から速報へ進めます。")}
      <div class="inner hist-filters">
        ${periodBarHtml}
        <div class="toolbar hist-toolbar">
          <label class="field">開始日
            <input id="hist-from" type="date" value="${esc(q.from || "")}" />
          </label>
          <label class="field">終了日
            <input id="hist-to" type="date" value="${esc(q.to || "")}" />
          </label>
          <label class="field">並び
            <select id="hist-sort">
              <option value="newest"${q.sort !== "oldest" ? " selected" : ""}>新しい順</option>
              <option value="oldest"${q.sort === "oldest" ? " selected" : ""}>古い順</option>
            </select>
          </label>
          <button type="button" class="btn btn-primary" id="hist-apply">絞り込む</button>
        </div>
        <p class="muted hist-count" id="hist-count">${historyTotal.toLocaleString("ja-JP")}件</p>
      </div>
      <div class="inner pad0">
        <div class="table-wrap">
          <table class="data" id="hist-table">
            <thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字／ボーナス</th>${prizeHeaders(grades)}<th class="num">キャリー</th></tr></thead>
            <tbody id="hist-body">${
              page.items.length
                ? page.items
                    .map((item) => drawRow(item, [], `${prizeCells(item, grades)}${carryCell(item)}`, game))
                    .join("")
                : `<tr><td colspan="${3 + grades + 1}">該当する回がありません。</td></tr>`
            }</tbody>
          </table>
        </div>
        <div class="inner" id="hist-more-wrap">
        ${
          historyOffset < historyTotal
            ? `<button type="button" class="btn more" id="more">さらに表示（${historyOffset}/${historyTotal}）</button>`
            : ""
        }
        </div>
      </div>
    </div>
    ${relatedFor("history", game, info.label)}
  `,
    game,
    "history",
  );

  const applyFilters = () => {
    const from = (document.querySelector("#hist-from") as HTMLInputElement).value || undefined;
    const to = (document.querySelector("#hist-to") as HTMLInputElement).value || undefined;
    const sort = (document.querySelector("#hist-sort") as HTMLSelectElement).value as "newest" | "oldest";
    const next: api.HistoryQuery = {
      period: from || to ? "all" : q.period || "all",
      sort,
      from,
      to,
    };
    history.replaceState({}, "", historyUrl(game, next));
    void renderHistory(game, info);
  };

  document.querySelector("#hist-apply")?.addEventListener("click", applyFilters);
  document.querySelector("#hist-sort")?.addEventListener("change", applyFilters);

  document.querySelector("#more")?.addEventListener("click", async () => {
    const more = await loadPage(historyOffset);
    historyOffset += more.items.length;
    document.querySelector("#hist-body")!.insertAdjacentHTML(
      "beforeend",
      more.items.map((item) => drawRow(item, [], `${prizeCells(item, grades)}${carryCell(item)}`, game)).join(""),
    );
    const btn = document.querySelector("#more") as HTMLButtonElement | null;
    if (btn) {
      if (historyOffset >= historyTotal) btn.remove();
      else btn.textContent = `さらに表示（${historyOffset}/${historyTotal}）`;
    }
  });
  bindLinks();
}

async function renderSearch(game: string, info: GameInfo) {
  selected = [];
  let favorites = loadFavorites(game).filter((n) => n >= info.min_number && n <= info.max_number);
  root.innerHTML = shell(
    `
    <div class="box">
      <h1>${info.label} 数字検索</h1>
      ${howto(`最大${info.main_count}個（${info.min_number}〜${info.max_number}）。選んだ数字が出た回を探せます。登録数字はこの端末に保存します。`)}
      <div class="inner">
        <div class="fav-panel">
          <div class="fav-head">
            <span>登録数字</span>
            <span class="fav-note">この端末に保存します</span>
          </div>
          <div class="fav-chips" id="fav-chips"></div>
          <div class="toolbar" style="margin:6px 0 0;border:0;padding:0">
            <button type="button" class="btn" id="fav-add">選択した数字を登録</button>
            <button type="button" class="btn" id="fav-use">登録数字で検索</button>
          </div>
        </div>
        <div class="slots" id="slots"></div>
        <div class="pad" id="pad" style="margin-top:8px"></div>
        <div class="toolbar" style="margin:8px 0 0;border:0;padding:0">
          <button type="button" class="btn btn-primary" id="do-search">検索</button>
          <button type="button" class="btn" id="clear">クリア</button>
        </div>
      </div>
    </div>
    <div id="result"></div>
    ${relatedFor("search", game, info.label)}
  `,
    game,
    "search",
  );

  const persistFav = () => {
    saveFavorites(game, favorites);
    paintFav();
    syncPad(info.main_count, favorites);
  };

  const paintFav = () => {
    const box = document.querySelector("#fav-chips")!;
    if (!favorites.length) {
      box.innerHTML = `<p class="fav-empty">登録した数字はありません</p>`;
      return;
    }
    box.innerHTML = favorites
      .map(
        (n) => `<span class="fav-item">
          <button type="button" class="fav-chip${selected.includes(n) ? " on" : ""}" data-pick="${n}">${pad2(n)}</button>
          <button type="button" class="fav-del" data-del="${n}" aria-label="${pad2(n)}の登録を解除">×</button>
        </span>`,
      )
      .join("");
    box.querySelectorAll<HTMLButtonElement>("[data-pick]").forEach((btn) => {
      btn.addEventListener("click", () => {
        toggleSelected(Number(btn.dataset.pick), info.main_count);
        paintFav();
        syncPad(info.main_count, favorites);
      });
    });
    box.querySelectorAll<HTMLButtonElement>("[data-del]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const n = Number(btn.dataset.del);
        favorites = favorites.filter((x) => x !== n);
        persistFav();
      });
    });
  };

  const pad = document.querySelector("#pad")!;
  for (let n = info.min_number; n <= info.max_number; n++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pad2(n);
    btn.dataset.n = String(n);
    btn.addEventListener("click", () => {
      toggleSelected(n, info.main_count);
      paintFav();
      syncPad(info.main_count, favorites);
    });
    pad.appendChild(btn);
  }
  document.querySelector("#fav-add")!.addEventListener("click", () => {
    if (!selected.length) {
      document.querySelector("#result")!.innerHTML = `<p class="error">登録する数字を選んでください</p>`;
      return;
    }
    favorites = [...new Set([...favorites, ...selected])].sort((a, b) => a - b);
    persistFav();
  });
  document.querySelector("#fav-use")!.addEventListener("click", () => {
    if (!favorites.length) {
      document.querySelector("#result")!.innerHTML = `<p class="error">登録した数字がありません</p>`;
      return;
    }
    selected = favorites.slice(0, info.main_count);
    paintFav();
    syncPad(info.main_count, favorites);
  });
  document.querySelector("#clear")!.addEventListener("click", () => {
    selected = [];
    paintFav();
    syncPad(info.main_count, favorites);
    document.querySelector("#result")!.innerHTML = "";
  });
  document.querySelector("#do-search")!.addEventListener("click", async () => {
    const box = document.querySelector("#result")!;
    if (!selected.length) {
      box.innerHTML = `<p class="error">数字を1個以上選んでください</p>`;
      return;
    }
    box.innerHTML = `<p class="muted">検索中…</p>`;
    try {
      const res = await api.search(game, selected);
      const chips = res.number_stats
        .map((s) => `<span class="chip"><strong>${pad2(s.number)}</strong> ${s.count}回</span>`)
        .join("");
      box.innerHTML = `
        <div class="chips" style="margin-bottom:8px">${chips}</div>
        <div class="box">
          <h2>該当 ${res.total} 回</h2>
          <div class="inner pad0">
            <div class="table-wrap">
              <table class="data">
                <thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字／ボーナス</th>${prizeHeaders(info.prize_grades)}<th class="num">一致</th></tr></thead>
                <tbody>${res.items.map((item) => drawRow(item, selected, `${prizeCells(item, info.prize_grades)}<td class="num">${item.match_count ?? 0}</td>`)).join("")}</tbody>
              </table>
            </div>
          </div>
        </div>`;
    } catch (err) {
      box.innerHTML = `<p class="error">${(err as Error).message}</p>`;
    }
  });
  paintFav();
  syncPad(info.main_count, favorites);
  bindLinks();
}

function queryNumbers(): number[] {
  return [...new URLSearchParams(location.search).getAll("n")]
    .map(Number)
    .filter((n) => Number.isInteger(n) && n > 0);
}

function comboQs(numbers: number[]): string {
  return numbers.map((n) => `n=${n}`).join("&");
}

function unitPriceOf(info: GameInfo): number {
  if (info.unit_price != null && info.unit_price > 0) return info.unit_price;
  return info.id === "loto7" ? 300 : 200;
}

/** 全角数字などを半角数字だけにする（口数入力用） */
function toHalfWidthDigits(raw: string): string {
  return raw
    .replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/[^\d]/g, "");
}

async function renderSimu(seq: number) {
  try {
    games = (await api.listGames()).games;
  } catch {
    /* 既存の games を使う */
  }
  if (seq !== renderSeq) return;
  const params = new URLSearchParams(location.search);
  let gameId = params.get("game") || "loto6";
  if (!games.find((g) => g.id === gameId)) gameId = games[0]?.id || "loto6";
  const info = games.find((g) => g.id === gameId)!;
  const unit = unitPriceOf(info);

  let hand: number[][] = [];
  let pick: number[] = [];
  let randomCount = 0;

  const fromQuery = queryNumbers().filter((n) => n >= info.min_number && n <= info.max_number);
  const uniqueQuery = [...new Set(fromQuery)].sort((a, b) => a - b);
  if (uniqueQuery.length === info.main_count) {
    hand = [uniqueQuery];
  }

  const paint = () => {
    if (seq !== renderSeq) return;
    const total = hand.length + randomCount;
    const cost = total * unit;
    const gameTabs = games
      .map(
        (g) =>
          `<button type="button" class="btn${g.id === info.id ? " btn-primary" : ""}" data-game="${g.id}">${esc(g.label)}</button>`,
      )
      .join("");
    const cartBodyHtml = () => {
      const handRows = hand
        .map((nums, i) => {
          const balls = nums.map((n) => `<span class="ball">${pad2(n)}</span>`).join("");
          return `<tr>
              <td class="num">${i + 1}</td>
              <td><span class="balls-main">${balls}</span></td>
              <td><button type="button" class="btn" data-del="${i}">削除</button></td>
            </tr>`;
        })
        .join("");
      const randomRow =
        randomCount > 0
          ? `<tr><td class="num">${hand.length ? "—" : "1"}</td><td>ランダム ${randomCount.toLocaleString("ja-JP")}口</td><td><button type="button" class="btn" id="clear-random">クリア</button></td></tr>`
          : "";
      const emptyRow =
        !hand.length && randomCount < 1
          ? `<tr><td colspan="3" class="muted">まだ口がありません。数字を足すか、ランダム口数を入れてください。</td></tr>`
          : "";
      return `${handRows}${randomRow}${emptyRow}`;
    };

    const bindCartActions = () => {
      document.querySelector("#clear-random")?.addEventListener("click", () => {
        randomCount = 0;
        const input = document.querySelector("#rnd-count") as HTMLInputElement | null;
        if (input) input.value = "0";
        refreshCart();
      });
      document.querySelectorAll<HTMLButtonElement>("[data-del]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const i = Number(btn.dataset.del);
          hand = hand.filter((_, idx) => idx !== i);
          refreshCart();
        });
      });
      const drawBtn = document.querySelector("#do-simu") as HTMLButtonElement | null;
      if (drawBtn) drawBtn.disabled = hand.length + randomCount < 1;
    };

    const refreshCart = () => {
      const totalNow = hand.length + randomCount;
      const costNow = totalNow * unit;
      const costEl = document.querySelector(".play-cost");
      if (costEl) {
        costEl.textContent = `合計 ${totalNow.toLocaleString("ja-JP")}口　／　${formatYen(costNow)}`;
      }
      const body = document.querySelector("#cart-body");
      if (body) body.innerHTML = cartBodyHtml();
      bindCartActions();
    };

    root.innerHTML = shell(
      `
      <div class="box">
        <h1>ロト購入シミュレーター</h1>
        ${howto("種目を選び、数字を足すか口数でランダムを入れて、疑似抽せんの結果を見ます。")}
        <div class="inner">
          <div class="toolbar simu-games">${gameTabs}</div>
          <p class="muted">1口 ${formatYen(unit)}</p>
          <div class="slots" id="slots"></div>
          <div class="pad" id="pad" style="margin-top:8px"></div>
          <div class="toolbar" style="margin:8px 0 0;border:0;padding:0">
            <button type="button" class="btn btn-primary" id="add-hand">この数字を1口追加</button>
            <button type="button" class="btn" id="clear-pick">選択クリア</button>
            <button type="button" class="btn" id="rnd-one">ランダム1口を追加</button>
          </div>
          <div class="toolbar" style="margin:12px 0 0;border:0;padding:0;flex-wrap:wrap;gap:8px">
            <label class="field">ランダム口数
              <input type="text" inputmode="numeric" pattern="[0-9]*" id="rnd-count" autocomplete="off" value="${randomCount}" />
            </label>
            <button type="button" class="btn" id="set-random">ランダム口数を反映</button>
          </div>
          <h2 class="simu-cart-title">購入内容</h2>
          <div class="simu-cart-total">
            <p class="play-cost">合計 ${total.toLocaleString("ja-JP")}口　／　${formatYen(cost)}</p>
            <button type="button" class="btn btn-primary" id="do-simu" ${total < 1 ? "disabled" : ""}>抽せんする</button>
          </div>
          <div class="table-wrap"><table class="data">
            <thead><tr><th class="num">#</th><th>数字</th><th></th></tr></thead>
            <tbody id="cart-body">${cartBodyHtml()}</tbody>
          </table></div>
        </div>
      </div>
      <div id="simu-stage" class="simu-stage" hidden></div>
      <div id="result"></div>
    `,
      info.id,
      "simu",
    );

    const syncPickUi = () => {
      document.querySelectorAll<HTMLButtonElement>("#pad button").forEach((btn) => {
        const n = Number(btn.dataset.n);
        btn.classList.toggle("on", pick.includes(n));
      });
      const slots = document.querySelector("#slots");
      if (!slots) return;
      const cells = [];
      for (let i = 0; i < info.main_count; i++) {
        const n = pick[i];
        cells.push(`<span class="slot${n ? " on" : ""}">${n ? pad2(n) : "·"}</span>`);
      }
      slots.innerHTML = cells.join("");
    };

    const pad = document.querySelector("#pad")!;
    for (let n = info.min_number; n <= info.max_number; n++) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = pad2(n);
      btn.dataset.n = String(n);
      btn.addEventListener("click", () => {
        if (pick.includes(n)) pick = pick.filter((x) => x !== n);
        else if (pick.length < info.main_count) pick = [...pick, n].sort((a, b) => a - b);
        syncPickUi();
      });
      pad.appendChild(btn);
    }
    syncPickUi();

    document.querySelectorAll<HTMLButtonElement>("[data-game]").forEach((btn) => {
      btn.addEventListener("click", () => {
        history.pushState({}, "", `/simu?game=${btn.dataset.game}`);
        void render();
      });
    });
    document.querySelector("#add-hand")!.addEventListener("click", () => {
      const box = document.querySelector("#result")!;
      if (pick.length !== info.main_count) {
        box.innerHTML = `<p class="error">本数字を${info.main_count}個選んでください</p>`;
        return;
      }
      if (hand.length >= 500) {
        box.innerHTML = `<p class="error">手選びは500口までです</p>`;
        return;
      }
      hand = [...hand, [...pick]];
      pick = [];
      paint();
    });
    document.querySelector("#clear-pick")!.addEventListener("click", () => {
      pick = [];
      syncPickUi();
    });
    document.querySelector("#rnd-one")!.addEventListener("click", () => {
      const box = document.querySelector("#result")!;
      if (hand.length >= 500) {
        box.innerHTML = `<p class="error">手選びは500口までです</p>`;
        return;
      }
      const pool: number[] = [];
      for (let n = info.min_number; n <= info.max_number; n++) pool.push(n);
      const nums: number[] = [];
      while (nums.length < info.main_count) {
        const i = Math.floor(Math.random() * pool.length);
        nums.push(pool.splice(i, 1)[0]!);
      }
      hand = [...hand, nums.sort((a, b) => a - b)];
      paint();
    });
    const rndInput = document.querySelector("#rnd-count") as HTMLInputElement;
    const syncRandomFromInput = () => {
      const digits = toHalfWidthDigits(rndInput.value);
      if (rndInput.value !== digits) rndInput.value = digits;
      if (digits === "") {
        randomCount = 0;
      } else {
        const raw = Number(digits);
        if (Number.isFinite(raw) && Number.isInteger(raw) && raw >= 0) {
          randomCount = raw;
        }
      }
      refreshCart();
    };
    rndInput.addEventListener("input", syncRandomFromInput);
    rndInput.addEventListener("blur", syncRandomFromInput);
    document.querySelector("#set-random")!.addEventListener("click", syncRandomFromInput);
    rndInput.addEventListener("keydown", (ev) => {
      if ((ev as KeyboardEvent).key === "Enter") {
        ev.preventDefault();
        syncRandomFromInput();
      }
    });
    bindCartActions();
    document.querySelector("#do-simu")!.addEventListener("click", () => {
      void runDraw();
    });
    bindLinks();
    restorePagesNav();
  };

  const runDraw = async () => {
    const total = hand.length + randomCount;
    const box = document.querySelector("#result")!;
    const stage = document.querySelector("#simu-stage") as HTMLElement;
    if (total < 1) {
      box.innerHTML = `<p class="error">1口以上入れてください</p>`;
      return;
    }
    box.innerHTML = "";
    stage.hidden = false;
    stage.innerHTML = `<div class="box simu-draw-box"><h2>抽せん結果</h2><div class="inner simu-draw-body"><p class="simu-spin-label">抽せん中…</p><div class="flash-balls simu-draw-balls simu-spin" id="spin-balls"></div></div></div>`;
    const spinEl = document.querySelector("#spin-balls")!;
    let frames = 0;
    const tick = () => {
      const pool: number[] = [];
      for (let n = info.min_number; n <= info.max_number; n++) pool.push(n);
      const shown: number[] = [];
      while (shown.length < info.main_count) {
        const i = Math.floor(Math.random() * pool.length);
        shown.push(pool.splice(i, 1)[0]!);
      }
      spinEl.innerHTML = `<span class="balls-main">${shown
        .sort((a, b) => a - b)
        .map((n) => `<span class="ball simu-ball-pulse">${pad2(n)}</span>`)
        .join("")}</span>`;
      frames += 1;
      if (frames < 8) window.setTimeout(tick, 90);
    };
    tick();

    try {
      let carryover: number | null = null;
      try {
        const latest = await api.latest(info.id);
        const raw = latest.item.carryover_amount;
        carryover = raw == null ? null : Number(raw);
      } catch {
        carryover = null;
      }
      const gameDef: SimuGameDef = {
        id: info.id,
        label: info.label,
        min_number: info.min_number,
        max_number: info.max_number,
        main_count: info.main_count,
        bonus_count: info.bonus_count,
        unit_price: unitPriceOf(info),
        simu_grade1_base: info.simu_grade1_base ?? 0,
        simu_prizes: info.simu_prizes ?? {},
      };
      const res = await runSimu({
        game: gameDef,
        tickets: hand,
        randomCount,
        carryoverAmount: carryover,
      });
      await new Promise((r) => window.setTimeout(r, 720));
      if (seq !== renderSeq) return;
      const drawBalls = res.draw.numbers.map((n) => `<span class="ball">${pad2(n)}</span>`).join("");
      const bonusBalls = res.draw.bonuses.map((n) => `<span class="ball bonus">${pad2(n)}</span>`).join("");
      stage.innerHTML = `<div class="box simu-draw-box">
        <h2>抽せん結果</h2>
        <div class="inner simu-draw-body">
          <div class="flash-balls simu-draw-balls">
            <span class="balls-main">${drawBalls}</span>
            <span class="balls-bonus">${bonusBalls}</span>
          </div>
          <p class="muted simu-draw-meta">キャリーオーバー反映 ${formatYen(res.carryover_amount)}</p>
          <p class="muted simu-draw-meta">1等プール ${formatYen(res.grade1_pool)}</p>
        </div>
      </div>`;
      const gradeChips = res.by_grade
        .map(
          (g) =>
            `<span class="chip">${g.grade}等 ${g.count.toLocaleString("ja-JP")}口　各${formatYen(g.amount_each)}</span>`,
        )
        .join("");
      const detailNote = res.winners_only
        ? `<p class="muted">${res.detail_threshold}口を超えたため、当たり口だけ表示しています。</p>`
        : "";
      const detailRows = res.details
        .map((d) => {
          const balls = d.numbers.map((n) => `<span class="ball">${pad2(n)}</span>`).join("");
          return `<tr>
            <td class="num">${d.index}</td>
            <td>${d.source === "hand" ? "手選び" : "ランダム"}</td>
            <td><span class="balls-main">${balls}</span></td>
            <td>${d.grade == null ? "—" : `${d.grade}等`}</td>
            <td class="num">${d.amount ? formatYen(d.amount) : "—"}</td>
          </tr>`;
        })
        .join("");
      box.innerHTML = `<div class="box">
        <h2>収支</h2>
        <div class="play-total">
          <p class="dx-verdict">${formatYen(res.prize_total)}</p>
          <p class="dx-summary">払戻合計</p>
          <p class="play-cost">購入 ${res.ticket_count.toLocaleString("ja-JP")}口　${formatYen(res.cost)}　／　差引 ${formatYen(res.net)}</p>
        </div>
        ${gradeChips ? `<div class="chips">${gradeChips}</div>` : `<p class="muted inner">当たりなし</p>`}
      </div>
      <div class="box">
        <h2>明細</h2>
        ${detailNote}
        <div class="inner pad0"><div class="table-wrap"><table class="data">
          <thead><tr><th class="num">#</th><th>種別</th><th>数字</th><th>等級</th><th class="num">金額</th></tr></thead>
          <tbody>${detailRows || `<tr><td colspan="5" class="muted">表示する口はありません</td></tr>`}</tbody>
        </table></div></div>
      </div>`;
    } catch (err) {
      stage.hidden = true;
      stage.innerHTML = "";
      const msg = err instanceof SimuError ? err.message : (err as Error).message;
      box.innerHTML = `<p class="error">${esc(msg)}</p>`;
    }
  };

  paint();
}

async function renderCombo(game: string, info: GameInfo) {
  const period = queryPeriod();
  const fromQuery = queryNumbers().filter((n) => n >= info.min_number && n <= info.max_number);
  selected = [...new Set(fromQuery)].sort((a, b) => a - b).slice(0, info.main_count);
  let favorites = loadFavorites(game).filter((n) => n >= info.min_number && n <= info.max_number);
  const meta = await api.gameMeta(game);
  const drawCount = meta.draw_count;
  root.innerHTML = shell(
    `
    <div class="box">
      <h1>${info.label} 予想診断</h1>
      ${howto("1口の形と、過去にどれくらい出たかを見ます。")}
      ${periodBar(game, "combo", period, drawCount, undefined, comboQs(selected))}
      <div class="inner">
        <div class="fav-panel">
          <div class="fav-head">
            <span>登録数字</span>
            <span class="fav-note">この端末に保存します</span>
          </div>
          <div class="fav-chips" id="fav-chips"></div>
          <div class="toolbar" style="margin:6px 0 0;border:0;padding:0">
            <button type="button" class="btn" id="fav-add">選択した数字を登録</button>
            <button type="button" class="btn" id="fav-use">登録数字を選択</button>
          </div>
        </div>
        <div class="slots" id="slots"></div>
        <div class="pad" id="pad" style="margin-top:8px"></div>
        <div class="toolbar" style="margin:8px 0 0;border:0;padding:0">
          <button type="button" class="btn btn-primary" id="do-combo">診断する</button>
          <button type="button" class="btn" id="clear">クリア</button>
        </div>
      </div>
    </div>
    <div id="result"></div>
    ${relatedFor("combo", game, info.label)}
  `,
    game,
    "combo",
  );

  const persistFav = () => {
    saveFavorites(game, favorites);
    paintFav();
    syncPad(info.main_count, favorites);
  };

  const paintFav = () => {
    const box = document.querySelector("#fav-chips")!;
    if (!favorites.length) {
      box.innerHTML = `<p class="fav-empty">登録した数字はありません</p>`;
      return;
    }
    box.innerHTML = favorites
      .map(
        (n) => `<span class="fav-item">
          <button type="button" class="fav-chip${selected.includes(n) ? " on" : ""}" data-pick="${n}">${pad2(n)}</button>
          <button type="button" class="fav-del" data-del="${n}" aria-label="${pad2(n)}の登録を解除">×</button>
        </span>`,
      )
      .join("");
    box.querySelectorAll<HTMLButtonElement>("[data-pick]").forEach((btn) => {
      btn.addEventListener("click", () => {
        toggleSelected(Number(btn.dataset.pick), info.main_count);
        paintFav();
        syncPad(info.main_count, favorites);
      });
    });
    box.querySelectorAll<HTMLButtonElement>("[data-del]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const n = Number(btn.dataset.del);
        favorites = favorites.filter((x) => x !== n);
        persistFav();
      });
    });
  };

  const pad = document.querySelector("#pad")!;
  for (let n = info.min_number; n <= info.max_number; n++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pad2(n);
    btn.dataset.n = String(n);
    btn.addEventListener("click", () => {
      toggleSelected(n, info.main_count);
      paintFav();
      syncPad(info.main_count, favorites);
    });
    pad.appendChild(btn);
  }
  document.querySelector("#fav-add")!.addEventListener("click", () => {
    if (!selected.length) {
      document.querySelector("#result")!.innerHTML = `<p class="error">登録する数字を選んでください</p>`;
      return;
    }
    favorites = [...new Set([...favorites, ...selected])].sort((a, b) => a - b);
    persistFav();
  });
  document.querySelector("#fav-use")!.addEventListener("click", () => {
    if (!favorites.length) {
      document.querySelector("#result")!.innerHTML = `<p class="error">登録した数字がありません</p>`;
      return;
    }
    selected = favorites.slice(0, info.main_count);
    paintFav();
    syncPad(info.main_count, favorites);
  });
  document.querySelector("#clear")!.addEventListener("click", () => {
    selected = [];
    paintFav();
    syncPad(info.main_count, favorites);
    document.querySelector("#result")!.innerHTML = "";
    history.replaceState({}, "", `/${game}/combo?period=${period}`);
  });
  const paintResult = (res: api.ComboPayload) => {
    const dx = res.diagnosis;
    const matchRows = res.match_hist
      .slice()
      .reverse()
      .map((row) => `<tr><td>本数字 ${row.match_count}個</td><td class="num">${formatTimes(row.draws)}</td></tr>`)
      .join("");
    const numRows = res.numbers_stats
      .map(
        (s) =>
          `<tr><td>${pad2(s.number)}</td><td class="num">${formatTimes(s.count)}</td><td>${s.last_draw_no ? formatDraw(s.last_draw_no) : "—"}</td></tr>`,
      )
      .join("");
    const pointHtml = (dx?.points || [])
      .map(
        (p) =>
          `<div class="dx-point ${esc(p.tone)}"><strong>${esc(p.label)}</strong><p>${esc(p.text)}</p></div>`,
      )
      .join("");
    const w = res.whatif;
    const hitRows = (res.hits || [])
      .map((item) => {
        const draw = {
          numbers: item.numbers,
          bonus: item.bonus ?? 0,
          bonus2: item.bonus2,
          draw_no: item.draw_no,
          draw_date: item.draw_date,
          game: "",
        } as DrawItem;
        return `<tr>
          <td class="num">${formatDraw(item.draw_no)}</td>
          <td>${formatDate(item.draw_date)}</td>
          <td class="nums">${ballsHtml(draw, res.numbers)}</td>
          <td>${item.grade}等</td>
          <td class="num">${item.amount == null ? "—" : formatYen(item.amount)}</td>
        </tr>`;
      })
      .join("");
    const gradeChips = (w?.by_grade || [])
      .map((g) => `<span class="chip">${g.grade}等 ${g.draws}回　${formatYen(g.amount)}</span>`)
      .join("");
    const unknown = w?.unknown_amount ? `金額未確定が${w.unknown_amount}回あります。` : "";
    const whatifBox = w
      ? `<div class="box">
        <h2>この口を毎回買っていたら</h2>
        <div class="play-total">
          <p class="dx-verdict">${formatYen(w.prize_total)}</p>
          <p class="dx-summary">当せん合計　${w.hit_count}回 / ${res.draw_count.toLocaleString("ja-JP")}回</p>
          <p class="play-cost">1口${formatYen(w.unit_price)}で毎回買っていたら、購入合計は${formatYen(w.cost)}です。${unknown}</p>
        </div>
        ${gradeChips ? `<div class="chips">${gradeChips}</div>` : ""}
        ${
          hitRows
            ? `<div class="inner pad0"><div class="table-wrap"><table class="data">
              <thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字／ボーナス</th><th>等級</th><th class="num">金額</th></tr></thead>
              <tbody>${hitRows}</tbody>
            </table></div></div>`
            : `<p class="muted inner">この期間は当たりなしです。</p>`
        }
      </div>`
      : "";
    const box = document.querySelector("#result")!;
    const levelClass = dx?.level ? ` lv${dx.level}` : "";
    const simuLink = `/simu?game=${encodeURIComponent(game)}&${comboQs(res.numbers)}`;
    box.innerHTML = `
      <div class="box">
        <div class="dx${levelClass}">
          <p class="dx-verdict">${esc(dx?.verdict || "—")}</p>
          <p class="dx-summary">${esc(dx?.summary || "")}</p>
        </div>
        <div class="dx-points">${pointHtml}</div>
        <div class="inner"><p><a href="${simuLink}" data-link>購入シミュレーターで試す</a></p></div>
      </div>
      ${whatifBox}
      <div class="box">
        <h2>各数字の出現</h2>
        <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>数字</th><th class="num">本数字</th><th>最終</th></tr></thead><tbody>${numRows}</tbody></table></div></div>
      </div>
      <div class="box">
        <h2>過去との照合（${res.draw_count.toLocaleString("ja-JP")}回）</h2>
        ${howto(`まったく同じ並びは${res.exact_count}回。下の表は、いくつかぶったかごとの回数です。`)}
        <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>一致</th><th class="num">開催</th></tr></thead><tbody>${matchRows}</tbody></table></div></div>
      </div>`;
  };

  const run = async () => {
    const box = document.querySelector("#result")!;
    if (selected.length !== info.main_count) {
      box.innerHTML = `<p class="error">本数字を${info.main_count}個選んでください</p>`;
      return;
    }
    history.replaceState({}, "", `/${game}/combo?period=${period}&${comboQs(selected)}`);
    box.innerHTML = `<p class="muted">診断中…</p>`;
    try {
      const res = await api.combo(game, selected, period);
      paintResult(res);
      bindLinks();
    } catch (err) {
      box.innerHTML = `<p class="error">${(err as Error).message}</p>`;
    }
  };

  document.querySelector("#do-combo")!.addEventListener("click", () => {
    void run();
  });
  paintFav();
  syncPad(info.main_count, favorites);
  bindLinks();
  if (selected.length === info.main_count) void run();
}

function toggleSelected(n: number, mainCount: number) {
  if (selected.includes(n)) selected = selected.filter((x) => x !== n);
  else if (selected.length < mainCount) selected = [...selected, n].sort((a, b) => a - b);
}

function syncPad(mainCount: number, favorites: number[] = []) {
  const fav = new Set(favorites);
  document.querySelectorAll<HTMLButtonElement>("#pad button").forEach((btn) => {
    const n = Number(btn.dataset.n);
    btn.classList.toggle("on", selected.includes(n));
    btn.classList.toggle("fav", fav.has(n));
  });
  const slots = document.querySelector("#slots");
  if (!slots) return;
  const cells = [];
  for (let i = 0; i < mainCount; i++) {
    const n = selected[i];
    cells.push(`<span class="slot${n ? " on" : ""}">${n ? pad2(n) : "·"}</span>`);
  }
  slots.innerHTML = cells.join("");
}

function rankDrawLine(item: PrizeRankItem): string {
  const draw = {
    numbers: item.numbers,
    bonus: item.bonus,
    bonus2: item.bonus2,
  } as DrawItem;
  return `<div class="rank-draw">
    <div class="rank-meta">${formatDraw(item.draw_no)}　${formatDate(item.draw_date)}　${formatCount(item.count)}</div>
    <div class="nums">${ballsHtml(draw)}</div>
  </div>`;
}

function rankRows(groups: PrizeRankGroup[]): string {
  if (!groups.length) return `<p class="muted">該当なし</p>`;
  return groups
    .map(
      (group) => `<details class="rank-item">
        <summary class="rank-top">
          <span class="rank-n">${group.rank}</span>
          <strong>${formatYen(group.amount)}</strong>
          <span class="rank-count">同額${group.draw_count.toLocaleString("ja-JP")}回</span>
        </summary>
        <div class="rank-body">${group.draws.map(rankDrawLine).join("")}</div>
      </details>`,
    )
    .join("");
}

function rankTable(title: string, groups: PrizeRankGroup[]): string {
  return `<div class="box">
    <h2>${title}</h2>
    <div class="inner pad0">${rankRows(groups)}</div>
  </div>`;
}

function queryPeriod(): string {
  return new URLSearchParams(location.search).get("period") || "all";
}

function queryRows(): number {
  const raw = Number(new URLSearchParams(location.search).get("rows") || 50);
  return raw === 20 || raw === 100 ? raw : 50;
}

function periodKeys(drawCount: number): [string, string][] {
  const keys: [string, string][] = [["all", "全期間"]];
  if (drawCount >= 50) keys.push(["draws50", "直近50回"]);
  if (drawCount >= 100) keys.push(["draws100", "直近100回"]);
  if (drawCount >= 500) keys.push(["draws500", "直近500回"]);
  keys.push(["years5", "過去5年"], ["years10", "過去10年"]);
  return keys;
}

function ranksPeriodKeys(): [string, string][] {
  return [
    ["all", "全期間"],
    ["years1", "過去1年"],
    ["years3", "過去3年"],
    ["years5", "過去5年"],
    ["years10", "過去10年"],
  ];
}

function periodBar(game: string, view: string, current: string, drawCount: number, number?: number, extraQs = ""): string {
  const keys = view === "ranks" ? ranksPeriodKeys() : periodKeys(drawCount);
  return `<div class="period-bar">${keys
    .map(([id, label]) => {
      const base = view === "number" && number != null ? `/${game}/n/${pad2(number)}` : viewPath(game, view);
      const extra = extraQs ? `&${extraQs.replace(/^&/, "")}` : "";
      const href = id === "all" && view === "ranks" ? base : `${base}?period=${id}${extra}`;
      return `<a href="${href}" class="${id === current ? "active" : ""}" data-link>${label}</a>`;
    })
    .join("")}</div>`;
}

function periodDrawTotal(meta: TrendsPayload["meta"] | undefined, fallback = 0): number {
  return Number(meta?.game_draw_count || meta?.draw_count || fallback);
}

function rangeLine(meta: TrendsPayload["meta"] | undefined): string {
  if (!meta?.start_draw || !meta.end_draw) return "";
  return `<p class="muted rank-asof">${formatDraw(meta.start_draw)}（${formatDate(String(meta.start_date))}）〜${formatDraw(meta.end_draw)}（${formatDate(String(meta.end_date))}）　${meta.draw_count}回</p>`;
}

function numLink(game: string, n: number): string {
  return `<a href="/${game}/n/${pad2(n)}" data-link>${pad2(n)}</a>`;
}

function sinceLabel(since: number | null | undefined): string {
  if (since == null) return "—";
  if (since === 0) return "今回";
  return `${since}回前`;
}

function round1(n: number): string {
  return n.toFixed(1);
}

function roundInt(n: number): string {
  return Math.round(n).toLocaleString("ja-JP");
}

async function renderFreq(game: string, info: GameInfo) {
  const period = queryPeriod();
  const data = await api.trends(game, period);
  const rows = data.frequency || [];
  const drawCount = periodDrawTotal(data.meta, info.max_number);
  let sort: "hot" | "cold" | "bonus" | "rest" | "num" = "hot";

  const paint = () => {
    const valued = rows.map((row) => ({
      row,
      main: row.count,
      bonus: row.bonus_count || 0,
      since: row.draws_since_last,
      last: row.last_draw_date,
    }));
    const sorted = [...valued].sort((a, b) => {
      if (sort === "cold") return a.main - b.main || a.row.number - b.row.number;
      if (sort === "bonus") return b.bonus - a.bonus || a.row.number - b.row.number;
      if (sort === "rest") return (b.since || 0) - (a.since || 0) || a.row.number - b.row.number;
      if (sort === "num") return a.row.number - b.row.number;
      return b.main - a.main || a.row.number - b.row.number;
    });
    const freqBox = data.error
      ? `<p class="error">${data.error}</p>`
      : `<div class="box">
      <h1>${info.label} よく出る数字・出現回数</h1>
      ${howto("数字ごとの出現回数です。本数字とボーナスを並べて見られます。")}
      <div class="filter-row">
        <span class="filter-label">期間</span>
        ${periodBar(game, "freq", period, drawCount)}
      </div>
      ${rangeLine(data.meta)}
      <div class="filter-row" role="group" aria-label="並び">
        <span class="filter-label">並び</span>
        <div class="period-bar">
          <button type="button" class="chip-btn${sort === "hot" ? " on" : ""}" data-sort="hot">本数字が多い順</button>
          <button type="button" class="chip-btn${sort === "cold" ? " on" : ""}" data-sort="cold">本数字が少ない順</button>
          <button type="button" class="chip-btn${sort === "bonus" ? " on" : ""}" data-sort="bonus">ボーナスが多い順</button>
          <button type="button" class="chip-btn${sort === "rest" ? " on" : ""}" data-sort="rest">空きが長い順</button>
          <button type="button" class="chip-btn${sort === "num" ? " on" : ""}" data-sort="num">数字順</button>
        </div>
      </div>
      <div class="inner pad0">
        <div class="table-wrap">
          <table class="data freq-table">
            <thead><tr>
              <th class="num">順位</th>
              <th class="num">数字</th>
              <th class="num">本数字</th>
              <th class="num">ボーナス</th>
              <th>最後の本数字</th>
              <th class="num">今の空き</th>
            </tr></thead>
            <tbody>
              ${sorted
                .map(
                  (s, i) => `<tr>
                    <td class="num">${formatRank(i + 1)}</td>
                    <td class="num">${numLink(game, s.row.number)}</td>
                    <td class="num">${formatTimes(s.main)}</td>
                    <td class="num">${formatTimes(s.bonus)}</td>
                    <td>${formatDate(s.last)}</td>
                    <td class="num">${sinceLabel(s.since)}</td>
                  </tr>`,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
    root.innerHTML = shell(`${freqBox}${relatedFor("freq", game, info.label)}`, game, "freq");
    root.querySelectorAll<HTMLButtonElement>("[data-sort]").forEach((btn) => {
      btn.addEventListener("click", () => {
        sort = btn.dataset.sort as typeof sort;
        paint();
      });
    });
    bindLinks();
  };
  paint();
}

function pairTable(game: string, title: string, rows: PairRow[], size: number): string {
  if (!rows.length) return "";
  return `<div class="box"><h2>${title}</h2><div class="inner pad0"><div class="table-wrap"><table class="data pair-table">
    <thead><tr><th>数字</th><th class="num">回数</th><th class="num">割合</th><th>最新出現日</th><th>他数字</th></tr></thead>
    <tbody>${rows
      .map((row) => {
        const nums = [row.number_a, row.number_b, row.number_c].filter((n): n is number => n != null).slice(0, size);
        const others = row.others?.length ? row.others.map((n) => numLink(game, n)).join(" ") : "—";
        return `<tr><td>${nums.map((n) => numLink(game, n)).join(" ")}</td><td class="num">${formatTimes(row.count)}</td><td class="num">${(row.probability * 100).toFixed(1)}%</td><td>${formatDate(row.last_draw_date)}</td><td class="nums">${others}</td></tr>`;
      })
      .join("")}</tbody></table></div></div></div>`;
}

async function renderPairs(game: string, info: GameInfo) {
  const period = queryPeriod();
  const data = await api.trends(game, period);
  const drawCount = periodDrawTotal(data.meta);
  const triples = (data.triples_high || data.triples || []).slice(0, 100);
  root.innerHTML = shell(
    `<div class="box"><h1>${info.label} よく出る組み合わせ</h1>
     ${howto("3個以上一緒に出やすい組を、回数の多い順に見られます。")}
     ${periodBar(game, "pairs", period, drawCount)}${rangeLine(data.meta)}</div>
     ${pairTable(game, "3個以上（上位100）", triples, 3)}
     ${relatedFor("pairs", game, info.label)}`,
    game,
    "pairs",
  );
  bindLinks();
}

function peakClass(n: number, peak: number): string {
  return n === peak && peak > 0 ? " hot" : "";
}

function shapeJump(items: [string, string][]): string {
  return `<nav class="shape-jump">${items.map(([id, label]) => `<a href="#${id}">${label}</a>`).join("")}</nav>`;
}

function shapeBox(id: string, title: string, lead: string, body: string): string {
  return `<div class="box" id="${id}"><h2>${title}</h2>${howto(lead)}${body}</div>`;
}

async function renderShape(game: string, info: GameInfo) {
  const period = queryPeriod();
  const data = await api.trends(game, period);
  const shape = data.shape;
  const drawCount = periodDrawTotal(data.meta);
  if (!shape) {
    root.innerHTML = shell(`<p class="error">${data.error || "分析できる当せんデータがありません"}</p>`, game, "shape");
    bindLinks();
    return;
  }
  const main = info.main_count;
  const maxBin = Math.max(...shape.sum_bins.map((b) => b.draws), 1);
  const sumPeakBin = shape.sum_bins.reduce((a, b) => (b.draws > a.draws ? b : a), shape.sum_bins[0]);
  const sumPeakRange = sumPeakBin ? sumPeakBin.label.replace("-", "〜") : "";
  const oddPeak = Math.max(...shape.odd_even.map((r) => r.draws), 0);
  const oddTop = shape.odd_even.length
    ? shape.odd_even.reduce((a, b) => (b.draws > a.draws ? b : a))
    : null;
  const oddTopLabel = oddTop ? `偶数${oddTop.even_count}個・奇数${oddTop.odd_count}個` : "";
  root.innerHTML = shell(
    `<div class="box">
      <h1>${info.label} 奇数偶数・合計</h1>
      ${howto("奇数偶数の分かれ方と、合計の出方を回数で見られます。")}
      ${shapeJump([
        ["odd-even", "奇数偶数"],
        ["sum", "合計"],
      ])}
      ${periodBar(game, "shape", period, drawCount)}${rangeLine(data.meta)}
    </div>
    ${shapeBox(
      "odd-even",
      "奇数偶数",
      `偶数と奇数の分かれ方。いちばん多いのは${oddTopLabel}。`,
      `<div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>形</th><th class="num">回数</th><th class="num">割合</th></tr></thead>
      <tbody>${shape.odd_even
        .map(
          (r) =>
            `<tr class="${peakClass(r.draws, oddPeak)}"><td>偶数${r.even_count}個・奇数${r.odd_count}個</td><td class="num">${formatTimes(r.draws)}</td><td class="num">${(r.rate * 100).toFixed(1)}%</td></tr>`,
        )
        .join("")}</tbody></table></div></div>`,
    )}
    ${shapeBox(
      "sum",
      "合計",
      `本数字${main}個の合計。いちばん多い幅は${sumPeakRange}。`,
      `<div class="inner"><p class="shape-kpi">平均 ${round1(shape.sum_summary.mean)}　中央値 ${round1(shape.sum_summary.median)}　最も多い合計 ${shape.sum_summary.mode}　最小 ${shape.sum_summary.min}　最大 ${shape.sum_summary.max}</p>
      ${shape.sum_bins
        .map(
          (b) =>
            `<div class="bar-row${peakClass(b.draws, maxBin)}"><span>${b.label}</span><span class="bar-track"><span class="bar-fill" style="width:${(b.draws / maxBin) * 100}%"></span></span><span class="num">${formatTimes(b.draws)}</span></div>`,
        )
        .join("")}</div>`,
    )}
    ${relatedFor("shape", game, info.label)}`,
    game,
    "shape",
  );
  bindLinks();
}

async function renderGrid(game: string, info: GameInfo) {
  const rowsN = queryRows();
  const page = await api.history(game, rowsN, 0);
  const items = page.items;
  let odd = false;
  let consec = false;
  let streak = false;
  const paint = () => {
    const max = info.max_number;
    const header = Array.from({ length: max }, (_, i) => `<th class="num">${pad2(i + 1)}</th>`).join("");
    const body = items
      .map((item, idx) => {
        const mains = new Set(item.numbers);
        const bonus = new Set([item.bonus, item.bonus2].filter((n): n is number => n != null));
        const consecSet = new Set<number>();
        const sorted = [...item.numbers].sort((a, b) => a - b);
        for (let i = 0; i < sorted.length - 1; i++) {
          if (sorted[i + 1] - sorted[i] === 1) {
            consecSet.add(sorted[i]);
            consecSet.add(sorted[i + 1]);
          }
        }
        const prev = items[idx + 1];
        const prevSet = new Set(prev?.numbers || []);
        const cells = Array.from({ length: max }, (_, i) => {
          const n = i + 1;
          const isMain = mains.has(n);
          const isBonus = bonus.has(n);
          const classes = [
            isMain ? "hit" : "",
            isBonus ? "bonus-hit" : "",
            odd && n % 2 === 1 && (isMain || isBonus) ? "odd-on" : "",
            consec && consecSet.has(n) ? "seq-on" : "",
            streak && isMain && prevSet.has(n) ? "streak-on" : "",
          ]
            .filter(Boolean)
            .join(" ");
          const label = isMain || isBonus ? pad2(n) : "";
          return `<td class="${classes}">${label}</td>`;
        }).join("");
        return `<tr><td class="num meta"><a href="/${game}/flash/${item.draw_no}" data-link>${formatDraw(item.draw_no)}</a></td><td class="meta">${formatDate(item.draw_date)}</td>${cells}</tr>`;
      })
      .join("");
    root.innerHTML = shell(
      `<div class="box"><h1>${info.label} 出目表</h1>
      ${howto("縦が回、横が数字。塗ったマスが本数字、橙がボーナス。")}
      <div class="period-bar">${[20, 50, 100]
        .map((n) => `<a href="/${game}/grid?rows=${n}" class="${n === rowsN ? "active" : ""}" data-link>${n}回</a>`)
        .join("")}</div>
      <div class="period-bar">
        <button type="button" class="chip-btn${odd ? " on" : ""}" data-hl="odd">奇数</button>
        <button type="button" class="chip-btn${consec ? " on" : ""}" data-hl="consec">連番</button>
        <button type="button" class="chip-btn${streak ? " on" : ""}" data-hl="streak">連続出現</button>
      </div>
      <div class="table-wrap"><table class="data grid-table"><thead><tr><th>回</th><th>日</th>${header}</tr></thead><tbody>${body}</tbody></table></div></div>
      ${relatedFor("grid", game, info.label)}`,
      game,
      "grid",
    );
    root.querySelectorAll<HTMLButtonElement>("[data-hl]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.hl;
        if (key === "odd") odd = !odd;
        if (key === "consec") consec = !consec;
        if (key === "streak") streak = !streak;
        paint();
      });
    });
    bindLinks();
  };
  paint();
}

async function renderFollow(game: string, info: GameInfo) {
  const period = queryPeriod();
  const data = await api.trends(game, period);
  const follow = data.follow;
  const drawCount = periodDrawTotal(data.meta);
  if (!follow?.summary?.length) {
    root.innerHTML = shell(`<p class="error">${data.error || "分析できる当せんデータがありません"}</p>`, game, "follow");
    bindLinks();
    return;
  }
  const summaryLabel: Record<string, string> = {
    none: "前回の数字を含まない",
    any: "前回の数字を含む",
    streak2: "2連続",
    streak3: "3連続",
  };
  const hl = follow.highlights;
  const hlLine = (label: string, rows: { number: number; value: number }[], fmt: (v: number) => string) =>
    `<tr><td>${label}</td><td>${rows.map((r) => `${numLink(game, r.number)}（${fmt(r.value)}）`).join("　")}</td></tr>`;
  root.innerHTML = shell(
    `<div class="box"><h1>${info.label} 前回の当選番号を含む回数</h1>
    ${howto("前回と同じ数字がまた出た回数と、続けて出た数字。")}
    ${periodBar(game, "follow", period, drawCount)}${rangeLine(data.meta)}</div>
    <div class="box"><h2>前回の数字を含む回数</h2>
    ${howto("前回と同じ数字が入っていた回と、入っていなかった回。続けて出た回数も並んでいます。")}
    <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>項目</th><th class="num">回数</th><th class="num">割合</th></tr></thead>
    <tbody>${follow.summary
      .map(
        (r) =>
          `<tr><td>${summaryLabel[r.key] || r.key}</td><td class="num">${formatTimes(r.draws)}</td><td class="num">${(r.rate * 100).toFixed(1)}%</td></tr>`,
      )
      .join("")}</tbody></table></div></div></div>
    <div class="box"><h2>数字ごと</h2>
    ${howto("その数字が出たとき、前回にも出ていたか。")}
    <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr>
      <th>数字</th><th class="num">前回に出ない</th><th class="num">前回にも出る</th><th class="num">前回にも出る率</th><th class="num">2連続</th><th class="num">3連続</th>
    </tr></thead>
    <tbody>${follow.by_number
      .map(
        (r) =>
          `<tr><td>${numLink(game, r.number)}</td><td class="num">${formatTimes(r.without_prev)}</td><td class="num">${formatTimes(r.with_prev)}</td><td class="num">${(r.with_prev_rate * 100).toFixed(1)}%</td><td class="num">${formatTimes(r.streak2)}</td><td class="num">${formatTimes(r.streak3)}</td></tr>`,
      )
      .join("")}</tbody></table></div></div></div>
    <div class="box"><h2>多い・少ない</h2>
    <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>項目</th><th>数字</th></tr></thead>
    <tbody>
      ${hlLine("前回にも出る回数が多い", hl.with_prev_high, (v) => `${v}回`)}
      ${hlLine("2連続が多い", hl.streak2_high, (v) => `${v}回`)}
      ${hlLine("前回にも出る率が高い", hl.rate_high, (v) => `${(v * 100).toFixed(1)}%`)}
      ${hlLine("前回にも出る率が低い", hl.rate_low, (v) => `${(v * 100).toFixed(1)}%`)}
    </tbody></table></div></div></div>
    ${relatedFor("follow", game, info.label)}`,
    game,
    "follow",
  );
  bindLinks();
}

async function renderNumber(game: string, info: GameInfo, n?: number) {
  if (n == null || n < info.min_number || n > info.max_number) {
    renderNotFound("指定した数字のページはありません。");
    return;
  }
  const period = queryPeriod();
  let data;
  try {
    data = await api.numberDetail(game, n, period);
  } catch (err) {
    root.innerHTML = shell(`<p class="error">${(err as Error).message}</p>`, game, "number");
    bindLinks();
    return;
  }
  const f = data.frequency;
  const drawCount = periodDrawTotal(data.meta);
  root.innerHTML = shell(
    `<div class="box">
      <h1>${info.label} ${pad2(n)} の出現回数</h1>
      ${howto("出現回数と、同じ回で一緒に出た数字。")}
      ${periodBar(game, "number", period, drawCount, n)}
      ${rangeLine(data.meta)}
      <ul class="flash-meta">
        <li>本数字 ${formatTimes(f.count)}</li>
        <li>ボーナス ${formatTimes(f.bonus_count ?? 0)}</li>
        <li>最後の本数字 ${formatDate(f.last_draw_date)}</li>
        <li>今の空き ${sinceLabel(f.draws_since_last)}</li>
      </ul>
    </div>
    <div class="box"><h2>一緒に出た数字</h2><div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>数字</th><th class="num">回数</th></tr></thead>
    <tbody>${data.mates.map((m) => `<tr><td>${numLink(game, m.number)}</td><td class="num">${formatTimes(m.count)}</td></tr>`).join("")}</tbody></table></div></div></div>
    <div class="box"><h2>出た開催</h2><div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字／ボーナス</th></tr></thead>
    <tbody>${data.items.map((item) => drawRow(item, [n])).join("")}</tbody></table></div></div></div>`,
    game,
    "number",
  );
  bindLinks();
}

async function renderRanks(game: string, _info: GameInfo) {
  const period = queryPeriod();
  const allowed = new Set(ranksPeriodKeys().map(([id]) => id));
  const key = allowed.has(period) ? period : "all";
  if (key !== period) {
    history.replaceState({}, "", key === "all" ? `/${game}/ranks` : `/${game}/ranks?period=${key}`);
  }
  const data = await api.trends(game, key);
  const ranks = data.prize_ranks || {};
  const latest = data.latest;
  const periodLabel = ranksPeriodKeys().find(([id]) => id === key)?.[1] || "全期間";
  const asOf = latest
    ? `<p class="muted rank-asof">${formatDraw(latest.draw_no)}（${formatDate(latest.draw_date)}）時点　対象 ${periodLabel}${data.meta?.draw_count != null ? `（${data.meta.draw_count}回）` : ""}</p>`
    : "";
  const rankBoxes = [1, 2, 3]
    .map((grade) => {
      const set = ranks[String(grade)] || { high: [], low: [] };
      return `${rankTable(`${grade}等 最高額（上位5）`, set.high)}${rankTable(`${grade}等 最低額（下位5）`, set.low)}`;
    })
    .join("");
  root.innerHTML = shell(
    `
    <div class="box">
      <h1>${_info.label} 当せん金額ランキング</h1>
      ${howto("1等から3等まで、金額の高い回と低い回。同額はまとめています。")}
      ${periodBar(game, "ranks", key, 0)}
      ${rangeLine(data.meta)}
      ${asOf}
    </div>
    ${rankBoxes}
    ${relatedFor("ranks", game, _info.label)}
  `,
    game,
    "ranks",
  );
  bindLinks();
}

function generateBodyFromForm(tickets: number): Parameters<typeof api.generate>[1] {
  const mode = (document.querySelector("#mode") as HTMLSelectElement | null)?.value as "hot" | "balanced" | undefined;
  const period = (document.querySelector("#period") as HTMLSelectElement | null)?.value || "all";
  const body: Parameters<typeof api.generate>[1] = { tickets, mode: mode || "hot" };
  if (period === "years5") body.recent_years = 5;
  if (period === "years10") body.recent_years = 10;
  if (period === "draws100") body.recent_draws = 100;
  if (period === "draws300") body.recent_draws = 300;
  return body;
}

function comboRowsHtml(combos: { index: number; numbers: number[] }[]): string {
  return combos
    .map(
      (c) => `
    <div class="combo-row">
      <span class="idx">${c.index}</span>
      <span class="balls">${c.numbers.map((n) => `<span class="ball">${pad2(n)}</span>`).join("")}</span>
    </div>`,
    )
    .join("");
}

async function renderGenerate(game: string, info: GameInfo) {
  let pick: api.WeekPick | null = null;
  try {
    pick = await api.weekPick(game);
  } catch {
    pick = null;
  }
  const nextNo = pick?.next_draw_no;
  const prevHtml = pick
    ? `<div class="box">
        <h2>前回の予想</h2>
        <div class="inner">
          <p class="muted">${formatDraw(pick.latest.draw_no)}（${formatDate(pick.latest.draw_date)}）　本数字 ${pick.match_count}個一致</p>
          <div class="flash-balls">${numberBalls(pick.previous, pick.matched)}</div>
        </div>
      </div>`
    : "";
  root.innerHTML = shell(
    `
    <div class="flash week-pick">
      <p class="flash-kicker">次回予想</p>
      <h1 class="flash-title">${info.label} 予想</h1>
      ${
        nextNo != null && pick
          ? `<p class="flash-date">${formatDraw(nextNo)}</p>
             <p class="muted">抽せん日 ${formatDate(pick.next_draw_date)}</p>`
          : nextNo != null
            ? `<p class="flash-date">${formatDraw(nextNo)}</p>`
            : ""
      }
      <div id="week-hero">${
        pick
          ? `<div class="flash-balls">${numberBalls(pick.next)}</div>
             <p class="flash-actions"><button type="button" class="btn" id="copy-week">コピー</button></p>`
          : `<p class="muted">読み込み中…</p>`
      }</div>
    </div>
    ${prevHtml}
    <div class="box">
      <h2>口数で作成</h2>
      <div class="inner">
        <div class="toolbar" style="margin:0;border:0;padding:0">
          <label class="field">口数
            <input id="tickets" type="number" min="1" max="20" value="1" />
          </label>
          <label class="field">優先
            <select id="mode">
              <option value="hot">出現の多い数字</option>
              <option value="balanced">均等</option>
            </select>
          </label>
          <label class="field">集計期間
            <select id="period">
              <option value="all">全期間</option>
              <option value="years5">直近5年</option>
              <option value="years10">直近10年</option>
              <option value="draws100">直近100回</option>
              <option value="draws300">直近300回</option>
            </select>
          </label>
          <button type="button" class="btn btn-primary" id="do-gen">作成</button>
        </div>
      </div>
    </div>
    <div id="gen-out"></div>
    <div class="box">
      <h2>予想の根拠</h2>
      <div class="inner basis">
        <p>よく出た数字ほど選ばれやすい作り方です。抽せんは回ごとに独立しており、当せんを保証するものではありません。</p>
        <h3>次回予想（1口）</h3>
        <p>全期間の出現回数から、その回の1口を出します。結果が載ると前回の予想へ移し、いくつ当たったかを見せます。</p>
        <h3>口数で作成</h3>
        <p>口数を指定して、その場で組み合わせを作ります。「出現の多い数字」か「均等」を選べます。期間も選べます。口どうしで同じ並びはできるだけ避けます。</p>
      </div>
    </div>
    ${relatedFor("generate", game, info.label)}
  `,
    game,
    "generate",
  );

  const bindWeekCopy = (numbers: number[]) => {
    const copyText = numbers.map(pad2).join(" ");
    document.querySelector("#copy-week")?.addEventListener("click", async () => {
      await navigator.clipboard.writeText(copyText);
      (document.querySelector("#copy-week") as HTMLButtonElement).textContent = "コピー済";
    });
  };
  if (pick) bindWeekCopy(pick.next);
  else {
    void (async () => {
      const hero = document.querySelector("#week-hero")!;
      try {
        const body = generateBodyFromForm(1);
        const res = await api.generate(game, body);
        const combo = res.combos[0];
        hero.innerHTML = `
          <div class="flash-balls">${numberBalls(combo.numbers)}</div>
          <p class="flash-actions"><button type="button" class="btn" id="copy-week">コピー</button></p>
        `;
        bindWeekCopy(combo.numbers);
      } catch (err) {
        hero.innerHTML = `<p class="error">${(err as Error).message}</p>`;
      }
    })();
  }

  document.querySelector("#do-gen")!.addEventListener("click", async () => {
    const tickets = Number((document.querySelector("#tickets") as HTMLInputElement).value || 1);
    const body = generateBodyFromForm(tickets);
    const out = document.querySelector("#gen-out")!;
    out.innerHTML = `<p class="muted">作成しています…</p>`;
    try {
      const res = await api.generate(game, body);
      const copyText = res.combos.map((c) => c.numbers.map(pad2).join(" ")).join("\n");
      out.innerHTML = `
        <div class="box">
          <h2>組み合わせ ${res.combos.length} 口（対象 ${res.draw_count} 回 / ${res.mode === "hot" ? "出現の多い数字" : "均等"}）</h2>
          <div class="inner pad0">
            ${comboRowsHtml(res.combos)}
            <div class="inner">
              <button type="button" class="btn" id="copy">コピー</button>
            </div>
          </div>
        </div>
        <div class="chips">${res.weights_summary.map((w) => `<span class="chip"><strong>${pad2(w.number)}</strong> ${w.count}回</span>`).join("")}</div>
        ${res.warnings?.length ? `<p class="error">${res.warnings.join(" ")}</p>` : ""}
      `;
      document.querySelector("#copy")?.addEventListener("click", async () => {
        await navigator.clipboard.writeText(copyText);
        (document.querySelector("#copy") as HTMLButtonElement).textContent = "コピー済";
      });
    } catch (err) {
      out.innerHTML = `<p class="error">${(err as Error).message}</p>`;
    }
  });
  bindLinks();
}

function bindLinks() {
  restorePagesNav();
  document.querySelectorAll<HTMLAnchorElement>("a[data-link]").forEach((a) => {
    a.addEventListener("click", (ev) => {
      if (ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
      ev.preventDefault();
      navigate(a.getAttribute("href") || "/");
    });
  });
  void hydrateAffiliate();
  if (!scrollToTopOnPaint) return;
  scrollToTopOnPaint = false;
  scrollPageTop();
  requestAnimationFrame(() => {
    scrollPageTop();
    requestAnimationFrame(scrollPageTop);
  });
}

window.addEventListener("popstate", () => {
  scrollToTopOnPaint = true;
  void render();
});
void render().catch((err) => {
  root.innerHTML = `<p class="error">${err.message}</p><p class="muted">${gameLabel("loto6")}</p>`;
});
