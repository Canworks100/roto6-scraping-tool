export type GameInfo = {
  id: string;
  label: string;
  min_number: number;
  max_number: number;
  main_count: number;
  bonus_count: number;
  prize_grades: number;
  ready: boolean;
};

export type DrawItem = {
  game: string;
  draw_no: number;
  draw_date: string;
  numbers: number[];
  bonus: number;
  bonus2: number | null;
  matched?: number[];
  match_count?: number;
  prizes?: { grade: number; count: number | null; amount: number | null }[];
  sales_amount?: number | null;
  carryover_amount?: number | null;
};

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || "通信に失敗しました");
  }
  return data as T;
}

export function listGames() {
  return getJson<{ games: GameInfo[] }>("/api/games");
}

export function gameMeta(game: string) {
  return getJson<{
    game: string;
    label: string;
    min_number: number;
    max_number: number;
    main_count: number;
    bonus_count: number;
    prize_grades: number;
    draw_count: number;
    min_draw_no: number | null;
    max_draw_no: number | null;
    min_date: string | null;
    max_date: string | null;
  }>(`/api/${game}/meta`);
}

export function history(game: string, limit = 50, offset = 0) {
  return getJson<{ total: number; items: DrawItem[]; limit: number; offset: number }>(
    `/api/${game}/history?limit=${limit}&offset=${offset}`,
  );
}

export function search(game: string, numbers: number[], limit = 40, offset = 0) {
  const qs = numbers.map((n) => `n=${n}`).join("&");
  return getJson<{
    numbers: number[];
    total: number;
    items: DrawItem[];
    number_stats: { number: number; count: number; last_draw_no: number | null; last_draw_date: string | null }[];
    exact_main: boolean;
  }>(`/api/${game}/search?${qs}&limit=${limit}&offset=${offset}`);
}

export type PrizeRankItem = {
  amount: number;
  count: number | null;
  draw_no: number;
  draw_date: string;
  numbers: number[];
  bonus: number;
  bonus2: number | null;
};

export type PrizeRankGroup = {
  rank: number;
  amount: number;
  draw_count: number;
  draws: PrizeRankItem[];
};

export function trends(game: string, years = 10) {
  return getJson<{
    game: string;
    meta: Record<string, unknown>;
    frequency: {
      number: number;
      count: number;
      rank: number;
      probability: number;
      last_draw_no?: number | null;
      last_draw_date?: string | null;
      draws_since_last?: number;
    }[];
    summary_text?: string;
    error?: string;
    latest?: DrawItem | null;
    prize_ranks?: Record<string, { high: PrizeRankGroup[]; low: PrizeRankGroup[] }>;
  }>(`/api/${game}/trends?years=${years}`);
}

export function latest(game: string) {
  return getJson<{ game: string; item: DrawItem }>(`/api/${game}/latest`);
}

export type FlashListItem = {
  draw_no: number;
  draw_date: string;
  title: string;
  lead: string;
  numbers: number[];
  bonus: number;
  bonus2: number | null;
};

export type FlashArticle = {
  game: string;
  label: string;
  draw_no: number;
  draw_date: string;
  title: string;
  lead: string;
  carry_text: string;
  observations: string[];
  prize_grades: number;
  item: DrawItem;
  prev_draw_no: number | null;
  next_draw_no: number | null;
};

export function articles(game: string, limit = 20, offset = 0) {
  return getJson<{ total: number; items: FlashListItem[]; limit: number; offset: number }>(
    `/api/${game}/articles?limit=${limit}&offset=${offset}`,
  );
}

export function article(game: string, drawNo: number) {
  return getJson<FlashArticle>(`/api/${game}/articles/${drawNo}`);
}

export function generate(
  game: string,
  body: {
    tickets: number;
    mode: "hot" | "balanced";
    recent_draws?: number | null;
    recent_years?: number | null;
  },
) {
  return getJson<{
    combos: { index: number; numbers: number[] }[];
    weights_summary: { number: number; count: number; weight: number }[];
    disclaimer: string;
    warnings: string[];
    draw_count: number;
    mode: string;
  }>(`/api/${game}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
