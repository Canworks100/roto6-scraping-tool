/** ロト購入シミュレーター（ブラウザ側で抽せん・判定） */

export const DETAIL_THRESHOLD = 50;
export const MAX_HAND_TICKETS = 500;
export const YEN_CAP = 200_000_000;

export type SimuGameDef = {
  id: string;
  label: string;
  min_number: number;
  max_number: number;
  main_count: number;
  bonus_count: number;
  unit_price: number;
  simu_grade1_base: number;
  simu_prizes: Record<number, number>;
};

export type SimuDetail = {
  index: number;
  source: string;
  numbers: number[];
  grade: number | null;
  match_count: number;
  bonus_hit: boolean;
  amount: number;
};

export type SimuResult = {
  game: string;
  label: string;
  unit_price: number;
  ticket_count: number;
  hand_count: number;
  random_count: number;
  cost: number;
  prize_total: number;
  net: number;
  carryover_amount: number;
  grade1_pool: number;
  draw: { numbers: number[]; bonuses: number[] };
  by_grade: { grade: number; count: number; amount_each: number; amount_total: number }[];
  winners_only: boolean;
  detail_threshold: number;
  details: SimuDetail[];
  max_tickets: number;
};

export class SimuError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SimuError";
  }
}

export function maxTicketsFor(unitPrice: number): number {
  return Math.max(1, Math.floor(YEN_CAP / Math.max(1, unitPrice)));
}

function ticketGrade(
  picked: Set<number>,
  mains: Set<number>,
  bonuses: Set<number>,
  mainCount: number,
): [number | null, number, boolean] {
  let hit = 0;
  for (const n of picked) if (mains.has(n)) hit += 1;
  let bonusHit = false;
  for (const n of picked) {
    if (bonuses.has(n)) {
      bonusHit = true;
      break;
    }
  }
  if (hit === mainCount) return [1, hit, bonusHit];
  if (hit === mainCount - 1 && bonusHit) return [2, hit, true];
  if (hit === mainCount - 1) return [3, hit, false];
  if (hit >= 3) return [mainCount - hit + 2, hit, bonusHit];
  return [null, hit, bonusHit];
}

function pickUnique(pool: number[], count: number): number[] {
  const copy = pool.slice();
  const out: number[] = [];
  for (let i = 0; i < count; i++) {
    const j = Math.floor(Math.random() * copy.length);
    out.push(copy.splice(j, 1)[0]!);
  }
  return out.sort((a, b) => a - b);
}

function drawWinning(game: SimuGameDef): { numbers: number[]; bonuses: number[] } {
  const pool: number[] = [];
  for (let n = game.min_number; n <= game.max_number; n++) pool.push(n);
  const numbers = pickUnique(pool, game.main_count);
  const remain = pool.filter((n) => !numbers.includes(n));
  const bonuses = pickUnique(remain, game.bonus_count);
  return { numbers, bonuses };
}

function gradeAmount(
  grade: number,
  grade1Pool: number,
  grade1Winners: number,
  fixed: Record<number, number>,
): number {
  if (grade === 1) {
    if (grade1Winners <= 0) return 0;
    return Math.floor(grade1Pool / grade1Winners);
  }
  return fixed[grade] || 0;
}

function yieldToUi(): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, 0));
}

const CHUNK = 2500;

