import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const repo = join(root, "..", "..");
const origin = (process.env.SITE_ORIGIN || "").replace(/\/+$/, "");
const SITE = "LOTOデータベース";

const GAMES = [
  { id: "loto6", label: "ロト6", max: 43 },
  { id: "loto7", label: "ロト7", max: 37 },
  { id: "miniloto", label: "ミニロト", max: 31 },
];

const VIEWS = [
  { view: "hub", path: "", title: (l) => `${l}｜${SITE}`, h1: (l) => l, desc: (l) => `${l}の最新結果、速報、結果一覧、出現回数、金額ランキング。` },
  { view: "latest", path: "/latest", title: (l) => `${l} 当選番号（最新結果）｜${SITE}`, h1: (l) => `${l} 当選番号`, desc: (l) => `${l}。直近の当せん番号と当せん金額。` },
  { view: "flash", path: "/flash", title: (l) => `${l} 速報｜${SITE}`, h1: (l) => `${l} 速報`, desc: (l) => `${l}。抽せん回ごとの当せん番号と当せん金額。` },
  { view: "history", path: "/history", title: (l) => `${l} 当選番号一覧（過去結果）｜${SITE}`, h1: (l) => `${l} 当選番号一覧`, desc: (l) => `${l}。過去の当せん番号と当せん金額を新しい順に表示します。` },
  { view: "freq", path: "/freq", title: (l) => `${l} よく出る数字・出現回数｜${SITE}`, h1: (l) => `${l} よく出る数字・出現回数`, desc: (l) => `${l}。数字ごとの出現回数と、最後に出た回。` },
  { view: "pairs", path: "/pairs", title: (l) => `${l} よく出る組み合わせ｜${SITE}`, h1: (l) => `${l} よく出る組み合わせ`, desc: (l) => `${l}。2個・3個の同時出現。` },
  { view: "shape", path: "/shape", title: (l) => `${l} 奇数偶数・合計｜${SITE}`, h1: (l) => `${l} 奇数偶数・合計`, desc: (l) => `${l}。奇数偶数、合計、連番。` },
  { view: "grid", path: "/grid", title: (l) => `${l} 出目表｜${SITE}`, h1: (l) => `${l} 出目表`, desc: (l) => `${l}。直近の出目表。` },
  { view: "follow", path: "/follow", title: (l) => `${l} 前回との重なり｜${SITE}`, h1: (l) => `${l} 前回との重なり`, desc: (l) => `${l}。直前の開催との重なりと、次に出た数字。` },
  { view: "ranks", path: "/ranks", title: (l) => `${l} 当せん金額ランキング｜${SITE}`, h1: (l) => `${l} 当せん金額ランキング`, desc: (l) => `${l}。1等から3等までの当せん金額の上位・下位。` },
  { view: "search", path: "/search", title: (l) => `${l} 数字検索｜${SITE}`, h1: (l) => `${l} 数字検索`, desc: (l) => `${l}。指定した数字が出た回を表示します。` },
  { view: "combo", path: "/combo", title: (l) => `${l} 組合診断｜${SITE}`, h1: (l) => `${l} 組合診断`, desc: (l) => `${l}。本数字1口の形と出現を、過去の開催と照らします。` },
  { view: "generate", path: "/generate", title: (l) => `${l} 予想｜${SITE}`, h1: (l) => `${l} 予想`, desc: (l) => `${l} 予想。出現回数をもとに組み合わせを作成します。` },
];

const LEGAL = [
  { path: "/about", title: `このサイトについて｜${SITE}`, h1: "このサイトについて", desc: "ロト6・ロト7・ミニロトの当せん番号を調べ、組み合わせを作成できるサイトです。" },
  { path: "/disclaimer", title: `免責事項｜${SITE}`, h1: "免責事項", desc: "掲載内容は参考情報です。正式な結果は公式の案内で確認してください。" },
  { path: "/privacy", title: `プライバシーポリシー｜${SITE}`, h1: "プライバシーポリシー", desc: "会員登録は不要です。" },
  { path: "/terms", title: `利用規約｜${SITE}`, h1: "利用規約", desc: "本サイトのご利用にあたっての規約です。" },
  { path: "/contact", title: `お問い合わせ｜${SITE}`, h1: "お問い合わせ", desc: "お問い合わせ窓口は設けていません。" },
];

