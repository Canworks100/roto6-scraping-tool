import "./styles.css";
import * as api from "./api";
import type { DrawItem, GameInfo, PrizeRankGroup, PrizeRankItem } from "./api";
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

type Route = { game?: string; view: string; drawNo?: number };

function parseRoute(): Route {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { view: "home" };
  if (isLegalPage(parts[0])) return { view: parts[0] };
  if (parts[1] === "flash") {
    const raw = parts[2] ? Number(parts[2]) : undefined;
    return { game: parts[0], view: "flash", drawNo: raw && Number.isFinite(raw) ? raw : undefined };
  }
  let view = parts[1] || "hub";
  if (view === "trends") view = "freq";
  return { game: parts[0], view };
}

const GAME_PAGES: [string, string][] = [
  ["latest", "最新結果"],
  ["flash", "速報"],
  ["history", "結果一覧"],
  ["freq", "出現回数"],
  ["ranks", "金額ランキング"],
  ["search", "数字検索"],
  ["generate", "出目生成"],
];

function viewPath(game: string, view: string, drawNo?: number): string {
  if (view === "hub" || view === "home") return `/${game}`;
  if (view === "flash") return drawNo ? `/${game}/flash/${drawNo}` : `/${game}/flash`;
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

function shell(inner: string, activeGame?: string, activeView?: string): string {
  const switchView = activeView && activeView !== "home" ? activeView : "hub";
  const gameLinks = games
    .map((g) => {
      const href = activeGame ? viewPath(g.id, switchView === "flash" ? "flash" : switchView) : `/${g.id}`;
      const on = activeGame === g.id;
      return `<a href="${href}" class="${on ? "active" : ""}"${on ? ' aria-current="page"' : ""} data-link>${g.label}</a>`;
    })
    .join("");
  const pages = activeGame ? pageLinks(activeGame, activeView) : "";
  const pagesPc = activeGame
    ? `<nav class="nav-pages-pc" aria-label="ページ">${pages}</nav>`
    : "";
  return `
    <header class="site-head">
      <div class="topbar">
        <a class="brand" href="/" data-link>LOTO<span>データベース</span></a>
        <nav class="nav-games" aria-label="ロト">${gameLinks}</nav>
        <button type="button" class="menu-toggle" id="menu-toggle" aria-expanded="false" aria-controls="sp-drawer">
          <span class="menu-toggle-bars" aria-hidden="true"></span>
          メニュー
        </button>
      </div>
      ${pagesPc}
    </header>
    <div class="sp-mask" id="sp-mask" hidden></div>
    <div class="sp-drawer" id="sp-drawer" hidden>
      <div class="sp-drawer-head">
        <strong>メニュー</strong>
        <button type="button" class="menu-close" id="menu-close">閉じる</button>
      </div>
      <p class="sp-label">ロト</p>
      <nav class="sp-games" aria-label="ロト">${gameLinks}</nav>
      ${
        activeGame
          ? `<p class="sp-label">${gameLabel(activeGame)}</p><nav class="sp-pages" aria-label="ページ">${pages}</nav>`
          : ""
      }
    </div>
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

  if (isLegalPage(route.view)) {
    root.innerHTML = shell(legalHtml(route.view), undefined, route.view);
    bindLinks();
    return;
  }

  if (route.view === "home" || !route.game) {
    const metas = await Promise.all(games.map((g) => api.gameMeta(g.id).catch(() => null)));
    root.innerHTML = shell(`
      <div class="box">
        <h2>ロトを選ぶ</h2>
        <div class="home-list">
          ${games
            .map((g, i) => {
              const m = metas[i];
              const count = m?.draw_count?.toLocaleString() ?? "—";
              return `<a href="/${g.id}" data-link>
                <span class="g">${g.label}</span>
                <span class="d">${g.min_number}〜${g.max_number} / 本数字${g.main_count}</span>
                <span class="n">${count}回</span>
              </a>`;
            })
            .join("")}
        </div>
      </div>
    `);
    bindLinks();
    return;
  }

  const game = route.game;
  const info = games.find((g) => g.id === game);
  if (!info) {
    root.innerHTML = shell(`<p class="error">指定したロトが見つかりません</p>`);
    bindLinks();
    return;
  }

  const allowed = ["hub", "latest", "flash", "history", "search", "freq", "ranks", "generate", "trends"];
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
    else if (view === "freq") await renderFreq(game, info);
    else if (view === "ranks") await renderRanks(game, info);
    else await renderGenerate(game, info);
  } catch (err) {
    root.innerHTML = shell(`<p class="error">${(err as Error).message}</p>`, game, view);
    bindLinks();
  }
}

async function renderHub(game: string, info: GameInfo) {
  const pages = [
    ["latest", "最新結果", "直近の当せん番号と金額"],
    ["flash", "速報", "抽せん回ごとの結果"],
    ["history", "結果一覧", "過去の当せん番号と金額"],
    ["freq", "出現回数", "数字ごとの出現状況"],
    ["ranks", "金額ランキング", "1〜3等の最高額と最低額"],
    ["search", "数字検索", "指定した数字が出た回"],
    ["generate", "出目生成", "出現回数をもとに組み合わせを作成"],
  ];
  root.innerHTML = shell(
    `
    <div class="box">
      <h2>${info.label}</h2>
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
        <a class="btn" href="/${game}/flash/${item.draw_no}" data-link>この回の速報</a>
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
    ? `<a href="/${game}/flash/${article.prev_draw_no}" data-link>前の回</a>`
    : `<span>前の回</span>`;
  const next = article.next_draw_no
    ? `<a href="/${game}/flash/${article.next_draw_no}" data-link>次の回</a>`
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
        <a class="btn" href="/${game}/flash" data-link>速報一覧</a>
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
      <div class="inner">
        <div class="fav-panel">
          <div class="fav-head">
            <span>登録数字</span>
            <span class="fav-note">このブラウザに保存します</span>
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

async function renderFreq(game: string, _info: GameInfo) {
  const data = await api.trends(game, 10);
  const rows = data.frequency || [];
  const latest = data.latest;
  const asOf = latest
    ? `<p class="muted rank-asof">${formatDraw(latest.draw_no)}（${formatDate(latest.draw_date)}）時点</p>`
    : "";
  const freqBox = data.error
    ? `<p class="error">${data.error}</p>`
    : `<div class="box">
      <h2>出現回数</h2>
      ${asOf}
      <div class="inner pad0">
        <div class="table-wrap">
          <table class="data">
            <thead><tr><th class="num">順位</th><th class="num">数字</th><th class="num">回数</th><th class="num">割合</th><th>最終</th><th class="num">経過</th></tr></thead>
            <tbody>
              ${rows
                .map((row) => {
                  const since = row.draws_since_last;
                  const sinceLabel = since == null ? "—" : since === 0 ? "今回" : `${since}回前`;
                  return `<tr>
                    <td class="num">${row.rank}</td>
                    <td class="num">${pad2(row.number)}</td>
                    <td class="num">${row.count}</td>
                    <td class="num">${(row.probability * 100).toFixed(1)}%</td>
                    <td>${formatDate(row.last_draw_date)}</td>
                    <td class="num">${sinceLabel}</td>
                  </tr>`;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
  root.innerHTML = shell(
    `
    ${freqBox}
    <p class="flash-actions"><a class="btn btn-ghost" href="/${game}/ranks" data-link>金額ランキング</a></p>
  `,
    game,
    "freq",
  );
  bindLinks();
}

async function renderRanks(game: string, _info: GameInfo) {
  const data = await api.trends(game, 10);
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
    ${asOf}
    ${rankBoxes}
    <p class="flash-actions"><a class="btn btn-ghost" href="/${game}/freq" data-link>出現回数</a></p>
  `,
    game,
    "ranks",
  );
  bindLinks();
}

async function renderGenerate(game: string, _info: GameInfo) {
  root.innerHTML = shell(
    `
    <div class="box">
      <h2>出目生成</h2>
      <div class="inner">
        <div class="toolbar" style="margin:0;border:0;padding:0">
          <label class="field">口数
            <input id="tickets" type="number" min="1" max="20" value="5" />
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
  `,
    game,
    "generate",
  );
  document.querySelector("#do-gen")!.addEventListener("click", async () => {
    const tickets = Number((document.querySelector("#tickets") as HTMLInputElement).value || 5);
    const mode = (document.querySelector("#mode") as HTMLSelectElement).value as "hot" | "balanced";
    const period = (document.querySelector("#period") as HTMLSelectElement).value;
    const body: Parameters<typeof api.generate>[1] = { tickets, mode };
    if (period === "years5") body.recent_years = 5;
    if (period === "years10") body.recent_years = 10;
    if (period === "draws100") body.recent_draws = 100;
    if (period === "draws300") body.recent_draws = 300;
    const out = document.querySelector("#gen-out")!;
    out.innerHTML = `<p class="muted">作成しています…</p>`;
    try {
      const res = await api.generate(game, body);
      const copyText = res.combos.map((c) => c.numbers.map(pad2).join(" ")).join("\n");
      out.innerHTML = `
        <div class="box">
          <h2>組み合わせ ${res.combos.length} 口（対象 ${res.draw_count} 回 / ${res.mode === "hot" ? "出現の多い数字" : "均等"}）</h2>
          <div class="inner pad0">
            ${res.combos
              .map(
                (c) => `
              <div class="combo-row">
                <span class="idx">${c.index}</span>
                <span class="balls">${c.numbers.map((n) => `<span class="ball">${pad2(n)}</span>`).join("")}</span>
              </div>`,
              )
              .join("")}
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
  document.body.classList.remove("menu-open");
  document.querySelectorAll<HTMLAnchorElement>("a[data-link]").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      navigate(a.getAttribute("href") || "/");
    });
  });
  const toggle = document.querySelector<HTMLButtonElement>("#menu-toggle");
  const drawer = document.querySelector<HTMLElement>("#sp-drawer");
  const mask = document.querySelector<HTMLElement>("#sp-mask");
  const setOpen = (open: boolean) => {
    if (!toggle || !drawer || !mask) return;
    drawer.hidden = !open;
    mask.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("menu-open", open);
  };
  toggle?.addEventListener("click", () => setOpen(drawer?.hidden !== false));
  document.querySelector("#menu-close")?.addEventListener("click", () => setOpen(false));
  mask?.addEventListener("click", () => setOpen(false));
}

window.addEventListener("popstate", () => void render());
void render().catch((err) => {
  root.innerHTML = `<p class="error">${err.message}</p><p class="muted">${gameLabel("loto6")}</p>`;
});
