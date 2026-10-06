import "./styles.css";
import * as api from "./api";
import type { DrawItem, GameInfo, PairRow, PrizeRankGroup, PrizeRankItem, TrendsPayload } from "./api";
import { gameLabel, setSeo } from "./seo";
import { isLegalPage, legalHtml } from "./legal";
import { loadFavorites, saveFavorites } from "./favorites";

const root = document.querySelector("#app")!;
let games: GameInfo[] = [];
let selected: number[] = [];
let historyOffset = 0;
let historyTotal = 0;
let flashOffset = 0;
let flashTotal = 0;

type Route = { game?: string; view: string; drawNo?: number; number?: number };

function parseRoute(): Route {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { view: "home" };
  if (isLegalPage(parts[0])) return { view: parts[0] };
  if (parts[1] === "flash") {
    const raw = parts[2] ? Number(parts[2]) : undefined;
    return { game: parts[0], view: "flash", drawNo: raw && Number.isFinite(raw) ? raw : undefined };
  }
  if (parts[1] === "n") {
    const raw = parts[2] ? Number(parts[2]) : NaN;
    return { game: parts[0], view: "number", number: Number.isFinite(raw) ? raw : undefined };
  }
  let view = parts[1] || "hub";
  if (view === "trends") view = "freq";
  return { game: parts[0], view };
}

const GAME_PAGES: [string, string][] = [
  ["latest", "最新結果"],
  ["generate", "次回予想"],
  ["history", "結果一覧"],
  ["freq", "出現回数"],
  ["pairs", "同時出現"],
  ["shape", "奇数偶数"],
  ["grid", "出目表"],
  ["follow", "前回重なり"],
  ["ranks", "金額ランキング"],
  ["search", "数字検索"],
  ["combo", "組合診断"],
  ["flash", "速報"],
];

function viewPath(game: string, view: string, drawNo?: number): string {
  if (view === "home") return "/";
  if (view === "hub") return `/${game}`;
  if (view === "flash") return drawNo ? `/${game}/flash/${drawNo}` : `/${game}/flash`;
  if (view === "number" && drawNo) return `/${game}/n/${pad2(drawNo)}`;
  return `/${game}/${view}`;
}

