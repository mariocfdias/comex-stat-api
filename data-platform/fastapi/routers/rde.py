"""
routers/rde.py — Registros Declaratórios Eletrônicos / IED (2 endpoints).
========================================================================
Substitui: src/rde/rde.controller.ts
PascalCase preservado nas colunas para manter o contrato do BCB.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from database import fetch_all, fetch_one
from models.common import PaginatedResponse
from models.rde import RdeRecord, RdeRecordIed
from responses import success

router = APIRouter(prefix="/rde", tags=["rde"])

_ORDER_MAP = {"asc": "ASC", "desc": "DESC"}


@router.get(
    "/todos-registros",
    summary="Todos os Registros RDE",
    response_model=PaginatedResponse[RdeRecord],
)
async def get_todos_registros(
    skip: int = Query(0, ge=0),
    top: int = Query(100, ge=1, le=10000),
    orderAno: str = Query("desc", description="asc | desc"),
    orderMes: str = Query("desc", description="asc | desc"),
):
    """NestJS: RdeService.getTodosRegistros() — tabela gold_rde_todos_registros."""
    ano_dir = _ORDER_MAP.get(orderAno, "DESC")
    mes_dir = _ORDER_MAP.get(orderMes, "DESC")

    rows = await fetch_all(
        f"""
        SELECT "CodigoRDE", "NomePessoaNacional", "UfPessoaNacional",
               "NomePessoaEstrangeira", "PaisPessoaEstrangeira", "MoedaOperacao",
               "ValorOperacao", "Sistema", "Ocorrencia", "Modalidade", "Ano", "Mes"
        FROM gold.gold_rde_todos_registros
        ORDER BY "Ano" {ano_dir}, "Mes" {mes_dir}
        LIMIT $1 OFFSET $2
        """,
        top, skip,
    )

    total_row = await fetch_one('SELECT COUNT(*) as n FROM gold.gold_rde_todos_registros')
    total = int(total_row["n"]) if total_row else 0

    return success(rows, total=total, skip=skip, top=top)


@router.get(
    "/registros-ied",
    summary="Registros RDE-IED",
    response_model=PaginatedResponse[RdeRecordIed],
)
async def get_registros_ied(
    skip: int = Query(0, ge=0),
    top: int = Query(100, ge=1, le=10000),
    orderAno: str = Query("desc"),
    orderMes: str = Query("desc"),
):
    """NestJS: RdeService.getRegistrosIed() — tabela gold_rde_registros_ied."""
    ano_dir = _ORDER_MAP.get(orderAno, "DESC")
    mes_dir = _ORDER_MAP.get(orderMes, "DESC")

    rows = await fetch_all(
        f"""
        SELECT "CodigoRDE", "NomePessoaNacional", "UfPessoaNacional",
               "NomePessoaEstrangeira", "PaisPessoaEstrangeira", "MoedaOperacao",
               "ValorOperacao", "Sistema", "Ocorrencia", "Modalidade", "Ano", "Mes",
               "CnpjBaseReceptora"
        FROM gold.gold_rde_registros_ied
        ORDER BY "Ano" {ano_dir}, "Mes" {mes_dir}
        LIMIT $1 OFFSET $2
        """,
        top, skip,
    )

    total_row = await fetch_one('SELECT COUNT(*) as n FROM gold.gold_rde_registros_ied')
    total = int(total_row["n"]) if total_row else 0

    return success(rows, total=total, skip=skip, top=top)
