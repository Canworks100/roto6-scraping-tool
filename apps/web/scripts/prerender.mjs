import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const distEnv = (process.env.LOTO_DIST_DIR || "").trim();
const dist = distEnv
  ? distEnv.startsWith("/")
    ? distEnv
    : join(root, distEnv)
  : join(root, "dist");
const repo = join(root, "..", "..");
const origin = (process.env.SITE_ORIGIN || process.env.VITE_SITE_ORIGIN || "").replace(/\/+$/, "");
const SITE = "LOTO アナリティクス";

const GAMES = [
  { id: "loto6", label: "ロト6", max: 43 },
  { id: "loto7", label: "ロト7", max: 37 },
  { id: "miniloto", label: "ミニロト", max: 31 },
];

const GUIDE_SLUGS = [
  { slug: "how-to-buy", title: "買い方" },
  { slug: "odds", title: "確率" },
  { slug: "faq", title: "FAQ" },
];

const VIEWS = [
  {
    view: "hub",
    path: "",
    title: (l) => `${l}｜${SITE}`,
    desc: (l) =>
      `${l}の当選番号や予想、出現の様子へ進む入口です。必要なページへここから辿れます。`,
  },
  {
    view: "latest",
    path: "/latest",
    title: (l) => `${l} 当選番号（最新結果）｜${SITE}`,
    desc: (l) =>
      `${l}の最新当選番号と当せん金額、次回予想をまとめて表示。キャリーオーバーの有無もこのページで確認できます。`,
  },
  {
    view: "flash",
    path: "/flash",
    title: (l) => `${l} 速報｜当選番号と当せん金額｜${SITE}`,
    desc: (l) =>
      `${l}の当選番号と当せん金額を回号ごとに掲載。前後の回へそのまま移れるので、さかのぼりやすい構成です。`,
  },
  {
    view: "history",
    path: "/history",
    title: (l) => `${l} 当選番号一覧（過去結果）｜${SITE}`,
    desc: (l) =>
      `${l}の過去の当選番号や当せん金額を、キャリーオーバーも含めて新しい回から順に一覧。気になる回を、さかのぼって探せます。`,
  },
  {
    view: "freq",
    path: "/freq",
    title: (l) => `${l} よく出る数字・出現回数｜${SITE}`,
    desc: (l) =>
      `${l}のよく出る数字と出にくい数字を出現回数で一覧。最終出現や空きも見えるので、数字選びの参考になります。`,
  },
  {
    view: "pairs",
    path: "/pairs",
    title: (l) => `${l} よく出る組み合わせ｜${SITE}`,
    desc: (l) =>
      `${l}で同じ回に一緒に出やすい2個や3個の組み合わせを、回数の多い順に整理。相性のよい並びを探すときに使えます。`,
  },
  {
    view: "shape",
    path: "/shape",
    title: (l) => `${l} 奇数偶数・合計｜${SITE}`,
    desc: (l) =>
      `${l}の奇数偶数や合計、連番など、本数字の形を開催回数で集計。自分の口の偏りを確認できます。`,
  },
  {
    view: "grid",
    path: "/grid",
    title: (l) => `${l} 出目表｜${SITE}`,
    desc: (l) =>
      `${l}の直近開催を出目表で縦に並べ、数字の並びや空きを表のまま追いやすくしました。`,
  },
  {
    view: "follow",
    path: "/follow",
    title: (l) => `${l} 前回の当選番号を含む回数｜${SITE}`,
    desc: (l) =>
      `${l}で、前回と同じ数字がまた出た回数と、2連続や3連続を数字ごとにまとめています。`,
  },
  {
    view: "ranks",
    path: "/ranks",
    title: (l) => `${l} 当せん金額ランキング｜${SITE}`,
    desc: (l) =>
      `${l}の1等から3等まで、当せん金額の高い回と低い回をランキング表示。金額の振れ幅を、ひと目で把握できます。`,
  },
  {
    view: "search",
    path: "/search",
    title: (l) => `${l} 数字検索｜出た回をまとめて確認｜${SITE}`,
    desc: (l) =>
      `${l}で気になる数字を選ぶと、本数字に出た回が一覧に。お気に入りがいつ出たか、すぐ追えます。`,
  },
  {
    view: "combo",
    path: "/combo",
    title: (l) => `${l} 組合診断｜1口の所見｜${SITE}`,
    desc: (l) =>
      `${l}の1口について、奇数偶数や合計などの所見と、過去に照合した一致の様子を表示します。`,
  },
  {
    view: "generate",
    path: "/generate",
    title: (l) => `${l} 予想｜${SITE}`,
    desc: (l) =>
      `${l}予想の候補を出現回数から作成。口数と集計期間を選んで、次の組み合わせを作れます（会員登録不要）。`,
  },
];