function navigate(path: string) {
  history.pushState({}, "", path);
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
  if (n == null) return "—";
  return `${n.toLocaleString("ja-JP")}円`;
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

function numberBalls(numbers: number[], highlight: number[] = []): string {
  const hi = new Set(highlight);
  return `<span class="balls">${numbers
    .map((n) => `<span class="ball${hi.has(n) ? " match" : ""}">${pad2(n)}</span>`)
    .join("")}</span>`;
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
  return `<span class="balls">${mains}<span class="bonus-group"><span class="bonus-lab">ボーナス</span>${bonus}</span></span>`;
}

function drawRow(item: DrawItem, highlight: number[] = [], extra = ""): string {
  return `<tr>
    <td class="num">${formatDraw(item.draw_no)}</td>
    <td>${formatDate(item.draw_date)}</td>
    <td class="nums">${ballsHtml(item, highlight)}</td>
    ${extra}
  </tr>`;
}

function pageLinks(game: string, activeView?: string): string {
  return GAME_PAGES.map(([id, label]) => {
    const on = activeView === id;
    return `<a href="${viewPath(game, id)}" class="${on ? "active" : ""}"${on ? ' aria-current="page"' : ""} data-link>${label}</a>`;
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

function shell(inner: string, activeGame?: string, activeView?: string): string {
  rememberPagesNav();
  const switchView = activeView && activeView !== "home" ? activeView : "hub";
  const gameLinks = games
    .map((g) => {
      const href = activeGame
        ? viewPath(g.id, switchView === "number" ? "hub" : switchView === "flash" ? "flash" : switchView)
        : `/${g.id}`;
      const on = activeGame === g.id;
      return `<a href="${href}" class="${on ? "active" : ""}"${on ? ' aria-current="page"' : ""} data-link>${g.label}</a>`;
    })
    .join("");
  const pages = activeGame ? pageLinks(activeGame, activeView) : "";
  const pagesNav = activeGame ? `<nav class="nav-pages" aria-label="ページ">${pages}</nav>` : "";
  return `
    <header class="site-head">
      <div class="topbar">
        <a class="brand" href="/" data-link>LOTO<span>データベース</span></a>
        <nav class="nav-games" aria-label="ロト">${gameLinks}</nav>
      </div>
      ${pagesNav}
    </header>
    <main class="body">${inner}</main>
    <footer class="footer">
      <nav class="footer-nav">
        <a href="/about" data-link>このサイトについて</a>
        <a href="/disclaimer" data-link>免責事項</a>
        <a href="/privacy" data-link>プライバシーポリシー</a>
        <a href="/terms" data-link>利用規約</a>
        <a href="/contact" data-link>お問い合わせ</a>
      </nav>
      <p class="copy">© 2026 LOTOデータベース</p>
    </footer>
  `;
}

async function render() {
  const route = parseRoute();
  setSeo(location.pathname);
  if (!games.length) games = (await api.listGames()).games;

  if (route.view === "home" && !route.game) {
    try {
      await renderSiteHome();
    } catch (err) {
      root.innerHTML = shell(`<p class="error">${(err as Error).message}</p>`);
      bindLinks();
    }
    return;
  }

  if (isLegalPage(route.view)) {
    root.innerHTML = shell(legalHtml(route.view), undefined, route.view);
    bindLinks();
    return;
  }

  const game = route.game;
  const info = games.find((g) => g.id === game);
  if (!game || !info) {
    root.innerHTML = shell(`<p class="error">指定したロトが見つかりません</p>`);
    bindLinks();
    return;
  }

  const allowed = [
    "hub",
    "latest",
    "flash",
    "history",
    "search",
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
  ];
  let view = allowed.includes(route.view) ? route.view : "hub";
  if (view === "trends") {
    view = location.hash === "#amount" ? "ranks" : "freq";
    history.replaceState({}, "", `/${game}/${view}`);
  }
  try {
    if (view === "hub") await renderHub(game, info);
    else if (view === "latest") await renderLatest(game, info);
    else if (view === "flash") await renderFlash(game, info, route.drawNo);
    else if (view === "history") await renderHistory(game, info);
    else if (view === "search") await renderSearch(game, info);
    else if (view === "combo") await renderCombo(game, info);
    else if (view === "freq") await renderFreq(game, info);
    else if (view === "pairs") await renderPairs(game, info);
    else if (view === "shape") await renderShape(game, info);
    else if (view === "grid") await renderGrid(game, info);
    else if (view === "follow") await renderFollow(game, info);
    else if (view === "number") await renderNumber(game, info, route.number);
    else if (view === "ranks") await renderRanks(game, info);
    else await renderGenerate(game, info);
  } catch (err) {
    root.innerHTML = shell(`<p class="error">${(err as Error).message}</p>`, game, view);
    bindLinks();
  }
}

async function renderSiteHome() {
  const picks = await Promise.all(
    games.map(async (g) => {
      try {
        return await api.weekPick(g.id);
      } catch {
        return null;
      }
    }),
  );
  const carryBlocks = picks
    .filter((p): p is NonNullable<typeof p> => p != null && (p.latest.carryover_amount || 0) > 0)
    .map((p) => carryBanner(p.label, p.latest.carryover_amount as number))
    .join("");
  const blocks = games
    .map((g, i) => {
      const pick = picks[i];
      if (!pick) {
        return `<div class="box"><h2>${g.label}</h2><div class="inner"><p class="muted">データがありません</p></div></div>`;
      }
      const latest = pick.latest;
      const carry = latest.carryover_amount || 0;
      return `<div class="box">
        <h2><a href="/${g.id}" data-link>${g.label}</a></h2>
        ${carry > 0 ? carryBanner(g.label, carry) : ""}
        <section class="home-sec">
          <h3>最新結果</h3>
          <p class="muted">${formatDraw(latest.draw_no)}（${formatDate(latest.draw_date)}）</p>
          <div class="flash-balls">${ballsHtml(latest)}</div>
          <p class="flash-actions"><a class="btn btn-ghost" href="/${g.id}/latest" data-link>最新結果を見る</a></p>
        </section>
        <section class="home-sec home-sec-next">
          <h3>次回予想</h3>
          <p class="muted">${formatDraw(pick.next_draw_no)}</p>
          <div class="flash-balls">${numberBalls(pick.next)}</div>
          <p class="flash-actions"><a class="btn btn-primary" href="/${g.id}/generate" data-link>次回予想を見る</a></p>
        </section>
        <section class="home-sec home-sec-prev">
          <h3>前回の予想</h3>
          <p class="muted">${formatDraw(latest.draw_no)}　本数字 ${pick.match_count}個一致</p>
          <div class="flash-balls">${numberBalls(pick.previous, pick.matched)}</div>
        </section>
      </div>`;
    })
    .join("");
  root.innerHTML = shell(
    `
    <div class="box">
      <h1>LOTOデータベース</h1>
    </div>
    ${carryBlocks}
    ${blocks}
  `,
    undefined,
    "home",
  );
  bindLinks();
}

async function renderHub(game: string, info: GameInfo) {
  const pages = [
    ["latest", "最新結果", "直近の当せん番号と金額"],
    ["generate", "次回予想", "次回の1口と、口数での作成"],
    ["history", "結果一覧", "過去の当せん番号と金額"],
    ["freq", "出現回数", "数字ごとの出現回数"],
    ["pairs", "同時出現", "同じ開催で同時に出た組"],
    ["shape", "奇数偶数", "奇偶、合計、連番などの内訳"],
    ["grid", "出目表", "直近開催の出目"],
    ["follow", "前回重なり", "直前の回と重なった本数字"],
    ["ranks", "金額ランキング", "1等から3等の最高額と最低額"],
    ["search", "数字検索", "指定した数字が出た開催"],
    ["combo", "組合診断", "1口の形と出現の所見"],
    ["flash", "速報", "開催ごとの当せん番号"],
  ];
  root.innerHTML = shell(
    `
    <div class="box">
      <h1>${info.label}</h1>
      <div class="home-list">
        ${pages
          .map(
            ([id, title, desc]) => `<a href="${viewPath(game, id)}" data-link>
              <span class="g">${title}</span>
              <span class="d">${desc}</span>
            </a>`,
          )
          .join("")}
      </div>
    </div>
  `,
    game,
    "hub",
  );
  bindLinks();
}

async function renderLatest(game: string, info: GameInfo) {
  const { item } = await api.latest(game);
  const prizes = (item.prizes || []).filter((p) => p.grade <= info.prize_grades);
  root.innerHTML = shell(
    `
    <div class="flash">
      <p class="flash-kicker">最新結果</p>
      <h2 class="flash-title">${formatDraw(item.draw_no)}</h2>
      <p class="flash-date">${formatDate(item.draw_date)}</p>
      <div class="flash-balls">${ballsHtml(item)}</div>
      ${
        prizes.some((p) => p.amount != null || p.count != null)
          ? `<dl class="flash-prizes">${prizes
              .map(
                (p) => `<div>
              <dt>${p.grade}等</dt>
              <dd><strong>${formatYen(p.amount)}</strong><span>${formatCount(p.count)}</span></dd>
            </div>`,
              )
              .join("")}</dl>`
          : ""
      }
      ${
        item.sales_amount != null || item.carryover_amount != null
          ? `<ul class="flash-meta">
        ${item.sales_amount != null ? `<li>販売実績 ${formatYen(item.sales_amount)}</li>` : ""}
        ${item.carryover_amount != null ? `<li>キャリーオーバー ${formatYen(item.carryover_amount)}</li>` : ""}
      </ul>`
          : ""
      }
      <p class="flash-actions">
        <a class="btn btn-primary" href="/${game}/flash/${item.draw_no}" data-link>この回の速報</a>
        <a class="btn btn-ghost" href="/${game}/flash" data-link>速報一覧</a>
        <a class="btn btn-ghost" href="/${game}" data-link>${info.label}</a>
      </p>
    </div>
  `,
    game,
    "latest",
  );
  bindLinks();
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
      <h2>速報</h2>
      <div class="article-list" id="flash-list">${page.items.map((item) => flashListRow(game, item)).join("")}</div>
      ${
        flashOffset < flashTotal
          ? `<div class="inner"><button type="button" class="btn more" id="more-flash">さらに表示（${flashOffset}/${flashTotal}）</button></div>`
          : ""
      }
    </div>
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
  const stub: api.DrawItem = {
    game,
    draw_no: item.draw_no,
    draw_date: item.draw_date,
    numbers: item.numbers,
    bonus: item.bonus,
    bonus2: item.bonus2,
  };
  return `<a class="article-tease" href="/${game}/flash/${item.draw_no}" data-link>
    <span class="article-tease-meta">${formatDraw(item.draw_no)}　${formatDate(item.draw_date)}</span>
    <strong>${esc(item.title)}</strong>
    <p>${esc(item.lead)}</p>
    <div class="flash-balls tease-balls">${ballsHtml(stub)}</div>
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
  root.innerHTML = shell(
    `
    <article class="post">
      <p class="flash-kicker">速報</p>
      <h2 class="post-title">${esc(article.title)}</h2>
      <p class="flash-date">${formatDate(article.draw_date)}</p>
      <p class="post-lead">${esc(article.lead)}</p>
      <div class="flash-balls">${ballsHtml(item)}</div>
      ${
        prizes.some((p) => p.amount != null || p.count != null)
          ? `<dl class="flash-prizes">${prizes
              .map(
                (p) => `<div>
              <dt>${p.grade}等</dt>
              <dd><strong>${formatYen(p.amount)}</strong><span>${formatCount(p.count)}</span></dd>
            </div>`,
              )
              .join("")}</dl>`
          : ""
      }
      ${article.carry_text ? `<p class="post-carry">${esc(article.carry_text)}</p>` : ""}
      ${
        item.sales_amount != null || item.carryover_amount != null
          ? `<ul class="flash-meta">
        ${item.sales_amount != null ? `<li>販売実績 ${formatYen(item.sales_amount)}</li>` : ""}
        ${item.carryover_amount != null ? `<li>キャリーオーバー ${formatYen(item.carryover_amount)}</li>` : ""}
      </ul>`
          : ""
      }
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

async function renderHistory(game: string, info: GameInfo) {
  historyOffset = 0;
  const page = await api.history(game, 40, 0);
  historyTotal = page.total;
  historyOffset = page.items.length;
  const grades = info.prize_grades;
  root.innerHTML = shell(
    `
    <div class="box">
      <h2>当せん結果（新しい順）</h2>
      ${howto("新しい開催から順に、本数字と当せん金額を表示します。続きは「さらに表示」です。")}
      <div class="inner pad0">
        <div class="table-wrap">
          <table class="data" id="hist-table">
            <thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字／ボーナス</th>${prizeHeaders(grades)}</tr></thead>
            <tbody id="hist-body">${page.items.map((item) => drawRow(item, [], prizeCells(item, grades))).join("")}</tbody>
          </table>
        </div>
        ${
          historyOffset < historyTotal
            ? `<div class="inner"><button type="button" class="btn more" id="more">さらに表示（${historyOffset}/${historyTotal}）</button></div>`
            : ""
        }
      </div>
    </div>
  `,
    game,
    "history",
  );
  document.querySelector("#more")?.addEventListener("click", async () => {
    const more = await api.history(game, 40, historyOffset);
    historyOffset += more.items.length;
    document.querySelector("#hist-body")!.insertAdjacentHTML(
      "beforeend",
      more.items.map((item) => drawRow(item, [], prizeCells(item, grades))).join(""),
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
      <h2>数字検索（最大${info.main_count}個、${info.min_number}〜${info.max_number}）</h2>
      ${howto("選んだ数字が本数字に含まれた開催を探します。一致は、選んだ数字のうち当たった個数です。登録数字はこの端末に保存します。")}
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
      <h1>${info.label} 組合診断</h1>
      ${howto("本数字1口の形と出現を、過去の開催と照らします。")}
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
      .map((row) => `<tr><td>本数字 ${row.match_count}個</td><td class="num">${row.draws}</td></tr>`)
      .join("");
    const numRows = res.numbers_stats
      .map(
        (s) =>
          `<tr><td>${pad2(s.number)}</td><td class="num">${s.count}</td><td class="num">${Math.round(s.expected)}</td><td class="num">${s.vs_expected > 0 ? "+" : ""}${s.vs_expected}</td><td>${s.last_draw_no ? formatDraw(s.last_draw_no) : "—"}</td></tr>`,
      )
      .join("");
    const sampleRows = res.samples
      .map(
        (item) =>
          `<tr><td class="num">${formatDraw(item.draw_no)}</td><td>${formatDate(item.draw_date)}</td><td class="nums">${numberBalls(item.numbers, res.numbers)}</td><td class="num">${item.match_count}</td></tr>`,
      )
      .join("");
    const pointHtml = (dx?.points || [])
      .map(
        (p) =>
          `<div class="dx-point ${esc(p.tone)}"><strong>${esc(p.label)}</strong><p>${esc(p.text)}</p></div>`,
      )
      .join("");
    const box = document.querySelector("#result")!;
    box.innerHTML = `
      <div class="box">
        <div class="dx">
          <p class="dx-verdict">${esc(dx?.verdict || "—")}</p>
          <p class="dx-summary">${esc(dx?.summary || "")}</p>
        </div>
        <div class="dx-points">${pointHtml}</div>
      </div>
      <div class="box">
        <h2>各数字の出現</h2>
        <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>数字</th><th class="num">本数字</th><th class="num">期待回数</th><th class="num">対期待</th><th>最終</th></tr></thead><tbody>${numRows}</tbody></table></div></div>
      </div>
      <div class="box">
        <h2>過去との照合（${res.draw_count.toLocaleString("ja-JP")}回）</h2>
        ${howto(`完全一致は${res.exact_count}回です。表は、この口と本数字が重なった個数ごとの開催回数です。`)}
        <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>一致</th><th class="num">開催</th></tr></thead><tbody>${matchRows}</tbody></table></div></div>
      </div>
      ${
        sampleRows
          ? `<div class="box">
        <h2>本数字が3個以上重なった開催</h2>
        <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字</th><th class="num">一致</th></tr></thead><tbody>${sampleRows}</tbody></table></div></div>
      </div>`
          : ""
      }`;
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
  keys.push(["years5", "直近5年"], ["years10", "直近10年"]);
  return keys;
}

function periodBar(game: string, view: string, current: string, drawCount: number, number?: number, extraQs = ""): string {
  return `<div class="period-bar">${periodKeys(drawCount)
    .map(([id, label]) => {
      const base = view === "number" && number != null ? `/${game}/n/${pad2(number)}` : viewPath(game, view);
      const extra = extraQs ? `&${extraQs.replace(/^&/, "")}` : "";
      const href = `${base}?period=${id}${extra}`;
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
  let mode: "main" | "bonus" | "both" = "main";
  let sort: "hot" | "cold" | "rest" | "num" = "hot";

  const paint = () => {
    const valued = rows.map((row) => {
      const count = mode === "main" ? row.count : mode === "bonus" ? row.bonus_count || 0 : row.main_plus_bonus || 0;
      const expected = mode === "bonus" ? row.expected_bonus || 0 : row.expected_main || 0;
      const since = mode === "bonus" ? row.bonus_draws_since_last : row.draws_since_last;
      const last = mode === "bonus" ? row.bonus_last_draw_date : row.last_draw_date;
      const rest = mode === "bonus" ? row.bonus_max_rest : row.max_rest;
      const streak = mode === "bonus" ? row.bonus_max_streak : row.max_streak;
      return { row, count, expected, since, last, rest, streak };
    });
    const sorted = [...valued].sort((a, b) => {
      if (sort === "cold") return a.count - b.count || a.row.number - b.row.number;
      if (sort === "rest") return (b.since || 0) - (a.since || 0) || a.row.number - b.row.number;
      if (sort === "num") return a.row.number - b.row.number;
      return b.count - a.count || a.row.number - b.row.number;
    });
    const freqBox = data.error
      ? `<p class="error">${data.error}</p>`
      : `<div class="box">
      <h1>${info.label} よく出る数字・出現回数</h1>
      ${howto("数字ごとの出現回数です。期間と本数字／ボーナスで集計を切り替えます。期待回数は均等に出たと仮定した回数、経過は最後に出てからの開催数です。")}
      ${periodBar(game, "freq", period, drawCount)}
      ${rangeLine(data.meta)}
      <div class="period-bar">
        <button type="button" class="chip-btn${mode === "main" ? " on" : ""}" data-mode="main">本数字</button>
        <button type="button" class="chip-btn${mode === "bonus" ? " on" : ""}" data-mode="bonus">ボーナス</button>
        <button type="button" class="chip-btn${mode === "both" ? " on" : ""}" data-mode="both">本＋ボーナス</button>
        <button type="button" class="chip-btn${sort === "hot" ? " on" : ""}" data-sort="hot">多い順</button>
        <button type="button" class="chip-btn${sort === "cold" ? " on" : ""}" data-sort="cold">少ない順</button>
        <button type="button" class="chip-btn${sort === "rest" ? " on" : ""}" data-sort="rest">未出現が長い順</button>
        <button type="button" class="chip-btn${sort === "num" ? " on" : ""}" data-sort="num">数字順</button>
      </div>
      <div class="inner pad0">
        <div class="table-wrap">
          <table class="data">
            <thead><tr><th class="num">順位</th><th class="num">数字</th><th class="num">本数字</th><th class="num">割合</th><th class="num">期待回数</th><th class="num">対期待</th><th class="num">ボーナス</th><th class="num">本＋ボーナス</th><th>最終</th><th class="num">経過</th><th class="num">最長空白</th><th class="num">最長連続</th></tr></thead>
            <tbody>
              ${sorted
                .map((s, i) => {
                  const expected = mode === "bonus" ? s.row.expected_bonus || 0 : s.row.expected_main || 0;
                  const countForProb = mode === "main" ? s.row.count : s.count;
                  const prob = data.meta?.draw_count ? countForProb / Number(data.meta.draw_count) : 0;
                  return `<tr>
                    <td class="num">${i + 1}</td>
                    <td class="num">${numLink(game, s.row.number)}</td>
                    <td class="num">${s.row.count}</td>
                    <td class="num">${(prob * 100).toFixed(1)}%</td>
                    <td class="num">${roundInt(expected)}</td>
                    <td class="num">${Math.round(s.count - expected)}</td>
                    <td class="num">${s.row.bonus_count ?? 0}</td>
                    <td class="num">${s.row.main_plus_bonus ?? 0}</td>
                    <td>${formatDate(s.last)}</td>
                    <td class="num">${sinceLabel(s.since)}</td>
                    <td class="num">${s.rest ?? "—"}</td>
                    <td class="num">${s.streak ?? "—"}</td>
                  </tr>`;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
    root.innerHTML = shell(`${freqBox}`, game, "freq");
    root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        mode = btn.dataset.mode as typeof mode;
        paint();
      });
    });
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
  return `<div class="box"><h2>${title}</h2><div class="inner pad0"><div class="table-wrap"><table class="data">
    <thead><tr><th>数字</th><th class="num">回数</th><th class="num">割合</th><th class="num">期待回数</th></tr></thead>
    <tbody>${rows
      .map((row) => {
        const nums = [row.number_a, row.number_b, row.number_c].filter((n): n is number => n != null).slice(0, size);
        return `<tr><td>${nums.map((n) => numLink(game, n)).join(" ")}</td><td class="num">${row.count}</td><td class="num">${(row.probability * 100).toFixed(1)}%</td><td class="num">${roundInt(row.expected || 0)}</td></tr>`;
      })
      .join("")}</tbody></table></div></div></div>`;
}

async function renderPairs(game: string, info: GameInfo) {
  const period = queryPeriod();
  const data = await api.trends(game, period);
  const drawCount = periodDrawTotal(data.meta);
  root.innerHTML = shell(
    `<div class="box"><h1>${info.label} よく出る組み合わせ</h1>
     ${howto("同じ開催の本数字に同時に現れた組み合わせです。上位は出現が多い組、下位は少ない組です。")}
     ${periodBar(game, "pairs", period, drawCount)}${rangeLine(data.meta)}</div>
     ${pairTable(game, "2個 上位", data.pairs_high || data.pairs || [], 2)}
     ${pairTable(game, "2個 下位", data.pairs_low || [], 2)}
     ${pairTable(game, "3個 上位", data.triples_high || data.triples || [], 3)}
     ${pairTable(game, "3個 下位", data.triples_low || [], 3)}`,
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
  const week = ["月", "火", "水", "木", "金", "土", "日"];
  const main = info.main_count;
  const maxBin = Math.max(...shape.sum_bins.map((b) => b.draws), 1);
  const sumPeakBin = shape.sum_bins.reduce((a, b) => (b.draws > a.draws ? b : a), shape.sum_bins[0]);
  const sumPeakRange = sumPeakBin ? sumPeakBin.label.replace("-", "〜") : "";
  const oddPeak = Math.max(...shape.odd_even.map((r) => r.draws), 0);
  const pairPeak = Math.max(...shape.consecutive_pairs.map((r) => r.draws), 0);
  const runPeak = Math.max(...shape.consecutive_run.map((r) => r.draws), 0);
  const digitPeak = Math.max(...shape.last_digit.map((r) => r.count), 0);
  const spanPeak = Math.max(...shape.span.items.map((r) => r.draws), 0);
  const bands3 = shape.bands.filter((b) => b.id.startsWith("3"));
  const bands6 = shape.bands.filter((b) => b.id.startsWith("s"));
  const band3Peak = Math.max(...bands3.map((b) => b.count), 0);
  const band6Peak = Math.max(...bands6.map((b) => b.count), 0);
  const bandRange = bands3.map((b) => `${b.label}${b.min}〜${b.max}`).join("、");
  const oddTop = shape.odd_even.length
    ? shape.odd_even.reduce((a, b) => (b.draws > a.draws ? b : a))
    : null;
  const oddTopLabel = oddTop ? `偶数${oddTop.even_count}個・奇数${oddTop.odd_count}個` : "";
  root.innerHTML = shell(
    `<div class="box">
      <h1>${info.label} 奇数偶数・合計</h1>
      ${howto("本数字の内訳と並びを、開催回数で集計しています。")}
      ${shapeJump([
        ["odd-even", "奇数偶数"],
        ["sum", "合計"],
        ["seq", "連番"],
        ["digit", "一の位"],
        ["span", "最小と最大の差"],
        ["band", "数字の帯"],
        ["weekday", "抽せん曜日"],
      ])}
      ${periodBar(game, "shape", period, drawCount)}${rangeLine(data.meta)}
    </div>
    ${shapeBox(
      "odd-even",
      "奇数偶数",
      `偶数と奇数の個数パターンです。多いのは${oddTopLabel}です。`,
      `<div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>形</th><th class="num">回数</th><th class="num">割合</th></tr></thead>
      <tbody>${shape.odd_even
        .map(
          (r) =>
            `<tr class="${peakClass(r.draws, oddPeak)}"><td>偶数${r.even_count}個・奇数${r.odd_count}個</td><td class="num">${r.draws}</td><td class="num">${(r.rate * 100).toFixed(1)}%</td></tr>`,
        )
        .join("")}</tbody></table></div></div>`,
    )}
    ${shapeBox(
      "sum",
      "合計",
      `各開催の本数字${main}個を足した値です。棒の右はその幅に入った開催回数、${sumPeakRange}が最多です。`,
      `<div class="inner"><p class="shape-kpi">平均 ${round1(shape.sum_summary.mean)}　中央値 ${round1(shape.sum_summary.median)}　最も多い合計 ${shape.sum_summary.mode}　最小 ${shape.sum_summary.min}　最大 ${shape.sum_summary.max}</p>
      ${shape.sum_bins
        .map(
          (b) =>
            `<div class="bar-row${peakClass(b.draws, maxBin)}"><span>${b.label}</span><span class="bar-track"><span class="bar-fill" style="width:${(b.draws / maxBin) * 100}%"></span></span><span class="num">${b.draws}</span></div>`,
        )
        .join("")}</div>`,
    )}
    ${shapeBox(
      "seq",
      "連番",
      "隣接する数字（07・08など）の組数です。10・11・12は連番2組で、最長は3です。",
      `<div class="inner pad0">
        <h3 class="shape-sub">連番の組数</h3>
        <div class="table-wrap"><table class="data"><thead><tr><th>形</th><th class="num">回数</th><th class="num">割合</th></tr></thead>
        <tbody>${shape.consecutive_pairs
          .map((r) => {
            const label = r.adjacent_count === 0 ? "連番なし" : `連番${r.adjacent_count}組`;
            return `<tr class="${peakClass(r.draws, pairPeak)}"><td>${label}</td><td class="num">${r.draws}</td><td class="num">${(r.rate * 100).toFixed(1)}%</td></tr>`;
          })
          .join("")}</tbody></table></div>
        <h3 class="shape-sub">最長の連番</h3>
        <div class="table-wrap"><table class="data"><thead><tr><th>形</th><th class="num">回数</th><th class="num">割合</th></tr></thead>
        <tbody>${shape.consecutive_run
          .map((r) => {
            const label = r.run_length <= 1 ? "連番なし" : `最長が${r.run_length}`;
            return `<tr class="${peakClass(r.draws, runPeak)}"><td>${label}</td><td class="num">${r.draws}</td><td class="num">${(r.rate * 100).toFixed(1)}%</td></tr>`;
          })
          .join("")}</tbody></table></div>
      </div>`,
    )}
    ${shapeBox(
      "digit",
      "一の位",
      "本数字の一の位の延べ回数です。01も11も1に数えます。期待回数は、その桁を持つ数字の個数から算出しています。",
      `<div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th class="num">一の位</th><th class="num">回数</th><th class="num">期待回数</th></tr></thead>
      <tbody>${shape.last_digit
        .map(
          (r) =>
            `<tr class="${peakClass(r.count, digitPeak)}"><td class="num">${r.digit}</td><td class="num">${r.count}</td><td class="num">${roundInt(r.expected)}</td></tr>`,
        )
        .join("")}</tbody></table></div></div>`,
    )}
    ${shapeBox(
      "span",
      "最小と最大の差",
      `最大の本数字と最小の本数字の差です。01と${pad2(info.max_number)}なら${info.max_number - 1}です。`,
      `<div class="inner"><p class="shape-kpi">平均 ${round1(shape.span.summary.mean)}　最小 ${shape.span.summary.min}　最大 ${shape.span.summary.max}</p>
      <div class="table-wrap"><table class="data"><thead><tr><th class="num">差</th><th class="num">回数</th></tr></thead>
      <tbody>${shape.span.items
        .map(
          (r) =>
            `<tr class="${peakClass(r.draws, spanPeak)}"><td class="num">${r.span}</td><td class="num">${r.draws}</td></tr>`,
        )
        .join("")}</tbody></table></div></div>`,
    )}
    ${shapeBox(
      "band",
      "数字の帯",
      `番号帯ごとの本数字の個数です。${info.label}は${bandRange}です。`,
      `<div class="inner">
        <p class="shape-kpi">1回あたり　低 ${round1(shape.band_mix["低"] || 0)}個　中 ${round1(shape.band_mix["中"] || 0)}個　高 ${round1(shape.band_mix["高"] || 0)}個</p>
        <h3 class="shape-sub">低・中・高</h3>
        <div class="table-wrap"><table class="data"><thead><tr><th>帯</th><th class="num">範囲</th><th class="num">延べ個数</th></tr></thead>
        <tbody>${bands3
          .map(
            (b) =>
              `<tr class="${peakClass(b.count, band3Peak)}"><td>${b.label}</td><td class="num">${b.min}〜${b.max}</td><td class="num">${b.count}</td></tr>`,
          )
          .join("")}</tbody></table></div>
        <h3 class="shape-sub">6分割</h3>
        <div class="table-wrap"><table class="data"><thead><tr><th>範囲</th><th class="num">延べ個数</th></tr></thead>
        <tbody>${bands6
          .map(
            (b) =>
              `<tr class="${peakClass(b.count, band6Peak)}"><td>${b.min}〜${b.max}</td><td class="num">${b.count}</td></tr>`,
          )
          .join("")}</tbody></table></div>
      </div>`,
    )}
    ${shapeBox(
      "weekday",
      "抽せん曜日",
      "抽せんが行われた曜日の開催回数です。",
      `<div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>曜日</th><th class="num">回数</th></tr></thead>
      <tbody>${shape.weekday.map((r) => `<tr><td>${week[r.weekday]}曜日</td><td class="num">${r.draws}</td></tr>`).join("")}</tbody></table></div></div>`,
    )}`,
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
          return `<td class="${classes}"></td>`;
        }).join("");
        return `<tr><td class="num">${formatDraw(item.draw_no)}</td><td>${formatDate(item.draw_date)}</td>${cells}</tr>`;
      })
      .join("");
    root.innerHTML = shell(
      `<div class="box"><h1>${info.label} 出目表</h1>
      ${howto("縦が開催、横が数字です。塗ったマスが本数字、橙がボーナスです。")}
      <div class="period-bar">${[20, 50, 100]
        .map((n) => `<a href="/${game}/grid?rows=${n}" class="${n === rowsN ? "active" : ""}" data-link>${n}回</a>`)
        .join("")}</div>
      <div class="period-bar">
        <button type="button" class="chip-btn${odd ? " on" : ""}" data-hl="odd">奇数</button>
        <button type="button" class="chip-btn${consec ? " on" : ""}" data-hl="consec">連番</button>
        <button type="button" class="chip-btn${streak ? " on" : ""}" data-hl="streak">連続出現</button>
      </div>
      <div class="table-wrap"><table class="data grid-table"><thead><tr><th>回</th><th>日</th>${header}</tr></thead><tbody>${body}</tbody></table></div></div>`,
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
  if (!follow) {
    root.innerHTML = shell(`<p class="error">${data.error || "分析できる当せんデータがありません"}</p>`, game, "follow");
    bindLinks();
    return;
  }
  root.innerHTML = shell(
    `<div class="box"><h1>${info.label} 前回との重なり</h1>
    ${howto("直前の開催との重なりと、次の開催でよく出た数字です。")}
    ${periodBar(game, "follow", period, drawCount)}${rangeLine(data.meta)}</div>
    <div class="box"><h2>前回との重なり</h2>
    ${howto("直前の開催と、本数字が何個重なったかです。")}
    <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th class="num">一致</th><th class="num">回数</th><th class="num">割合</th></tr></thead>
    <tbody>${follow.overlap.map((r) => `<tr><td class="num">${r.match_count}</td><td class="num">${r.draws}</td><td class="num">${(r.rate * 100).toFixed(1)}%</td></tr>`).join("")}</tbody></table></div></div></div>
    <div class="box"><h2>出た直後</h2>
    ${howto("その数字が出た次の開催で、よく出た本数字です。母数は集計した回数です。")}
    <div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>数字</th><th class="num">母数</th><th>次に多い</th></tr></thead>
    <tbody>${follow.next_top
      .map(
        (r) =>
          `<tr><td>${numLink(game, r.number)}</td><td class="num">${r.sample}</td><td>${r.next.map((n) => `${numLink(game, n.number)} ${n.count}`).join("　")}</td></tr>`,
      )
      .join("")}</tbody></table></div></div></div>`,
    game,
    "follow",
  );
  bindLinks();
}

async function renderNumber(game: string, info: GameInfo, n?: number) {
  if (n == null || n < info.min_number || n > info.max_number) {
    root.innerHTML = shell(`<p class="error">指定した数字のページはありません</p>`, game, "hub");
    bindLinks();
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
      ${howto("この数字の出現回数と、同じ開催で一緒に出た数字です。")}
      ${periodBar(game, "number", period, drawCount, n)}
      ${rangeLine(data.meta)}
      <ul class="flash-meta">
        <li>本数字 ${f.count}</li>
        <li>ボーナス ${f.bonus_count ?? 0}</li>
        <li>本＋ボーナス ${f.main_plus_bonus ?? 0}</li>
        <li>期待回数 ${roundInt(f.expected_main || 0)}</li>
        <li>最終 ${formatDate(f.last_draw_date)}</li>
        <li>経過 ${sinceLabel(f.draws_since_last)}</li>
        <li>最長空白 ${f.max_rest ?? "—"}</li>
        <li>最長連続 ${f.max_streak ?? "—"}</li>
      </ul>
    </div>
    <div class="box"><h2>一緒に出た数字</h2><div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th>数字</th><th class="num">回数</th></tr></thead>
    <tbody>${data.mates.map((m) => `<tr><td>${numLink(game, m.number)}</td><td class="num">${m.count}</td></tr>`).join("")}</tbody></table></div></div></div>
    <div class="box"><h2>出た開催</h2><div class="inner pad0"><div class="table-wrap"><table class="data"><thead><tr><th class="num">回</th><th>抽せん日</th><th>本数字／ボーナス</th></tr></thead>
    <tbody>${data.items.map((item) => drawRow(item, [n])).join("")}</tbody></table></div></div></div>`,
    game,
    "number",
  );
  bindLinks();
}

async function renderRanks(game: string, _info: GameInfo) {
  const data = await api.trends(game, "all");
  const ranks = data.prize_ranks || {};
  const latest = data.latest;
  const asOf = latest
    ? `<p class="muted rank-asof">${formatDraw(latest.draw_no)}（${formatDate(latest.draw_date)}）時点</p>`
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
      <h1>金額ランキング</h1>
      ${howto("1等から3等まで、当せん金額の高い開催と低い開催です。同額はまとめています。")}
      ${asOf}
    </div>
    ${rankBoxes}
    <p class="flash-actions"><a class="btn btn-ghost" href="/${game}/freq" data-link>出現回数</a></p>
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
      ${nextNo != null ? `<p class="flash-date">${formatDraw(nextNo)}</p>` : ""}
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
        <p>数字は、過去の本数字の出現回数を重みにして機械的に選んでいます。出現が多い数字ほど選ばれやすくなります。抽せんは回ごとに独立しており、当せんを保証するものではありません。</p>
        <h3>次回予想（1口）</h3>
        <p>全期間の本数字の出現回数を使います。同じ開催回のあいだは同じ組み合わせを出します。結果が載ると、その回の予想は前回の予想へ移し、本数字の一致数を表示します。</p>
        <h3>口数で作成</h3>
        <p>指定した口数の組み合わせを、その都度作ります。「出現の多い数字」は出現回数どおりの重み、「均等」は回数の差を抑えた重みです。集計期間は全期間、直近の年数、直近の開催回数から選べます。口どうしで同じ並びはできるだけ避けます。</p>
      </div>
    </div>
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
      ev.preventDefault();
      navigate(a.getAttribute("href") || "/");
    });
  });
}

window.addEventListener("popstate", () => void render());
void render().catch((err) => {
  root.innerHTML = `<p class="error">${err.message}</p><p class="muted">${gameLabel("loto6")}</p>`;
});
