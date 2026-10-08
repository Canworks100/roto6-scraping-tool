const SITE = "LOTO アナリティクス";

const LABELS: Record<string, string> = {
  loto6: "ロト6",
  loto7: "ロト7",
  miniloto: "ミニロト",
};

/**
 * メタ description の目安: 全角おおよそ70〜90字。
 * 文末の「〜ます。〜ます。」連打を避け、体言止め・名詞句でテンポを出す。
 */
const HOME_DESC =
  "ロト6・ロト7・ミニロトの最新当選番号・次回予想・出現回数・結果一覧の他、各要素、観点から分析できるツールを揃えています。高額当選を狙おう！";

/** トップの title 用（description に合わせた短い一句） */
const HOME_TITLE_SUFFIX = "ロト6・ロト7・ミニロト｜高額当選を狙おう！";

const LEGAL_DESC: Record<string, string> = {
  about:
    "ロト6・ロト7・ミニロトの当選番号と予想を、会員登録なしで調べられるサイトです。",
  disclaimer:
    "掲載の番号や金額は参考情報。正式な結果は、宝くじ公式やみずほ銀行の案内でご確認ください。",
  privacy:
    "会員登録なしで利用可能。数字検索のお気に入りは、お使いのブラウザのCookieに保存します。",
  terms:
    "本サイトのご利用条件。掲載情報の扱いと、サービス内容の変更について定めています。",
  contact:
    "お問い合わせ窓口なし。当せん結果の確認は、公式の案内をご利用ください。",
};

const NOT_FOUND_TITLE = `ページが見つかりません｜${SITE}`;
const NOT_FOUND_DESC =
  "お探しのページは見つかりませんでした。トップからロト6・ロト7・ミニロトの各ページへお進みください。";

const GUIDE_META: Record<string, { title: string; desc: (label: string) => string }> = {
  "how-to-buy": {
    title: "買い方",
    desc: (l) =>
      `${l}の買い方の案内です。売り場での購入のほか、本サイトでできることとできないことをまとめています。`,
  },
  odds: {
    title: "確率",
    desc: (l) =>
      `${l}の当せん確率について。抽せんは回ごとに独立で、過去の出目は次の確率を変えません。`,
  },
  faq: {
    title: "FAQ",
    desc: (l) =>
      `${l}についてよくある質問。最新結果の見方や予想の扱い、公式結果との違いをまとめています。`,
  },
};

type GameDescKey =
  | "hub"
  | "latest"
  | "flash"
  | "history"
  | "search"
  | "combo"
  | "freq"
  | "pairs"
  | "shape"
  | "grid"
  | "follow"
  | "ranks"
  | "generate";

const GAME_DESC: Record<GameDescKey, (label: string) => string> = {
  hub: (l) =>
    `${l}の当選番号や予想、出現の様子へ進む入口です。必要なページへここから辿れます。`,
  latest: (l) =>
    `${l}の最新当選番号と当せん金額、次回予想をまとめて表示。キャリーオーバーの有無もこのページで確認できます。`,
  flash: (l) =>
    `${l}の当選番号と当せん金額を回号ごとに掲載。前後の回へそのまま移れるので、さかのぼりやすい構成です。`,
  history: (l) =>
    `${l}の過去の当選番号や当せん金額を、キャリーオーバーも含めて新しい回から順に一覧。気になる回を、さかのぼって探せます。`,
  search: (l) =>
    `${l}で気になる数字を選ぶと、本数字に出た回が一覧に。お気に入りがいつ出たか、すぐ追えます。`,
  combo: (l) =>
    `${l}の1口について、奇数偶数や合計などの所見と、過去に照合した一致の様子を表示します。`,
  freq: (l) =>
    `${l}のよく出る数字と出にくい数字を出現回数で一覧。最終出現や空きも見えるので、数字選びの参考になります。`,
  pairs: (l) =>
    `${l}で同じ回に一緒に出やすい2個や3個の組み合わせを、回数の多い順に整理。相性のよい並びを探すときに使えます。`,
  shape: (l) =>
    `${l}の奇数偶数や合計、連番など、本数字の形を開催回数で集計。自分の口の偏りを確認できます。`,
  grid: (l) =>
    `${l}の直近開催を出目表で縦に並べ、数字の並びや空きを表のまま追いやすくしました。`,
  follow: (l) =>
    `${l}で、前回と同じ数字がまた出た回数と、2連続や3連続を数字ごとにまとめています。`,
  ranks: (l) =>
    `${l}の1等から3等まで、当せん金額の高い回と低い回をランキング表示。金額の振れ幅を、ひと目で把握できます。`,
  generate: (l) =>
    `${l}予想の候補を出現回数から作成。口数と集計期間を選んで、次の組み合わせを作れます（会員登録不要）。`,
};