const LEGAL = [
  {
    path: "/about",
    title: `このサイトについて｜${SITE}`,
    h1: "このサイトについて",
    desc: "ロト6・ロト7・ミニロトの当選番号と予想を、会員登録なしで調べられるサイトです。",
    body: `<p>LOTO アナリティクスは、ロト6・ロト7・ミニロトの予想と、過去の当せん番号の確認ができるサイトです。</p>
    <p>掲載している番号・口数・金額は、公表されている抽せん結果を整理したものです。</p>
    <p>各種目のページから、予想、最新結果、速報、結果一覧、出現回数、金額ランキング、数字検索、組合診断を利用できます。</p>`,
  },
  {
    path: "/disclaimer",
    title: `免責事項｜${SITE}`,
    h1: "免責事項",
    desc: "掲載の番号や金額は参考情報。正式な結果は、宝くじ公式やみずほ銀行の案内でご確認ください。",
    body: `<p>当せん番号・等級・金額は参考情報です。正式な結果は、宝くじ公式サイトまたはみずほ銀行の当せん番号案内でご確認ください。</p>
    <p>データの反映には遅れが生じることがあります。最新回がすぐに載らない場合があります。</p>
    <p>予想は、過去の出現回数を重みにした候補の提示です。抽せんは回ごとに独立しており、当せんを約束するものではありません。</p>
    <p>本サイトの利用により生じた損害について、運営者は責任を負いません。</p>`,
  },
  {
    path: "/privacy",
    title: `プライバシーポリシー｜${SITE}`,
    h1: "プライバシーポリシー",
    desc: "会員登録なしで利用可能。数字検索のお気に入りは、お使いのブラウザのCookieに保存します。",
    body: `<p>本サイトは会員登録を行わず、閲覧だけでご利用いただけます。氏名・住所・電話番号などの入力は求めていません。</p>
    <p>数字検索の登録数字は、ブラウザのCookie（loto_fav）に保存します。会員情報としては扱いません。保存期間は最大400日で、ブラウザ側でCookieを削除すると消えます。</p>
    <p>サーバーの運用上、アクセス日時やIPアドレスなどが記録されることがあります。これらは障害対応と不正利用の防止に限り使用します。</p>
    <p>広告やアクセス解析を導入する場合は、本ページの内容を更新します。</p>`,
  },
  {
    path: "/terms",
    title: `利用規約｜${SITE}`,
    h1: "利用規約",
    desc: "本サイトのご利用条件。掲載情報の扱いと、サービス内容の変更について定めています。",
    body: `<p>本サイトを利用した時点で、本規約に同意したものとみなします。</p>
    <p>掲載情報の無断転載や、公式発表であるかのような表示はご遠慮ください。過度な自動アクセスはお断りします。</p>
    <p>サービス内容は予告なく変更・停止することがあります。</p>
    <p>本サイトは日本国内での利用を想定しています。宝くじの購入は、法令に従ってください。</p>`,
  },
  {
    path: "/contact",
    title: `お問い合わせ｜${SITE}`,
    h1: "お問い合わせ",
    desc: "お問い合わせ窓口なし。当せん結果の確認は、公式の案内をご利用ください。",
    body: `<p>本サイトに関するお問い合わせ窓口は、現在設けていません。</p>
    <p>データ内容のご確認は、宝くじ公式サイトまたはみずほ銀行の当せん番号案内をご利用ください。</p>`,
  },
];

function loc(path) {
  let p = path || "/";
  if (!p.startsWith("/")) p = `/${p}`;
  return origin ? `${origin}${p}` : p;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function pad4(n) {
  return String(n).padStart(4, "0");
}

function formatDateJa(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!m) return String(iso || "");
  return `${m[1]}年${Number(m[2])}月${Number(m[3])}日`;
}

function formatMonthDay(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!m) return "";
  return `${Number(m[2])}月${Number(m[3])}日`;
}

function flashNewsHeadline(label, drawNo, dateIso) {
  const padded = pad4(drawNo);
  const md = formatMonthDay(dateIso);
  if (md) return `第${padded}回${label}の当選番号速報　${md}の抽選結果`;
  return `第${padded}回${label}の当選番号速報`;
}

