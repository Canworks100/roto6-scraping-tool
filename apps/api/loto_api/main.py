"""FastAPI 公開 API（読み取り専用）。"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from loto6.analyze import analyze, to_payload  # noqa: E402
from loto6.config import abs_path, load_config  # noqa: E402
from loto6.flash_article import article_or_build, list_articles  # noqa: E402
from loto6.games import get_game, public_game_list  # noqa: E402
from loto6.generate import generate_combos  # noqa: E402
from loto6.scrape import years_ago  # noqa: E402
from loto6.storage import Store, row_to_draw  # noqa: E402

from loto_api.rate_limit import RateLimiter  # noqa: E402

CONFIG = load_config()
DB_PATH = abs_path(CONFIG, "storage.sqlite_path")
PUBLIC = CONFIG.get("public") or {}
SEARCH_LIMITER = RateLimiter(int(PUBLIC.get("search_rate_per_minute", 60)))
GENERATE_LIMITER = RateLimiter(int(PUBLIC.get("generate_rate_per_minute", 20)))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="Loto Public API", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        response.headers["X-Frame-Options"] = "DENY"
        return response


app.add_middleware(SecureHeadersMiddleware)

cors_origins = list(PUBLIC.get("cors_origins") or [])
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


def get_store() -> Iterator[Store]:
    store = Store(DB_PATH)
    try:
        yield store
    finally:
        store.close()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def parse_game(game: str) -> dict[str, Any]:
    try:
        return get_game(CONFIG, game)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未知の種目です") from exc


class GenerateBody(BaseModel):
    tickets: int = Field(default=5, ge=1, le=20)
    mode: Literal["hot", "balanced"] = "hot"
    recent_draws: int | None = Field(default=None, ge=1, le=10000)
    recent_years: int | None = Field(default=None, ge=1, le=50)
    seed: int | None = None

    @field_validator("tickets")
    @classmethod
    def tickets_ok(cls, value: int) -> int:
        return value


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/games")
def games() -> dict[str, Any]:
    return {"games": public_game_list(CONFIG)}


@app.get("/api/{game}/meta")
def game_meta(game: str, store: Annotated[Store, Depends(get_store)]) -> dict[str, Any]:
    g = parse_game(game)
    min_no, max_no, min_date, max_date = store.draw_range(game)
    draw_count = store.count_draws(game)
    return {
        "game": g["id"],
        "label": g["label"],
        "min_number": int(g["min_number"]),
        "max_number": int(g["max_number"]),
        "main_count": int(g["main_count"]),
        "bonus_count": int(g["bonus_count"]),
        "prize_grades": int(g["prize_grades"]),
        "draw_count": draw_count,
        "min_draw_no": min_no,
        "max_draw_no": max_no,
        "min_date": min_date,
        "max_date": max_date,
    }


@app.get("/api/{game}/history")
def history(
    game: str,
    store: Annotated[Store, Depends(get_store)],
    limit: int = Query(default=50, ge=0, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
) -> dict[str, Any]:
    g = parse_game(game)
    main_count = int(g["main_count"])
    total = store.count_draws(game)
    effective = 500 if limit == 0 else limit
    rows = store.load_draws(game=game, limit=effective, offset=offset, newest_first=True)
    items = [row_to_draw(row, main_count) for row in rows]
    return {"game": game, "total": total, "limit": effective, "offset": offset, "items": items}


@app.get("/api/{game}/search")
def search(
    request: Request,
    game: str,
    store: Annotated[Store, Depends(get_store)],
    n: Annotated[list[int] | None, Query()] = None,
    numbers: Annotated[list[int] | None, Query()] = None,
    limit: int = Query(default=40, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
) -> dict[str, Any]:
    if not SEARCH_LIMITER.allow(f"search:{client_ip(request)}"):
        raise HTTPException(status_code=429, detail="リクエストが多すぎます。しばらくしてから再度お試しください。")
    g = parse_game(game)
    min_n = int(g["min_number"])
    max_n = int(g["max_number"])
    main_count = int(g["main_count"])
    raw = list(n or []) + list(numbers or [])
    cleaned: list[int] = []
    for value in raw:
        if value < min_n or value > max_n:
            raise HTTPException(status_code=400, detail=f"数字は{min_n}〜{max_n}の整数です")
        cleaned.append(int(value))
    if not cleaned:
        raise HTTPException(status_code=400, detail="数字を1個以上指定してください")
    if len(set(cleaned)) > main_count:
        raise HTTPException(status_code=400, detail=f"数字は最大{main_count}個までです")
    result = store.search_numbers(cleaned, game=game, main_count=main_count, limit=limit, offset=offset)
    result["game"] = game
    return result


@app.get("/api/{game}/trends")
def trends(
    game: str,
    store: Annotated[Store, Depends(get_store)],
    years: int = Query(default=10, ge=1, le=40),
) -> dict[str, Any]:
    g = parse_game(game)
    start = years_ago(years)
    rows = store.load_draws(start_date=start, game=game)
    cfg = dict(CONFIG)
    cfg["lottery"] = {
        **dict(CONFIG.get("lottery") or {}),
        "max_number": int(g["max_number"]),
        "main_count": int(g["main_count"]),
        "min_number": int(g["min_number"]),
    }
    latest_row = store.latest_draw(game)
    latest = None if latest_row is None else row_to_draw(latest_row, int(g["main_count"]))
    ranks = store.prize_amount_rankings(game, int(g["main_count"]))
    if not rows:
        return {
            "error": "分析できる当せんデータがありません",
            "meta": {"draw_count": 0},
            "game": game,
            "latest": latest,
            "prize_ranks": ranks,
        }
    result = analyze(rows, cfg)
    payload = to_payload(result)
    payload["meta"]["years"] = years
    payload["game"] = game
    payload["latest"] = latest
    payload["prize_ranks"] = ranks
    return payload


@app.get("/api/{game}/latest")
def latest_draw(game: str, store: Annotated[Store, Depends(get_store)]) -> dict[str, Any]:
    g = parse_game(game)
    row = store.latest_draw(game)
    if row is None:
        raise HTTPException(status_code=404, detail="当せんデータがありません")
    return {"game": game, "item": row_to_draw(row, int(g["main_count"]))}


@app.get("/api/{game}/articles")
def articles(
    game: str,
    store: Annotated[Store, Depends(get_store)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
) -> dict[str, Any]:
    g = parse_game(game)
    return list_articles(store, g, limit, offset)


@app.get("/api/{game}/articles/{draw_no}")
def article_detail(
    game: str,
    draw_no: int,
    store: Annotated[Store, Depends(get_store)],
) -> dict[str, Any]:
    g = parse_game(game)
    if draw_no < 1:
        raise HTTPException(status_code=404, detail="記事がありません")
    article = article_or_build(store, g, draw_no)
    if article is None:
        raise HTTPException(status_code=404, detail="記事がありません")
    return article


@app.post("/api/{game}/generate")
def generate(
    request: Request,
    game: str,
    body: GenerateBody,
    store: Annotated[Store, Depends(get_store)],
) -> dict[str, Any]:
    if not GENERATE_LIMITER.allow(f"generate:{client_ip(request)}"):
        raise HTTPException(status_code=429, detail="生成リクエストが多すぎます。しばらくしてから再度お試しください。")
    g = parse_game(game)
    return generate_combos(
        store,
        game=game,
        main_count=int(g["main_count"]),
        max_number=int(g["max_number"]),
        min_number=int(g["min_number"]),
        tickets=body.tickets,
        mode=body.mode,
        recent_draws=body.recent_draws,
        recent_years=body.recent_years,
        seed=body.seed,
    )


@app.exception_handler(404)
async def not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "見つかりません"}, status_code=404)
