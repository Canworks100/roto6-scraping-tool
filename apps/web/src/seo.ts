const SITE = "LOTOデータベース";

const LABELS: Record<string, string> = {
  loto6: "ロト6",
  loto7: "ロト7",
  miniloto: "ミニロト",
};

export const PAGE_LEAD: Record<string, string> = {
  home: "ロト6・ロト7・ミニロトの当せん番号検索。過去の結果、出現回数、組み合わせ作成に対応しています。",
  latest: "直近の当せん番号と当せん金額を表示します。",
  flash: "抽せん回ごとの当せん番号と当せん金額です。",
  history: "過去の当せん番号と当せん金額を、新しい順に表示します。",
  search: "指定した数字が本数字またはボーナスに出た回を表示します。",
  trends: "数字ごとの出現回数と、最後に出た回を表示します。",
  generate: "出現回数をもとに組み合わせを作成します。",
  about: "ロト6・ロト7・ミニロトの当せん番号を調べ、組み合わせを作成できるサイトです。",
  disclaimer: "掲載内容は参考情報です。正式な結果は公式の案内で確認してください。",
  privacy: "会員登録は不要です。お問い合わせでいただいた情報は、返信に限り使用します。",
  terms: "本サイトのご利用にあたっての規約です。",
  contact: "お問い合わせ窓口は設けていません。結果の確認は公式案内をご利用ください。",
};

const META_DESC: Record<string, string> = {
  home: "ロト6・ロト7・ミニロトの当せん番号検索。過去の結果、出現回数、組み合わせ作成。",
  latest: "直近の当せん番号と当せん金額。",
  flash: "抽せん回ごとの当せん番号と当せん金額。",
  history: "過去の当せん番号と当せん金額を新しい順に表示します。",
  search: "指定した数字が出た回を表示します。",
  combo: "本数字1口の形と出現を、過去の開催と照らします。",
  freq: "数字ごとの出現回数と、最後に出た回。",
  pairs: "2個・3個の同時出現。",
  shape: "奇数偶数、合計、連番。",
  grid: "直近の出目表。",
  follow: "直前の開催との重なりと、次に出た数字。",
  ranks: "1等から3等までの当せん金額の上位・下位。",
  generate: "出現回数をもとに組み合わせを作成します。",
  about: "ロト6・ロト7・ミニロトの当せん番号を調べ、組み合わせを作成できるサイトです。",
  disclaimer: "掲載内容は参考情報です。正式な結果は公式の案内で確認してください。",
  privacy: "会員登録は不要です。お問い合わせでいただいた情報は返信に限り使用します。",
  terms: "本サイトのご利用にあたっての規約です。",
  contact: "お問い合わせ窓口は設けていません。結果の確認は公式案内をご利用ください。",
};

export function setSeo(path: string) {
  const parts = path.replace(/^\//, "").split("/").filter(Boolean);
  let title = SITE;
  let description = META_DESC.home;

  if (parts.length === 0) {
    title = SITE;
    description = META_DESC.home;
  } else if (parts[0] === "about") {
    title = `このサイトについて｜${SITE}`;
    description = META_DESC.about;
  } else if (parts[0] === "disclaimer") {
    title = `免責事項｜${SITE}`;
    description = META_DESC.disclaimer;
  } else if (parts[0] === "privacy") {
    title = `プライバシーポリシー｜${SITE}`;
    description = META_DESC.privacy;
  } else if (parts[0] === "terms") {
    title = `利用規約｜${SITE}`;
    description = META_DESC.terms;
  } else if (parts[0] === "contact") {
    title = `お問い合わせ｜${SITE}`;
    description = META_DESC.contact;
  } else {
    const game = parts[0];
    const label = LABELS[game] || game;
    const view = parts[1] || "hub";
    if (!parts[1] || view === "hub") {
      title = `${label}｜${SITE}`;
      description = `${label}の最新結果、速報、結果一覧、出現回数、金額ランキング。`;
    } else if (view === "latest") {
      title = `${label} 当選番号（最新結果）｜${SITE}`;
      description = `${label}。${META_DESC.latest}`;
    } else if (view === "flash") {
      const drawNo = parts[2];
      if (drawNo) {
        title = `${label} 第${String(drawNo).padStart(4, "0")}回 当選番号｜${SITE}`;
        description = `${label}第${String(drawNo).padStart(4, "0")}回の当せん番号と当せん金額。`;
      } else {
        title = `${label} 速報｜${SITE}`;
        description = `${label}。${META_DESC.flash}`;
      }
    } else if (view === "generate") {
      title = `${label} 予想｜${SITE}`;
      description = `${label} 予想。${META_DESC.generate}`;
    } else if (view === "search") {
      title = `${label} 数字検索｜${SITE}`;
      description = `${label}。${META_DESC.search}`;
    } else if (view === "combo") {
      title = `${label} 組合診断｜${SITE}`;
      description = `${label}。${META_DESC.combo}`;
    } else if (view === "freq" || view === "trends") {
      title = `${label} よく出る数字・出現回数｜${SITE}`;
      description = `${label}。${META_DESC.freq}`;
    } else if (view === "pairs") {
      title = `${label} よく出る組み合わせ｜${SITE}`;
      description = `${label}。${META_DESC.pairs}`;
    } else if (view === "shape") {
      title = `${label} 奇数偶数・合計｜${SITE}`;
      description = `${label}。${META_DESC.shape}`;
    } else if (view === "grid") {
      title = `${label} 出目表｜${SITE}`;
      description = `${label}。${META_DESC.grid}`;
    } else if (view === "follow") {
      title = `${label} 前回との重なり｜${SITE}`;
      description = `${label}。${META_DESC.follow}`;
    } else if (view === "n") {
      const nn = parts[2] ? String(Number(parts[2])).padStart(2, "0") : "";
      title = `${label} ${nn} の出現回数・相性｜${SITE}`;
      description = `${label} ${nn} の出現回数と一緒に出た数字。`;
    } else if (view === "ranks") {
      title = `${label} 当せん金額ランキング｜${SITE}`;
      description = `${label}。${META_DESC.ranks}`;
    } else if (view === "history") {
      title = `${label} 当選番号一覧（過去結果）｜${SITE}`;
      description = `${label}。${META_DESC.history}`;
    } else {
      title = `${label}｜${SITE}`;
      description = `${label}。${META_DESC.home}`;
    }
  }

  document.title = title;
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute("content", description);
  const clean = path.split("?")[0] || "/";
  let canonical = document.querySelector('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement("link");
    canonical.setAttribute("rel", "canonical");
    document.head.appendChild(canonical);
  }
  canonical.setAttribute("href", clean);
}

export function gameLabel(id: string): string {
  return LABELS[id] || id;
}