function injectMeta(html, { title, description, canonical, bodyHtml, jsonLd, article }) {
  let out = html;
  out = out.replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`);
  if (out.includes('name="description"')) {
    out = out.replace(
      /<meta\s+name="description"\s+content="[^"]*"\s*\/?>/,
      `<meta name="description" content="${esc(description)}" />`,
    );
  } else {
    out = out.replace("</title>", `</title>\n    <meta name="description" content="${esc(description)}" />`);
  }
  const canon = canonical || loc("/");
  if (out.includes('rel="canonical"')) {
    out = out.replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${canon}" />`);
  } else {
    out = out.replace("</title>", `</title>\n    <link rel="canonical" href="${canon}" />`);
  }
  const ogType = article?.ogType || "website";
  const imageAbs = "https://lottery-analytics.com/og-image.png";
  const imageAlt = "LOTO アナリティクス";
  const pub = article?.publishedTime || "";
  // index.html 既定の og/twitter 画像系を外し、ページ単位で入れ直す（重複防止）
  out = out.replace(/\s*<meta\s+property="og:image(?::(?:width|height|alt))?"\s+content="[^"]*"\s*\/?>/g, "");
  out = out.replace(/\s*<meta\s+name="twitter:(?:card|image)"\s+content="[^"]*"\s*\/?>/g, "");
  const og = `
    <meta property="og:title" content="${esc(title)}" />
    <meta property="og:description" content="${esc(description)}" />
    <meta property="og:url" content="${canon}" />
    <meta property="og:type" content="${esc(ogType)}" />
    <meta property="og:site_name" content="${SITE}" />
    <meta property="og:image" content="${esc(imageAbs)}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="${esc(imageAlt)}" />
    ${pub ? `<meta property="article:published_time" content="${esc(pub)}" />` : ""}
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:image" content="${esc(imageAbs)}" />
    <meta name="twitter:title" content="${esc(title)}" />
    <meta name="twitter:description" content="${esc(description)}" />`;
  out = out.replace("</head>", `${og}\n  </head>`);
  if (jsonLd) {
    out = out.replace(
      "</head>",
      `    <script type="application/ld+json">${JSON.stringify(jsonLd)}</script>\n  </head>`,
    );
  }
  out = out.replace(/<div id="app"><\/div>/, `<div id="app">${bodyHtml}</div>`);
  return out;
}