export const PAGE_LEAD: Record<string, string> = {
  home: HOME_DESC,
  latest: "最新の当選番号と当せん金額、次回予想を確認できます。",
  flash: "回号ごとの当選番号と当せん金額を見られます。",
  history: "過去の当選番号や当せん金額を、キャリーオーバーも含めて新しい回から順に探せます。",
  search: "気になる数字が出た回を、まとめて調べられます。",
  trends: "数字ごとの出現回数と、最後に出た回を一覧できます。",
  generate: "出現回数をもとに、次回の組み合わせを作れます。",
  about: LEGAL_DESC.about,
  disclaimer: LEGAL_DESC.disclaimer,
  privacy: LEGAL_DESC.privacy,
  terms: LEGAL_DESC.terms,
  contact: LEGAL_DESC.contact,
};

function gameDesc(label: string, key: GameDescKey): string {
  return GAME_DESC[key](label);
}

function flashDrawDesc(label: string, padded: string, dateIso?: string): string {
  const md = formatMonthDay(dateIso || "");
  if (md) {
    return `第${padded}回${label}の当選番号速報。${md}の抽選結果と当せん金額、キャリーオーバーを掲載。`;
  }
  return `第${padded}回${label}の当選番号速報。抽選結果と当せん金額を掲載。`;
}

function numberDesc(label: string, nn: string): string {
  return `${label}の数字${nn}について、出現回数や最終出現、一緒に出やすい数字をまとめました。`;
}

function formatDateJa(iso: string): string {
  const matched = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!matched) return iso;
  return `${matched[1]}年${Number(matched[2])}月${Number(matched[3])}日`;
}

/** 10月5日 */
export function formatMonthDay(iso: string): string {
  const matched = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!matched) return "";
  return `${Number(matched[2])}月${Number(matched[3])}日`;
}

/** 47NEWS系に寄せた速報見出し */
export function flashNewsHeadline(label: string, drawNo: number, dateIso?: string): string {
  const padded = String(drawNo).padStart(4, "0");
  const md = formatMonthDay(dateIso || "");
  if (md) return `第${padded}回${label}の当選番号速報　${md}の抽選結果`;
  return `第${padded}回${label}の当選番号速報`;
}

/** アイキャッチ差し替え時に上げる（ブラウザキャッシュ避け） */
const EYECATCH_VER = "3";

export function eyecatchPath(game: string, drawNo: number): string {
  return `/og/${game}/${drawNo}.svg?v=${EYECATCH_VER}`;
}

export function eyecatchApiPath(game: string, drawNo: number): string {
  return `/api/${game}/articles/${drawNo}/eyecatch.svg?v=${EYECATCH_VER}`;
}

/** ビルド時 VITE_SITE_ORIGIN。未設定時はブラウザの origin。 */
export function siteOrigin(): string {
  const fromEnv = String(import.meta.env.VITE_SITE_ORIGIN || "")
    .trim()
    .replace(/\/+$/, "");
  if (fromEnv) return fromEnv;
  if (typeof location !== "undefined" && location.origin) return location.origin;
  return "";
}

export function absoluteUrl(path: string): string {
  const clean = (path.split("?")[0] || "/").replace(/\/+$/, "") || "/";
  const normalized = clean.startsWith("/") ? clean : `/${clean}`;
  const origin = siteOrigin();
  return origin ? `${origin}${normalized === "/" ? "/" : normalized}` : normalized;
}

function ensureMeta(attr: "name" | "property", key: string): HTMLMetaElement {
  const sel = attr === "name" ? `meta[name="${key}"]` : `meta[property="${key}"]`;
  let el = document.querySelector(sel) as HTMLMetaElement | null;
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  return el;
}

function setRobots(content: string | null) {
  const el = ensureMeta("name", "robots");
  if (content) el.setAttribute("content", content);
  else el.remove();
}

