"""
database.py — Pool asyncpg e helpers de consulta.
=================================================
Conexão única compartilhada por toda a aplicação (lifespan gerencia ciclo de vida).
Sem ORM: queries raw com parâmetros posicionais ($1, $2, ...) do asyncpg.
"""

from __future__ import annotations

import asyncpg

from config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Retorna o pool global, criando-o sob demanda."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.asyncpg_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
    return _pool


async def close_pool() -> None:
    """Fecha o pool (chamado no shutdown da aplicação)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def fetch_all(sql: str, *args) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]


async def fetch_one(sql: str, *args) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return dict(row) if row else None


async def fetch_val(sql: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(sql, *args)
