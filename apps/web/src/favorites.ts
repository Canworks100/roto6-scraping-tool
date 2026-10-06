const COOKIE = "loto_fav";
const MAX_AGE = 60 * 60 * 24 * 400;

type Store = Record<string, number[]>;

function readCookie(): string | null {
  const prefix = `${COOKIE}=`;
  const hit = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  if (!hit) return null;
  return hit.slice(prefix.length);
}

function parseStore(raw: string | null): Store {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(decodeURIComponent(raw)) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: Store = {};
    for (const [game, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (!Array.isArray(value)) continue;
      out[game] = [
        ...new Set(
          value
            .map((n) => Number(n))
            .filter((n) => Number.isInteger(n) && n > 0 && n < 100),
        ),
      ].sort((a, b) => a - b);
    }
    return out;
  } catch {
    return {};
  }
}

function writeStore(store: Store): void {
  const value = encodeURIComponent(JSON.stringify(store));
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${COOKIE}=${value}; Path=/; Max-Age=${MAX_AGE}; SameSite=Lax${secure}`;
}

export function loadFavorites(game: string): number[] {
  return parseStore(readCookie())[game] ?? [];
}

export function saveFavorites(game: string, numbers: number[]): void {
  const store = parseStore(readCookie());
  store[game] = [...new Set(numbers.filter((n) => Number.isInteger(n) && n > 0))].sort((a, b) => a - b);
  if (!store[game].length) delete store[game];
  writeStore(store);
}