export function setJsonLd(data: Record<string, unknown> | null) {
  const id = "jsonld-main";
  let el = document.getElementById(id) as HTMLScriptElement | null;
  if (!data) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement("script");
    el.type = "application/ld+json";
    el.id = id;
    document.head.appendChild(el);
  }
  el.textContent = JSON.stringify(data);
}

export type SeoOpts = {
  drawDate?: string;
  noindex?: boolean;
  ogType?: "website" | "article";
  image?: string;
  publishedTime?: string;
  /** 指定時はパス解決より優先（404 など） */
  title?: string;
  description?: string;
};

export function setSeo(path: string, opts?: SeoOpts) {
  const parts = path.replace(/^\//, "").split("/").filter(Boolean);
  let title = `${SITE}｜${HOME_TITLE_SUFFIX}`;
  let description = HOME_DESC;

  if (parts.length === 0) {
    title = `${SITE}｜${HOME_TITLE_SUFFIX}`;
    description = HOME_DESC;
  } else if (parts[0] === "about") {
    title = `このサイトについて｜${SITE}`;
    description = LEGAL_DESC.about;
  } else if (parts[0] === "disclaimer") {
    title = `免責事項｜${SITE}`;
    description = LEGAL_DESC.disclaimer;
  } else if (parts[0] === "privacy") {
    title = `プライバシーポリシー｜${SITE}`;
    description = LEGAL_DESC.privacy;
  } else if (parts[0] === "terms") {
    title = `利用規約｜${SITE}`;
    description = LEGAL_DESC.terms;
  } else if (parts[0] === "contact") {
    title = `お問い合わせ｜${SITE}`;
    description = LEGAL_DESC.contact;
  } else if (parts[0] === "404") {
    title = NOT_FOUND_TITLE;
    description = NOT_FOUND_DESC;
  } else {
    const game = parts[0];
    const label = LABELS[game] || game;
    const view = parts[1] || "hub";
    if (!parts[1] || view === "hub") {
      title = `${label}｜${SITE}`;
      description = gameDesc(label, "hub");
    } else if (view === "latest") {
      title = `${label} 当選番号（最新結果）｜${SITE}`;
      description = gameDesc(label, "latest");
    } else if (view === "flash") {
      const drawNo = parts[2];
      if (drawNo) {
        const n = Number(drawNo);
        const padded = String(n).padStart(4, "0");
        title = `${flashNewsHeadline(label, n, opts?.drawDate)}｜${SITE}`;
        description = flashDrawDesc(label, padded, opts?.drawDate);
      } else {
        title = `${label} 速報｜当選番号と当せん金額｜${SITE}`;
        description = gameDesc(label, "flash");
      }
    } else if (view === "generate") {
      title = `${label} 予想｜${SITE}`;
      description = gameDesc(label, "generate");
    } else if (view === "search") {
      title = `${label} 数字検索｜出た回をまとめて確認｜${SITE}`;
      description = gameDesc(label, "search");
    } else if (view === "combo") {
      title = `${label} 組合診断｜1口の所見｜${SITE}`;
      description = gameDesc(label, "combo");
    } else if (view === "freq" || view === "trends") {
      title = `${label} よく出る数字・出現回数｜${SITE}`;
      description = gameDesc(label, "freq");
    } else if (view === "pairs") {
      title = `${label} よく出る組み合わせ｜${SITE}`;
      description = gameDesc(label, "pairs");
    } else if (view === "shape") {
      title = `${label} 奇数偶数・合計｜${SITE}`;
      description = gameDesc(label, "shape");
    } else if (view === "grid") {
      title = `${label} 出目表｜${SITE}`;
      description = gameDesc(label, "grid");
    } else if (view === "follow") {
      title = `${label} 前回の当選番号を含む回数｜${SITE}`;
      description = gameDesc(label, "follow");
    } else if (view === "n") {
      const nn = parts[2] ? String(Number(parts[2])).padStart(2, "0") : "";
      title = `${label} ${nn} の出現回数・相性｜${SITE}`;
      description = numberDesc(label, nn);
    } else if (view === "ranks") {
      title = `${label} 当せん金額ランキング｜${SITE}`;
      description = gameDesc(label, "ranks");
    } else if (view === "history") {
      title = `${label} 当選番号一覧（過去結果）｜${SITE}`;
      description = gameDesc(label, "history");
    } else if (view === "guide") {
      const slug = parts[2] || "";
      const meta = GUIDE_META[slug];
      if (meta) {
        title = `${label} ${meta.title}｜${SITE}`;
        description = meta.desc(label);
      } else {
        title = `${label} ガイド｜${SITE}`;
        description = `${label}の買い方・確率・よくある質問への案内です。`;
      }
    } else {
      title = `${label}｜${SITE}`;
      description = gameDesc(label, "hub");
    }
  }

  if (opts?.title) title = opts.title;
  if (opts?.description) description = opts.description;

  const cleanPath = path.split("?")[0] || "/";
  const abs = absoluteUrl(cleanPath);
  const params = new URLSearchParams(typeof location !== "undefined" ? location.search : "");
  const hasIndexQuery = params.has("period") || params.has("rows") || params.has("page");
  const robots =
    opts?.noindex || hasIndexQuery ? "noindex, follow" : "index, follow";

  document.title = title;
  ensureMeta("name", "description").setAttribute("content", description);
  setRobots(robots);

  let canonical = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null;
  if (!canonical) {
    canonical = document.createElement("link");
    canonical.setAttribute("rel", "canonical");
    document.head.appendChild(canonical);
  }
  canonical.setAttribute("href", abs);

  const ogType = opts?.ogType || "website";
  ensureMeta("property", "og:title").setAttribute("content", title);
  ensureMeta("property", "og:description").setAttribute("content", description);
  ensureMeta("property", "og:url").setAttribute("content", abs);
  ensureMeta("property", "og:type").setAttribute("content", ogType);
  ensureMeta("property", "og:site_name").setAttribute("content", SITE);
  const imageAbs = opts?.image ? absoluteUrl(opts.image) : "";
  if (imageAbs) {
    ensureMeta("property", "og:image").setAttribute("content", imageAbs);
    ensureMeta("name", "twitter:image").setAttribute("content", imageAbs);
  }
  if (opts?.publishedTime) {
    ensureMeta("property", "article:published_time").setAttribute("content", opts.publishedTime);
  }
  ensureMeta("name", "twitter:card").setAttribute(
    "content",
    imageAbs ? "summary_large_image" : "summary",
  );
  ensureMeta("name", "twitter:title").setAttribute("content", title);
  ensureMeta("name", "twitter:description").setAttribute("content", description);
}

export function gameLabel(id: string): string {
  return LABELS[id] || id;
}

export function drawResultJsonLd(opts: {
  label: string;
  drawNo: number;
  drawDate: string;
  numbers: number[];
  url: string;
}): Record<string, unknown> {
  const padded = String(opts.drawNo).padStart(4, "0");
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `${opts.label} 第${padded}回 当選番号`,
    datePublished: opts.drawDate,
    url: opts.url,
    itemListElement: opts.numbers.map((n, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: String(n).padStart(2, "0"),
    })),
  };
}

