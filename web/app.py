import os
import secrets
import string
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

DB_DSN = os.environ["DB_DSN"]
REDIS_URL = os.environ["REDIS_URL"]
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")
CACHE_TTL = 3600  # 秒
ALPHABET = string.ascii_letters + string.digits


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
    app.state.cache = redis.from_url(REDIS_URL, decode_responses=True)
    yield
    await app.state.db.close()
    await app.state.cache.aclose()


app = FastAPI(title="URL Shortener", lifespan=lifespan)


class CreateLink(BaseModel):
    url: HttpUrl


@app.get("/healthz")
async def healthz():
    await app.state.db.fetchval("SELECT 1")
    await app.state.cache.ping()
    return {"status": "ok"}


@app.post("/links", status_code=201)
async def create_link(body: CreateLink):
    for _ in range(5):  # 碰撞重試
        code = "".join(secrets.choice(ALPHABET) for _ in range(7))
        try:
            await app.state.db.execute(
                "INSERT INTO links (code, target_url) VALUES ($1, $2)",
                code, str(body.url),
            )
            break
        except asyncpg.UniqueViolationError:
            continue
    else:
        raise HTTPException(500, "無法產生唯一短碼")
    return {"code": code, "short_url": f"{BASE_URL}/{code}", "target_url": str(body.url)}


@app.get("/{code}")
async def redirect(code: str):
    cache_key = f"link:{code}"

    # 1. 先查 Redis（cache hit）
    target = await app.state.cache.get(cache_key)

    # 2. 沒有就查 PostgreSQL，再回填快取
    if target is None:
        target = await app.state.db.fetchval(
            "SELECT target_url FROM links WHERE code = $1", code
        )
        if target is None:
            raise HTTPException(404, "短碼不存在")
        await app.state.cache.set(cache_key, target, ex=CACHE_TTL)

    # 3. 點擊數用 Redis 累加，不每次寫 DB
    await app.state.cache.incr(f"hits:{code}")
    return RedirectResponse(target, status_code=302)


@app.get("/links/{code}/stats")
async def stats(code: str):
    row = await app.state.db.fetchrow(
        "SELECT code, target_url, hits, created_at FROM links WHERE code = $1", code
    )
    if row is None:
        raise HTTPException(404, "短碼不存在")
    pending = int(await app.state.cache.get(f"hits:{code}") or 0)
    return {**dict(row), "hits": row["hits"] + pending}