function loc(path) {
  let p = path || "/";
  if (!p.startsWith("/")) p = `/${p}`;
  return origin ? `${origin}${p}` : p;
}

function writePage(path, title, description, h1) {
  const dir = join(dist, path.replace(/^\//, ""));
  mkdirSync(dir, { recursive: true });
  let html = template;
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${title}</title>`);
  if (html.includes('name="description"')) {
    html = html.replace(/<meta\s+name="description"\s+content="[^"]*"\s*\/>/, `<meta name="description" content="${description}" />`);
  } else {
    html = html.replace("</title>", `</title>\n    <meta name="description" content="${description}" />`);
  }
  const canonical = loc(path || "/");
  if (html.includes('rel="canonical"')) {
    html = html.replace(/<link rel="canonical" href="[^"]*"\s*\/>/, `<link rel="canonical" href="${canonical}" />`);
  } else {
    html = html.replace("</title>", `</title>\n    <link rel="canonical" href="${canonical}" />`);
  }
  html = html.replace(/<div id="app"><\/div>/, `<div id="app"><h1>${h1}</h1></div>`);
  writeFileSync(join(dir, "index.html"), html);
}

function latestDraws() {
  try {
    const py = `
import json, sqlite3
from pathlib import Path
p = Path(${JSON.stringify(join(repo, "data", "loto.sqlite"))})
if not p.exists():
    print("{}")
else:
    c = sqlite3.connect(p)
    out = {r[0]: int(r[1]) for r in c.execute("SELECT game, MAX(draw_no) FROM draws GROUP BY game")}
    print(json.dumps(out))
`;
    return JSON.parse(execFileSync("python3", ["-c", py], { encoding: "utf8" }).trim() || "{}");
  } catch {
    return {};
  }
}

const template = readFileSync(join(dist, "index.html"), "utf8");
const urls = [];

writePage("", SITE, "ロト6・ロト7・ミニロトの当せん番号検索。過去の結果、出現回数、組み合わせ作成。", SITE);
urls.push("/");

for (const page of LEGAL) {
  writePage(page.path.slice(1), page.title, page.desc, page.h1);
  urls.push(page.path);
}

for (const game of GAMES) {
  for (const view of VIEWS) {
    const path = `/${game.id}${view.path}`;
    writePage(path.slice(1), view.title(game.label), view.desc(game.label), view.h1(game.label));
    urls.push(path);
  }
  for (let n = 1; n <= game.max; n++) {
    const nn = String(n).padStart(2, "0");
    const path = `/${game.id}/n/${nn}`;
    writePage(
      path.slice(1),
      `${game.label} ${nn} の出現回数・相性｜${SITE}`,
      `${game.label} ${nn} の出現回数と一緒に出た数字。`,
      `${game.label} ${nn} の出現回数`,
    );
    urls.push(path);
  }
}

const latest = latestDraws();
for (const game of GAMES) {
  const maxNo = latest[game.id];
  if (!maxNo) continue;
  const start = Math.max(1, maxNo - 49);
  for (let n = start; n <= maxNo; n++) {
    const path = `/${game.id}/flash/${n}`;
    const padded = String(n).padStart(4, "0");
    writePage(
      path.slice(1),
      `${game.label} 第${padded}回 当選番号｜${SITE}`,
      `${game.label}第${padded}回の当せん番号と当せん金額。`,
      `${game.label} 第${padded}回 当選番号`,
    );
    urls.push(path);
  }
  for (let n = 1; n < start; n++) {
    urls.push(`/${game.id}/flash/${n}`);
  }
}

const body = urls
  .map((u) => `  <url><loc>${loc(u === "/" ? "/" : u)}</loc></url>`)
  .join("\n");
writeFileSync(
  join(dist, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`,
);

console.log(`prerender ${urls.length} urls`);