export function flashNewsJsonLd(opts: {
  label: string;
  drawNo: number;
  drawDate: string;
  numbers: number[];
  url: string;
  image: string;
  description: string;
}): Record<string, unknown> {
  const headline = flashNewsHeadline(opts.label, opts.drawNo, opts.drawDate);
  const imageAbs = absoluteUrl(opts.image);
  const datePub = /^\d{4}-\d{2}-\d{2}/.test(opts.drawDate)
    ? `${opts.drawDate.slice(0, 10)}T12:00:00+09:00`
    : opts.drawDate;
  const list = drawResultJsonLd({
    label: opts.label,
    drawNo: opts.drawNo,
    drawDate: opts.drawDate,
    numbers: opts.numbers,
    url: opts.url,
  });
  delete list["@context"];
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "NewsArticle",
        headline,
        description: opts.description,
        datePublished: datePub,
        dateModified: datePub,
        mainEntityOfPage: opts.url,
        url: opts.url,
        image: [imageAbs],
        author: { "@type": "Organization", name: SITE },
        publisher: {
          "@type": "Organization",
          name: SITE,
          logo: { "@type": "ImageObject", url: absoluteUrl("/favicon.svg") },
        },
        articleSection: "宝くじ",
        inLanguage: "ja",
      },
      list,
    ],
  };
}
