export const LEGAL_PAGES = ["about", "disclaimer", "privacy", "terms", "contact"] as const;
export type LegalId = (typeof LEGAL_PAGES)[number];

export function isLegalPage(id: string): id is LegalId {
  return (LEGAL_PAGES as readonly string[]).includes(id);
}

const TITLES: Record<LegalId, string> = {
  about: "このサイトについて",
  disclaimer: "免責事項",
  privacy: "プライバシーポリシー",
  terms: "利用規約",
  contact: "お問い合わせ",
};

export function legalTitle(id: LegalId): string {
  return TITLES[id];
}

export function legalHtml(id: LegalId): string {
  return `<article class="legal"><h2>${TITLES[id]}</h2>${BODIES[id]}</article>`;
}

const BODIES: Record<LegalId, string> = {
  about: `
    <p>LOTOデータベースは、ロト6・ロト7・ミニロトの過去の当せん番号を調べ、出現回数をもとに組み合わせを作成できるサイトです。</p>
    <p>掲載している番号・口数・金額は、公表されている抽せん結果を整理したものです。</p>
    <p>各ロトのページから、最新結果、速報、結果一覧、出現回数、金額ランキング、数字検索、出目生成を利用できます。</p>
  `,
  disclaimer: `
    <p>当せん番号・等級・金額は参考情報です。正式な結果は、宝くじ公式サイトまたはみずほ銀行の当せん番号案内でご確認ください。</p>
    <p>データの反映には遅れが生じることがあります。最新回がすぐに載らない場合があります。</p>
    <p>出目生成は、過去の出現回数を重みにした候補の提示です。抽せんは回ごとに独立しており、当せんを約束するものではありません。</p>
    <p>本サイトの利用により生じた損害について、運営者は責任を負いません。</p>
  `,
  privacy: `
    <p>本サイトは会員登録を行わず、閲覧だけでご利用いただけます。氏名・住所・電話番号などの入力は求めていません。</p>
    <p>数字検索の登録数字は、ブラウザのCookie（loto_fav）に保存します。会員情報としては扱いません。保存期間は最大400日で、ブラウザ側でCookieを削除すると消えます。</p>
    <p>サーバーの運用上、アクセス日時やIPアドレスなどが記録されることがあります。これらは障害対応と不正利用の防止に限り使用します。</p>
    <p>広告やアクセス解析を導入する場合は、本ページの内容を更新します。</p>
    <p>お問い合わせで連絡先をお預かりしたときは、返信の目的に限って利用し、目的達成後は速やかに削除します。</p>
  `,
  terms: `
    <p>本サイトを利用した時点で、本規約に同意したものとみなします。</p>
    <p>掲載情報の無断転載や、公式発表であるかのような表示はご遠慮ください。過度な自動アクセスはお断りします。</p>
    <p>サービス内容は予告なく変更・停止することがあります。</p>
    <p>本サイトは日本国内での利用を想定しています。宝くじの購入は、法令に従ってください。</p>
  `,
  contact: `
    <p>本サイトに関するお問い合わせ窓口は、現在設けていません。</p>
    <p>データ内容のご確認は、宝くじ公式サイトまたはみずほ銀行の当せん番号案内をご利用ください。</p>
  `,
};