function writePage(path, title, description, bodyHtml, jsonLd, article) {
  const dir = join(dist, path.replace(/^\//, ""));
  mkdirSync(dir, { recursive: true });
  const html = injectMeta(template, {
    title,
    description,
    canonical: loc(path || "/"),
    bodyHtml,
    jsonLd,
    article,
  });
  writeFileSync(join(dir, "index.html"), html);
}

function chipNav(game, compact) {
  const pages = compact
    ? [
        ["latest", "最新結果"],
        ["generate", "次回予想"],
        ["freq", "出現回数"],
        ["history", "結果一覧"],
        ["flash", "速報"],
      ]
    : [
        ["latest", "最新結果"],
        ["generate", "次回予想"],
        ["history", "結果一覧"],
        ["freq", "出現回数"],
        ["pairs", "組み合わせ"],
        ["shape", "奇数偶数"],
        ["grid", "出目表"],
        ["follow", "前回を含む回数"],
        ["ranks", "金額ランキング"],
        ["search", "数字検索"],
        ["combo", "組合診断"],
        ["flash", "速報"],
      ];
  const links = pages.map(([id, t]) => `<a href="/${game.id}/${id}">${t}</a>`).join("");
  const guides = compact
    ? ""
    : `<a href="/${game.id}/guide/how-to-buy">買い方</a>
       <a href="/${game.id}/guide/odds">確率</a>
       <a href="/${game.id}/guide/faq">FAQ</a>`;
  return `<nav class="chip-nav">${links}${guides}</nav>`;
}

function homeCardBody(game) {
  const gdata = db.games?.[game.id] || {};
  const latest = gdata.latest;
  const nextNums = gdata.next_numbers || [];
  const nextNo = gdata.next_draw_no;
  const nextDate = gdata.next_draw_date;
  const latestLine = latest
    ? `第${pad4(latest.draw_no)}回（${formatDateJa(latest.draw_date)}）`
    : "—";
  const nextLine =
    nextNo != null
      ? `第${pad4(nextNo)}回${nextDate ? `（${formatDateJa(nextDate)}）` : ""}`
      : "—";
  return `<article class="home-card">
    <h2 class="home-card-lab"><a href="/${game.id}">${game.label}</a></h2>
    <section class="home-card-feat">
      <p class="home-card-k"><span>最新の当選番号</span></p>
      <p class="home-card-v">${latestLine}</p>
      <div class="home-card-balls">${latest ? ballsHtml(latest.numbers, latest.bonus) : "—"}</div>
      <p class="home-card-more"><a href="/${game.id}/latest">最新結果をみる</a></p>
    </section>
    <section class="home-card-feat">
      <p class="home-card-k"><span>次回予想</span></p>
      <p class="home-card-v">${nextLine}</p>
      <div class="home-card-balls">${
        nextNums.length
          ? `<span class="balls"><span class="balls-main">${nextNums.map((n) => `<span class="ball">${pad2(n)}</span>`).join("")}</span></span>`
          : "—"
      }</div>
      <p class="home-card-more"><a href="/${game.id}/generate">次回予想をみる</a></p>
    </section>
    <div class="home-card-more-nav">${chipNav(game, true)}</div>
  </article>`;
}

function gameBlockBody(game) {
  const gdata = db.games?.[game.id] || {};
  const latest = gdata.latest;
  const nextNums = gdata.next_numbers || [];
  const nextNo = gdata.next_draw_no;
  const nextDate = gdata.next_draw_date;
  const latestLine = latest
    ? `第${pad4(latest.draw_no)}回（${formatDateJa(latest.draw_date)}）`
    : "—";
  const nextLine =
    nextNo != null
      ? `第${pad4(nextNo)}回${nextDate ? `（抽せん日 ${formatDateJa(nextDate)}）` : ""}`
      : "—";
  return `<article class="game-block box">
    <h1 class="game-block-title">${game.label}</h1>
    <section class="game-block-sec">
      <h3>${game.label}｜最新の当選番号</h3>
      <p class="muted">${latestLine}</p>
      <div class="flash-balls">${latest ? ballsHtml(latest.numbers, latest.bonus) : "—"}</div>
    </section>
    <section class="game-block-sec">
      <h3>${game.label}｜次回予想</h3>
      <p class="muted">${nextLine}</p>
      <div class="flash-balls">${
        nextNums.length
          ? `<span class="balls"><span class="balls-main">${nextNums.map((n) => `<span class="ball">${pad2(n)}</span>`).join("")}</span></span>`
          : "—"
      }</div>
    </section>
    <section class="game-block-sec">
      <h3>${game.label}のページ</h3>
      ${chipNav(game, false)}
    </section>
  </article>`;
}

function hubBody(game) {
  return `<section class="hub">${gameBlockBody(game)}</section>`;
}

function loadDbBundle() {
  try {
    const py = `
import json, sqlite3, sys
from pathlib import Path
from datetime import date, timedelta

repo = Path(${JSON.stringify(repo)})
sys.path.insert(0, str(repo / "src"))
p = repo / "data" / "loto.sqlite"
if not p.exists():
    print("{}")
    raise SystemExit
from loto6.games import next_draw_date

# 本数字列は種目の main_count に合わせる（generate は依存が重いので使わない）
MAIN = {"loto6": 6, "loto7": 7, "miniloto": 5}
MAXN = {"loto6": 43, "loto7": 37, "miniloto": 31}
c = sqlite3.connect(p)
c.row_factory = sqlite3.Row
out = {"games": {}}
for game in ("loto6", "loto7", "miniloto"):
    main = MAIN[game]
    cols = ",".join(f"n{i}" for i in range(1, main + 1))
    latest = c.execute(
        f"SELECT draw_no, draw_date, {cols}, bonus FROM draws WHERE game=? ORDER BY draw_no DESC LIMIT 1",
        (game,),
    ).fetchone()
    if not latest:
        continue
    nums = [int(latest[f"n{i}"]) for i in range(1, main + 1)]
    last_no = int(latest["draw_no"])
    bonus2_col = ", bonus2" if game == "loto7" else ""
    hist = c.execute(
        f"SELECT draw_no, draw_date, {cols}, bonus{bonus2_col} FROM draws WHERE game=? ORDER BY draw_no DESC LIMIT 50",
        (game,),
    ).fetchall()
    hist_rows = []
    for r in hist:
        row = {
            "draw_no": int(r["draw_no"]),
            "draw_date": r["draw_date"],
            "numbers": [int(r[f"n{i}"]) for i in range(1, main + 1)],
            "bonus": int(r["bonus"]) if r["bonus"] is not None else None,
        }
        if game == "loto7":
            row["bonus2"] = int(r["bonus2"]) if r["bonus2"] is not None else None
        hist_rows.append(row)
    flashes = c.execute(
        "SELECT draw_no, draw_date FROM draws WHERE game=? ORDER BY draw_no",
        (game,),
    ).fetchall()
    flash_map = {int(r["draw_no"]): r["draw_date"] for r in flashes}
    # 直近50回のアイキャッチを dist/og へ
    dist = __import__("os").environ.get("PRERENDER_DIST")
    if dist:
        from pathlib import Path as P
        from loto6.eyecatch import eyecatch_svg
        for r in hist_rows:
            og = P(dist) / "og" / game / f'{r["draw_no"]}.svg'
            og.parent.mkdir(parents=True, exist_ok=True)
            og.write_text(
                eyecatch_svg(
                    label={"loto6": "ロト6", "loto7": "ロト7", "miniloto": "ミニロト"}[game],
                    draw_no=r["draw_no"],
                    draw_date=r["draw_date"],
                    numbers=r["numbers"],
                    bonus=r.get("bonus"),
                    bonus2=r.get("bonus2"),
                ),
                encoding="utf-8",
            )
    counts = {i: 0 for i in range(1, MAXN[game] + 1)}
    for r in c.execute(f"SELECT {cols} FROM draws WHERE game=?", (game,)):
        for i in range(1, main + 1):
            counts[int(r[f"n{i}"])] += 1
    # 次回予想数字は頻度上位から決定的に選ぶ（ビルド用・クライアントと同値でなくてよい）
    top = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    next_nums = sorted(n for n, _ in top[:main])
    out["games"][game] = {
        "latest": {
            "draw_no": last_no,
            "draw_date": latest["draw_date"],
            "numbers": nums,
            "bonus": int(latest["bonus"]) if latest["bonus"] is not None else None,
        },
        "next_draw_no": last_no + 1,
        "next_draw_date": next_draw_date(game, str(latest["draw_date"])),
        "next_numbers": next_nums,
        "history": hist_rows,
        "flashes": flash_map,
        "counts": counts,
        "max": MAXN[game],
    }
print(json.dumps(out, ensure_ascii=False))
`;
    const pyBin = existsSync(join(repo, ".venv", "bin", "python"))
      ? join(repo, ".venv", "bin", "python")
      : "python3";
    return JSON.parse(
      execFileSync(pyBin, ["-c", py], {
        encoding: "utf8",
        cwd: repo,
        env: { ...process.env, PYTHONPATH: join(repo, "src"), PRERENDER_DIST: dist },
      }).trim() || "{}",
    );
  } catch (err) {
    console.warn("prerender db bundle failed:", err.message || err);
    return { games: {} };
  }
}

const template = readFileSync(join(dist, "index.html"), "utf8");
const urls = [];
const lastmods = {};
const db = loadDbBundle();

function ballsText(numbers, bonus) {
  const mains = numbers.map((n) => pad2(n)).join(" ");
  return bonus != null ? `${mains} ボーナス ${pad2(bonus)}` : mains;
}

function ballsHtml(numbers, bonus) {
  const mains = (numbers || [])
    .map((n) => `<span class="ball">${pad2(n)}</span>`)
    .join("");
  const bonusHtml =
    bonus != null
      ? `<span class="bonus-group"><span class="bonus-lab">ボーナス</span><span class="bonus">${pad2(bonus)}</span></span>`
      : "";
  return `<span class="balls"><span class="balls-main">${mains}</span>${bonusHtml}</span>`;
}

function homeBody() {
  const cards = GAMES.map((game) => homeCardBody(game)).join("");
  const dirs = GAMES.map(
    (game) => `<div class="home-dir-row">
      <h3><a href="/${game.id}">${game.label}</a></h3>
      ${chipNav(game, false)}
    </div>`,
  ).join("");
  return `<section class="home-fv">
    <header class="hub-head">
      <h1 class="hub-title">LOTO アナリティクス</h1>
      <p class="hub-lead">ロト6・ロト7・ミニロトの最新当選番号・次回予想・出現回数・結果一覧の他、各要素、観点から分析できるツールを揃えています。高額当選を狙おう！</p>
    </header>
    <div class="home-kpi">${cards}</div>
  </section>
  <section class="box home-dirs">
    <h2>ページ一覧</h2>
    <div class="inner">${dirs}</div>
  </section>`;
}

writePage(
  "",
  `${SITE}｜ロト6・ロト7・ミニロト｜高額当選を狙おう！`,
  "ロト6・ロト7・ミニロトの最新当選番号・次回予想・出現回数・結果一覧の他、各要素、観点から分析できるツールを揃えています。高額当選を狙おう！",
  homeBody(),
);
urls.push("/");
lastmods["/"] =
  db.games?.loto6?.latest?.draw_date ||
  db.games?.loto7?.latest?.draw_date ||
  db.games?.miniloto?.latest?.draw_date;

for (const page of LEGAL) {
  writePage(
    page.path.slice(1),
    page.title,
    page.desc,
    `<article class="legal"><h1>${page.h1}</h1>${page.body}</article>`,
  );
  urls.push(page.path);
}

for (const game of GAMES) {
  const gdata = db.games?.[game.id] || {};
  const latest = gdata.latest;

  for (const view of VIEWS) {
    const path = `/${game.id}${view.path}`;
    let body = `<h1>${view.view === "hub" ? game.label : view.title(game.label).split("｜")[0]}</h1>`;
    let jsonLd = null;

    if (view.view === "hub") {
      body = hubBody(game);
    } else if (view.view === "latest" && latest) {
      const nextNums = gdata.next_numbers || [];
      const nextNo = gdata.next_draw_no;
      const nextDate = gdata.next_draw_date;
      const nextBlock = nextNums.length
        ? `<div class="box"><h2>${game.label}｜次回予想</h2>
            <div class="inner">
              <p class="muted">${nextNo != null ? `第${pad4(nextNo)}回` : "次回"}${nextDate ? `（抽せん日 ${formatDateJa(nextDate)}）` : ""}</p>
              <div class="flash-balls"><span class="balls"><span class="balls-main">${nextNums.map((n) => `<span class="ball">${pad2(n)}</span>`).join("")}</span></span></div>
              <p><a href="/${game.id}/generate">口数で作成</a>　<a href="/${game.id}/generate">次回予想ページ</a></p>
            </div></div>`
        : `<div class="box"><h2>${game.label}｜次回予想</h2>
            <div class="inner"><p><a href="/${game.id}/generate">次回予想ページ</a></p></div></div>`;
      body = `<div class="flash"><p class="flash-kicker">最新結果</p>
        <h1>${game.label} 当選番号</h1>
        <p>第${pad4(latest.draw_no)}回（${formatDateJa(latest.draw_date)}）</p>
        <div class="flash-balls">${ballsHtml(latest.numbers, latest.bonus)}</div>
        <p><a href="/${game.id}/flash/${latest.draw_no}">この回の速報</a></p></div>
        ${nextBlock}`;
      jsonLd = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        name: `${game.label} 第${pad4(latest.draw_no)}回 当選番号`,
        datePublished: latest.draw_date,
        url: loc(path),
        itemListElement: latest.numbers.map((n, i) => ({
          "@type": "ListItem",
          position: i + 1,
          name: pad2(n),
        })),
      };
      lastmods[path] = latest.draw_date;
    } else if (view.view === "generate" && gdata.next_numbers) {
      body = `<div class="flash"><p class="flash-kicker">次回予想</p>
        <h1>${game.label} 予想</h1>
        <p>第${pad4(gdata.next_draw_no)}回</p>
        <p>抽せん日 ${formatDateJa(gdata.next_draw_date)}</p>
        <p>候補 ${gdata.next_numbers.map(pad2).join(" ")}</p></div>`;
    } else if (view.view === "history" && gdata.history?.length) {
      const rows = gdata.history
        .map(
          (r) =>
            `<tr><td><a href="/${game.id}/flash/${r.draw_no}">第${pad4(r.draw_no)}回</a></td><td>${formatDateJa(r.draw_date)}</td><td>${ballsText(r.numbers, r.bonus)}</td></tr>`,
        )
        .join("");
      body = `<div class="box"><h1>${game.label} 当選番号一覧</h1>
        <table class="data"><thead><tr><th>回</th><th>抽せん日</th><th>本数字／ボーナス</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
      lastmods[path] = latest?.draw_date;
    } else if (view.view === "flash" && gdata.history?.length) {
      const items = gdata.history
        .slice(0, 20)
        .map((r) => {
          const headline = flashNewsHeadline(game.label, r.draw_no, r.draw_date);
          return `<p><a href="/${game.id}/flash/${r.draw_no}">${esc(headline)}</a><br /><span class="muted">${formatDateJa(r.draw_date)}　抽選結果・当せん金額は記事で</span></p>`;
        })
        .join("");
      body = `<div class="box"><h1>${game.label} 速報</h1>${items}</div>`;
    } else if (view.view === "search") {
      body = `<div class="box"><h1>${game.label} 数字検索</h1>
        <p>気になる数字を選ぶと、本数字に出た開催が一覧できます。登録数字はこの端末に保存します。</p></div>`;
    } else if (view.view === "combo") {
      body = `<div class="box"><h1>${game.label} 組合診断</h1>
        <p>1口の奇数偶数や合計などの所見と、過去開催との照合結果を表示します。</p></div>`;
    } else {
      const h1 = view.title(game.label).split("｜")[0];
      body = `<div class="box"><h1>${h1}</h1><p>${esc(view.desc(game.label))}</p>
        <p><a href="/${game.id}/freq">出現回数</a>　<a href="/${game.id}/history">結果一覧</a></p></div>`;
    }

    writePage(path.slice(1), view.title(game.label), view.desc(game.label), body, jsonLd);
    urls.push(path);
  }

  for (let n = 1; n <= game.max; n++) {
    const nn = pad2(n);
    const path = `/${game.id}/n/${nn}`;
    const count = gdata.counts?.[n] ?? gdata.counts?.[String(n)] ?? 0;
    const body = `<div class="box"><h1>${game.label} ${nn} の出現回数</h1>
      <p>本数字としての出現回数: ${count}回</p>
      <p><a href="/${game.id}/freq">出現回数一覧</a></p></div>`;
    writePage(
      path.slice(1),
      `${game.label} ${nn} の出現回数・相性｜${SITE}`,
      `${game.label}の数字${nn}について、出現回数や最終出現、一緒に出やすい数字をまとめました。`,
      body,
    );
    urls.push(path);
  }

  const guideDesc = {
    "how-to-buy": (l) =>
      `${l}の買い方の案内です。売り場での購入のほか、本サイトでできることとできないことをまとめています。`,
    odds: (l) =>
      `${l}の当せん確率について。抽せんは回ごとに独立で、過去の出目は次の確率を変えません。`,
    faq: (l) =>
      `${l}についてよくある質問。最新結果の見方や予想の扱い、公式結果との違いをまとめています。`,
  };
  for (const g of GUIDE_SLUGS) {
    const path = `/${game.id}/guide/${g.slug}`;
    const body = `<article class="legal"><h1>${game.label} ${g.title}</h1>
      <p>${game.label}の${g.title}についての案内です。正式な購入方法・確率は宝くじ公式の案内をご確認ください。</p>
      <p><a href="/${game.id}">${game.label}トップ</a>　<a href="/disclaimer">免責事項</a></p></article>`;
    const descFn = guideDesc[g.slug];
    writePage(
      path.slice(1),
      `${game.label} ${g.title}｜${SITE}`,
      descFn ? descFn(game.label) : `${game.label}のガイドです。`,
      body,
    );
    urls.push(path);
  }

  const flashMap = gdata.flashes || {};
  const maxNo = latest?.draw_no || 0;
  const richStart = Math.max(1, maxNo - 49);
  for (const [noStr, drawDate] of Object.entries(flashMap)) {
    const n = Number(noStr);
    const path = `/${game.id}/flash/${n}`;
    const padded = pad4(n);
    const dateJa = formatDateJa(drawDate);
    const headline = flashNewsHeadline(game.label, n, drawDate);
    const histHit = gdata.history?.find((h) => h.draw_no === n);
    const eye = `/og/${game.id}/${n}.svg?v=2`;
    const pub = `${String(drawDate).slice(0, 10)}T12:00:00+09:00`;
    let body = `<article class="post"><p class="flash-kicker">速報</p>`;
    if (n >= richStart) {
      body += `<figure class="post-eyecatch"><img src="${eye}" alt="${esc(headline)}" width="1200" height="630" /></figure>`;
    }
    body += `<h1>${esc(headline)}</h1><p>${dateJa}</p>`;
    let jsonLd = null;
    if (histHit) {
      body += `<p>本数字 ${ballsText(histHit.numbers, histHit.bonus)}</p>`;
      jsonLd = {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "NewsArticle",
            headline,
            description: `${headline}。本数字と当せん金額を掲載。`,
            datePublished: pub,
            dateModified: pub,
            mainEntityOfPage: loc(path),
            url: loc(path),
            image: [loc(eye)],
            author: { "@type": "Organization", name: SITE },
            publisher: {
              "@type": "Organization",
              name: SITE,
              logo: { "@type": "ImageObject", url: loc("/favicon.svg") },
            },
            articleSection: "宝くじ",
            inLanguage: "ja",
          },
          {
            "@type": "ItemList",
            name: `${game.label} 第${padded}回 当選番号`,
            datePublished: drawDate,
            url: loc(path),
            itemListElement: histHit.numbers.map((num, i) => ({
              "@type": "ListItem",
              position: i + 1,
              name: pad2(num),
            })),
          },
        ],
      };
    } else if (n >= richStart) {
      body += `<p>${esc(headline)}</p>`;
    } else {
      body += `<p>${game.label}第${padded}回（${dateJa}）の当選番号ページです。</p>`;
    }
    body += `<p><a href="/${game.id}/flash">速報一覧</a>　<a href="/${game.id}/latest">最新結果</a></p></article>`;
    const md = formatMonthDay(drawDate);
    const desc = md
      ? `第${padded}回${game.label}の当選番号速報。${md}の抽選結果と当せん金額、キャリーオーバーを掲載。`
      : `第${padded}回${game.label}の当選番号速報。抽選結果と当せん金額を掲載。`;
    writePage(
      path.slice(1),
      `${headline}｜${SITE}`,
      desc,
      body,
      jsonLd,
      n >= richStart
        ? { ogType: "article", image: eye, publishedTime: pub }
        : { ogType: "article", publishedTime: pub },
    );
    urls.push(path);
    if (n >= richStart) lastmods[path] = drawDate;
  }
}

// 404
writePage(
  "404",
  `ページが見つかりません｜${SITE}`,
  "お探しのページは見つかりませんでした。トップからロト6・ロト7・ミニロトの各ページへお進みください。",
  `<div class="box"><h1>ページが見つかりません</h1><p><a href="/">トップへ</a></p></div>`,
);

const sitemapUrls = [...new Set(urls)];
const body = sitemapUrls
  .map((u) => {
    const lm = lastmods[u];
    const last = lm ? `<lastmod>${String(lm).slice(0, 10)}</lastmod>` : "";
    return `  <url><loc>${loc(u === "/" ? "/" : u)}</loc>${last}</url>`;
  })
  .join("\n");
writeFileSync(
  join(dist, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`,
);

// Google News: 直近2日分の速報
const newsCutoff = Date.now() - 2 * 24 * 60 * 60 * 1000;
const newsUrls = [];
for (const game of GAMES) {
  const flashMap = db.games?.[game.id]?.flashes || {};
  for (const [noStr, drawDate] of Object.entries(flashMap)) {
    const t = Date.parse(String(drawDate).slice(0, 10));
    if (!Number.isFinite(t) || t < newsCutoff) continue;
    const n = Number(noStr);
    const path = `/${game.id}/flash/${n}`;
    const headline = flashNewsHeadline(game.label, n, drawDate);
    const pub = String(drawDate).slice(0, 10);
    newsUrls.push({ path, headline, pub });
  }
}
const newsBody = newsUrls
  .map(
    (u) => `  <url>
    <loc>${loc(u.path)}</loc>
    <news:news>
      <news:publication>
        <news:name>${SITE}</news:name>
        <news:language>ja</news:language>
      </news:publication>
      <news:publication_date>${u.pub}</news:publication_date>
      <news:title>${esc(u.headline)}</news:title>
    </news:news>
  </url>`,
  )
  .join("\n");
writeFileSync(
  join(dist, "news-sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n${newsBody}\n</urlset>\n`,
);

const sitemapLine = origin
  ? `Sitemap: ${origin}/sitemap.xml\nSitemap: ${origin}/news-sitemap.xml\n`
  : "Sitemap: /sitemap.xml\nSitemap: /news-sitemap.xml\n";
writeFileSync(join(dist, "robots.txt"), `User-agent: *\nAllow: /\n\n${sitemapLine}`);

const stagingRobots = join(root, "public", "robots.staging.txt");
if (existsSync(stagingRobots)) {
  writeFileSync(join(dist, "robots.staging.txt"), readFileSync(stagingRobots, "utf8"));
}

console.log(`prerender ${sitemapUrls.length} urls (origin=${origin || "relative"})`);
