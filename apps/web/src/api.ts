export type GameInfo = {
  id: string;
  label: string;
  min_number: number;
  max_number: number;
  main_count: number;
  bonus_count: number;
  prize_grades: number;
  unit_price?: number;
  simu_grade1_base?: number;
  simu_prizes?: Record<number, number>;
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
    const detail = data.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("、")
          : data.error || "通信に失敗しました";
    throw new Error(msg);
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

export type HistoryQuery = {
  limit?: number;
  offset?: number;
  period?: string;
  sort?: "newest" | "oldest";
  from?: string;
  to?: string;
};

export function history(game: string, opts: HistoryQuery | number = 50, offset = 0) {
  const q: HistoryQuery =
    typeof opts === "number" ? { limit: opts, offset } : { limit: 50, offset: 0, ...opts };
  const params = new URLSearchParams();
  params.set("limit", String(q.limit ?? 50));
  params.set("offset", String(q.offset ?? 0));
  if (q.period && q.period !== "all") params.set("period", q.period);
  if (q.sort && q.sort !== "newest") params.set("sort", q.sort);
  if (q.from) params.set("from", q.from);
  if (q.to) params.set("to", q.to);
  return getJson<{
    total: number;
    items: DrawItem[];
    limit: number;
    offset: number;
    period?: string;
    sort?: string;
    from?: string | null;
    to?: string | null;
  }>(`/api/${game}/history?${params}`);
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

export type ComboPayload = {
  game?: string;
  period: string;
  numbers: number[];
  draw_count: number;
  prizes: { grade: number; ways: number; total: number; one_in: number | null }[];
  match_hist: { match_count: number; draws: number }[];
  exact_count: number;
  exact: { draw_no: number; draw_date: string; match_count: number; prize1_amount?: number | null }[];
  samples: { draw_no: number; draw_date: string; match_count: number; numbers: number[] }[];
  numbers_stats: {
    number: number;
    count: number;
    expected: number;
    vs_expected: number;
    last_draw_no: number | null;
    last_draw_date: string | null;
  }[];
  shape: {
    even_count: number;
    odd_count: number;
    same_odd_even_draws: number;
    sum: number;
    sum_bin: string;
    same_sum_bin_draws: number;
    adjacent_count: number;
    longest_run: number;
    same_adjacent_draws: number;
    bands: { label: string; count: number }[];
    mean_sum?: number;
  };
  diagnosis?: {
    verdict: string;
    level?: number;
    summary: string;
    points: { label: string; tone: string; text: string }[];
  };
  hits?: ComboHit[];
  whatif?: {
    hit_count: number;
    prize_total: number;
    unknown_amount: number;
    unit_price: number;
    cost: number;
    by_grade: { grade: number; draws: number; amount: number }[];
  };
};

export type ComboHit = {
  draw_no: number;
  draw_date: string;
  grade: number;
  match_count: number;
  bonus_hit: boolean;
  numbers: number[];
  bonus: number | null;
  bonus2: number | null;
  amount: number | null;
};

export function combo(game: string, numbers: number[], period = "all") {
  const qs = numbers.map((n) => `n=${n}`).join("&");
  return getJson<ComboPayload>(`/api/${game}/combo?${qs}&period=${encodeURIComponent(period)}`);
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

export type FreqRow = {
  number: number;
  count: number;
  rank: number;
  probability: number;
  last_draw_no?: number | null;
  last_draw_date?: string | null;
  draws_since_last?: number;
  bonus_count?: number;
  main_plus_bonus?: number;
  expected_main?: number;
  expected_bonus?: number;
  max_rest?: number;
  max_streak?: number;
  bonus_draws_since_last?: number;
  bonus_last_draw_date?: string | null;
  bonus_max_rest?: number;
  bonus_max_streak?: number;
};

export type PairRow = {
  number_a: number;
  number_b: number;
  number_c?: number;
  count: number;
  probability: number;
  expected?: number;
  last_draw_no?: number;
  last_draw_date?: string;
  others?: number[];
};

export type TrendsPayload = {
  game: string;
  period?: string;
  period_label?: string;
  meta: {
    draw_count?: number;
    start_draw?: number;
    end_draw?: number;
    start_date?: string;
    end_date?: string;
    years?: number;
    game_draw_count?: number;
  };
  frequency: FreqRow[];
  pairs?: PairRow[];
  pairs_high?: PairRow[];
  pairs_low?: PairRow[];
  triples?: PairRow[];
  triples_high?: PairRow[];
  triples_low?: PairRow[];
  shape?: {
    odd_even: { even_count: number; odd_count: number; draws: number; rate: number }[];
    sum_summary: { mean: number; median: number; min: number; max: number; mode: number };
    sum_bins: { label: string; draws: number }[];
    consecutive_pairs: { adjacent_count: number; draws: number; rate: number }[];
    consecutive_run: { run_length: number; draws: number; rate: number }[];
    last_digit: { digit: number; count: number; expected: number }[];
    span: { summary: { mean: number; min: number; max: number }; items: { span: number; draws: number }[] };
    bands: { id: string; label: string; min: number; max: number; count: number }[];
    band_mix: Record<string, number>;
    weekday: { weekday: number; draws: number }[];
  };
  follow?: {
    summary: { key: string; draws: number; rate: number }[];
    by_number: {
      number: number;
      without_prev: number;
      with_prev: number;
      with_prev_rate: number;
      streak2: number;
      streak3: number;
    }[];
    highlights: {
      with_prev_high: { number: number; value: number }[];
      streak2_high: { number: number; value: number }[];
      rate_high: { number: number; value: number }[];
      rate_low: { number: number; value: number }[];
    };
  };
  summary_text?: string;
  error?: string;
  latest?: DrawItem | null;
  prize_ranks?: Record<string, { high: PrizeRankGroup[]; low: PrizeRankGroup[] }>;
};

export function trends(game: string, period = "all") {
  return getJson<TrendsPayload>(`/api/${game}/trends?period=${encodeURIComponent(period)}`);
}

export function numberDetail(game: string, n: number, period = "all") {
  return getJson<{
    game: string;
    period: string;
    number: number;
    frequency: FreqRow;
    mates: { number: number; count: number; probability: number }[];
    total: number;
    items: DrawItem[];
    meta?: TrendsPayload["meta"];
  }>(`/api/${game}/numbers/${n}?period=${encodeURIComponent(period)}`);
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

export type WeekPick = {
  game: string;
  label: string;
  latest: DrawItem;
  next_draw_no: number;
  next_draw_date: string;
  next: number[];
  previous: number[];
  matched: number[];
  match_count: number;
};

export function weekPick(game: string) {
  return getJson<WeekPick>(`/api/${game}/week-pick`);
}

export function generate(
  game: string,
  body: {
    tickets: number;
    mode: "hot" | "balanced";
    recent_draws?: number | null;
    recent_years?: number | null;
    seed?: number | null;
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

