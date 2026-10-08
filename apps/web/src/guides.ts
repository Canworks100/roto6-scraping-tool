export const GUIDE_SLUGS = ["how-to-buy", "odds", "faq"] as const;
export type GuideSlug = (typeof GUIDE_SLUGS)[number];

export function isGuideSlug(id: string): id is GuideSlug {
  return (GUIDE_SLUGS as readonly string[]).includes(id);
}

const TITLES: Record<GuideSlug, string> = {
  "how-to-buy": "買い方",
  odds: "確率",
  faq: "FAQ",
};

export function guideTitle(slug: GuideSlug): string {
  return TITLES[slug];
}

export function guideHtml(label: string, slug: GuideSlug): string {
  const title = `${label} ${TITLES[slug]}`;
  return `<article class="legal"><h1>${title}</h1>${BODIES[slug](label)}</article>`;
}

const BODIES: Record<GuideSlug, (label: string) => string> = {
  "how-to-buy": (label) => `
    <p>${label}は、全国の宝くじ売り場や一部のコンビニ・銀行などで購入できます。購入方法の詳細は、宝くじ公式の案内をご確認ください。</p>
    <p>本サイトでは、過去の当せん番号の確認や出現回数の閲覧、次回の組み合わせ候補の作成ができます。購入そのものは取り扱っていません。</p>
    <p><a href="/disclaimer" data-link>免責事項</a>もあわせてご覧ください。</p>
  `,
  odds: (label) => `
    <p>${label}の当せん確率は、公式が公表する組合せの総数から決まります。抽せんは回ごとに独立しており、過去の出目は次の確率を変えません。</p>
    <p>本サイトの出現回数や予想は、過去データの整理と候補の提示です。当せんを保証するものではありません。</p>
    <p>正式な確率・ルールは、宝くじ公式の案内をご確認ください。</p>
  `,
  faq: (label) => `
    <p><strong>最新の当選番号はどこで見られますか？</strong><br />各種目の「最新結果」と「速報」から確認できます。</p>
    <p><strong>予想は当たるのですか？</strong><br />出現回数をもとにした候補の提示です。当せんを約束するものではありません。</p>
    <p><strong>公式の結果と違うことがありますか？</strong><br />掲載は参考情報です。正式な結果は宝くじ公式やみずほ銀行の案内でご確認ください。</p>
    <p>${label}の結果ページへは、ヘッダーの種目名から移動できます。</p>
  `,
};
