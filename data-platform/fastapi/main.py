"""
FastAPI — Nova camada de API (Fase 3 da migração)
==================================================
Substitui: API NestJS (porta 3000) → FastAPI (porta 8000)

Princípio: preservação total do contrato de API.
Todos os endpoints retornam a mesma estrutura JSON do NestJS.
Dados servidos via SELECT nas tabelas gold do PostgreSQL — sem chamadas HTTP externas.

Estrutura (Fase 3 — refatoração):
  config.py     → configurações (pydantic-settings)
  database.py   → pool asyncpg + helpers de consulta
  responses.py  → envelope de resposta padrão
  models/       → DTOs Pydantic (aliases camelCase / PascalCase)
  routers/      → um módulo por domínio (comexstat, rde, scm, layers)

Documentação: http://localhost:8000/docs (Swagger automático)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import close_pool, get_pool
from routers import comexstat, layers, rde, scm


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)


@app.get("/health", tags=["health"])
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "version": settings.app_version,
        "database": "connected" if db_ok else "unavailable",
    }


app.include_router(comexstat.router)
app.include_router(rde.router)
app.include_router(scm.router)
app.include_router(layers.router)