export async function runSimu(opts: {
  game: SimuGameDef;
  tickets: number[][];
  randomCount: number;
  carryoverAmount: number | null;
}): Promise<SimuResult> {
  const { game } = opts;
  const randomCount = opts.randomCount;
  const unitPrice = game.unit_price > 0 ? game.unit_price : 200;
  const maxTickets = maxTicketsFor(unitPrice);
  const fixed = game.simu_prizes || {};

  if (randomCount < 0) throw new SimuError("ランダム口数は0以上です");
  if (opts.tickets.length > MAX_HAND_TICKETS) {
    throw new SimuError(`手選びは${MAX_HAND_TICKETS}口までです`);
  }

  const hand: number[][] = [];
  for (const row of opts.tickets) {
    const cleaned: number[] = [];
    const seen = new Set<number>();
    for (const value of row) {
      const n = Number(value);
      if (n < game.min_number || n > game.max_number) {
        throw new SimuError(`数字は${game.min_number}〜${game.max_number}の整数です`);
      }
      if (seen.has(n)) throw new SimuError("同じ数字は1口に1回だけです");
      seen.add(n);
      cleaned.push(n);
    }
    if (cleaned.length !== game.main_count) {
      throw new SimuError(`本数字は${game.main_count}個選んでください`);
    }
    hand.push(cleaned.sort((a, b) => a - b));
  }

  const totalCount = hand.length + randomCount;
  if (totalCount < 1) throw new SimuError("1口以上指定してください");
  if (totalCount > maxTickets) {
    throw new SimuError("口数が多すぎて処理できません。口数を減らして再度お試しください。");
  }

  const win = drawWinning(game);
  const mainSet = new Set(win.numbers);
  const bonusSet = new Set(win.bonuses);
  const pool: number[] = [];
  for (let n = game.min_number; n <= game.max_number; n++) pool.push(n);
  const winnersOnly = totalCount > DETAIL_THRESHOLD;

  const byGradeCounts = new Map<number, number>();
  const handGrades: { numbers: number[]; grade: number | null; matched: number; bonusHit: boolean }[] =
    [];
  for (const numbers of hand) {
    const [grade, matched, bonusHit] = ticketGrade(new Set(numbers), mainSet, bonusSet, game.main_count);
    handGrades.push({ numbers, grade, matched, bonusHit });
    if (grade != null) byGradeCounts.set(grade, (byGradeCounts.get(grade) || 0) + 1);
  }

  const randomGrades: {
    numbers: number[];
    grade: number | null;
    matched: number;
    bonusHit: boolean;
  }[] = [];
  const keepAllRandom = !winnersOnly;
  for (let i = 0; i < randomCount; i++) {
    const numbers = pickUnique(pool, game.main_count);
    const [grade, matched, bonusHit] = ticketGrade(new Set(numbers), mainSet, bonusSet, game.main_count);
    if (grade != null) byGradeCounts.set(grade, (byGradeCounts.get(grade) || 0) + 1);
    if (keepAllRandom || grade != null) {
      randomGrades.push({ numbers, grade, matched, bonusHit });
    }
    if (i > 0 && i % CHUNK === 0) await yieldToUi();
  }

  const carry = opts.carryoverAmount == null ? 0 : Math.max(0, opts.carryoverAmount);
  const grade1Pool = carry + (game.simu_grade1_base || 0);
  const grade1Winners = byGradeCounts.get(1) || 0;

  const byGrade: SimuResult["by_grade"] = [];
  let prizeTotal = 0;
  const grades = [...byGradeCounts.keys()].sort((a, b) => a - b);
  for (const grade of grades) {
    const count = byGradeCounts.get(grade) || 0;
    const per = gradeAmount(grade, grade1Pool, grade1Winners, fixed);
    const total = per * count;
    prizeTotal += total;
    byGrade.push({ grade, count, amount_each: per, amount_total: total });
  }

  const details: SimuDetail[] = [];
  let idx = 0;
  const appendDetail = (
    numbers: number[],
    source: string,
    grade: number | null,
    matched: number,
    bonusHit: boolean,
  ) => {
    idx += 1;
    let amount = 0;
    if (grade != null) amount = gradeAmount(grade, grade1Pool, grade1Winners, fixed);
    if (winnersOnly && grade == null) return;
    details.push({
      index: idx,
      source,
      numbers,
      grade,
      match_count: matched,
      bonus_hit: bonusHit,
      amount,
    });
  };

  for (const row of handGrades) {
    appendDetail(row.numbers, "hand", row.grade, row.matched, row.bonusHit);
  }
  for (const row of randomGrades) {
    appendDetail(row.numbers, "random", row.grade, row.matched, row.bonusHit);
  }

  return {
    game: game.id,
    label: game.label,
    unit_price: unitPrice,
    ticket_count: totalCount,
    hand_count: hand.length,
    random_count: randomCount,
    cost: totalCount * unitPrice,
    prize_total: prizeTotal,
    net: prizeTotal - totalCount * unitPrice,
    carryover_amount: carry,
    grade1_pool: grade1Pool,
    draw: { numbers: win.numbers, bonuses: win.bonuses },
    by_grade: byGrade,
    winners_only: winnersOnly,
    detail_threshold: DETAIL_THRESHOLD,
    details,
    max_tickets: maxTickets,
  };
}
