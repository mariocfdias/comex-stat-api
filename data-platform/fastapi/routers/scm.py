"""
routers/scm.py — Sistema de Cadastro Mineiro (17 endpoints).
============================================================
Substitui: src/scm/scm.controller.ts
Endpoints de listagem servem linhas cruas (raw.*); analytics vêm de gold.scm_*.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from config import settings
from database import fetch_all, fetch_one
from responses import success

router = APIRouter(prefix="/scm", tags=["SCM - Sistema de Cadastro Mineiro"])


@router.get("/health", summary="Status do SCM")
async def scm_health():
    """NestJS: ScmService.getHealth() — contadores de registros."""
    counts = {}
    for table in ["scm_processo", "scm_fase_processo", "scm_tipo_requerimento", "scm_municipio", "scm_substancia"]:
        row = await fetch_one(f"SELECT COUNT(*) as n FROM raw.{table}")
        counts[table] = int(row["n"]) if row else 0
    return success({"status": "ok", "counts": counts})


@router.get("/summary", summary="Resumo SCM")
async def scm_summary():
    """Contagens gerais de processos SCM do Ceará."""
    row = await fetch_one("""
        SELECT
            COUNT(*) as total_processos,
            COUNT(DISTINCT fase_id) as total_fases,
            COUNT(DISTINCT tipo_id) as total_tipos,
            SUM(area_ha) as area_total_ha
        FROM raw.scm_processo
    """)
    return success(dict(row) if row else {})


@router.get("/processos", summary="Lista de Processos")
async def scm_processos(
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    rows = await fetch_all(
        "SELECT * FROM raw.scm_processo ORDER BY numero LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return success(rows)


@router.get("/fases", summary="Fases dos Processos")
async def scm_fases():
    rows = await fetch_all("SELECT * FROM raw.scm_fase_processo ORDER BY id")
    return success(rows)


@router.get("/tipos", summary="Tipos de Requerimento")
async def scm_tipos():
    rows = await fetch_all("SELECT * FROM raw.scm_tipo_requerimento ORDER BY id")
    return success(rows)


@router.get("/municipios", summary="Municípios do Ceará")
async def scm_municipios():
    rows = await fetch_all("SELECT * FROM raw.scm_municipio ORDER BY nome")
    return success(rows)


@router.get("/substancias", summary="Substâncias Minerais")
async def scm_substancias():
    rows = await fetch_all("SELECT * FROM raw.scm_substancia ORDER BY nome")
    return success(rows)


@router.get("/analytics/by-fase", summary="Analytics por Fase")
async def scm_by_fase():
    """NestJS: ScmService.getProcessosByFase() — tabela gold.scm_by_fase."""
    rows = await fetch_all("SELECT * FROM gold.scm_by_fase ORDER BY total_processos DESC")
    return success(rows)


@router.get("/analytics/by-tipo", summary="Analytics por Tipo")
async def scm_by_tipo():
    rows = await fetch_all("SELECT * FROM gold.scm_by_tipo ORDER BY total_processos DESC")
    return success(rows)


@router.get("/analytics/by-municipio", summary="Analytics por Município")
async def scm_by_municipio():
    rows = await fetch_all("SELECT * FROM gold.scm_by_municipio ORDER BY total_processos DESC")
    return success(rows)


@router.get("/analytics/by-substancia", summary="Analytics por Substância")
async def scm_by_substancia():
    rows = await fetch_all("SELECT * FROM gold.scm_by_substancia ORDER BY total_processos DESC")
    return success(rows)


@router.get("/analytics/by-uf", summary="Analytics por UF")
async def scm_by_uf():
    """Agrupamento por UF — CE domina mas pode incluir processos limítrofes."""
    rows = await fetch_all("""
        SELECT uf, COUNT(*) as total_processos, SUM(area_ha) as area_total_ha
        FROM raw.scm_processo
        GROUP BY uf
        ORDER BY total_processos DESC
    """)
    return success(rows)


@router.get("/relations/processo-municipios", summary="Relações Processo-Município")
async def scm_processo_municipios(
    limit: int = Query(1000, ge=1, le=50000),
):
    rows = await fetch_all(
        "SELECT * FROM raw.scm_processo_municipio LIMIT $1",
        limit,
    )
    return success(rows)


@router.get("/relations/processo-substancias", summary="Relações Processo-Substância")
async def scm_processo_substancias(
    limit: int = Query(1000, ge=1, le=50000),
):
    rows = await fetch_all(
        "SELECT * FROM raw.scm_processo_substancia LIMIT $1",
        limit,
    )
    return success(rows)


@router.get("/search", summary="Busca com Filtros")
async def scm_search(
    q: str = Query(None, description="Termo de busca"),
    fase: int = Query(None),
    tipo: int = Query(None),
    municipio: int = Query(None),
    substancia: int = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    conditions = ["1=1"]
    params: list = []
    idx = 1

    if q:
        conditions.append(f"(numero ILIKE ${idx} OR nome ILIKE ${idx})")
        params.append(f"%{q}%")
        idx += 1
    if fase is not None:
        conditions.append(f"fase_id = ${idx}")
        params.append(fase)
        idx += 1
    if tipo is not None:
        conditions.append(f"tipo_id = ${idx}")
        params.append(tipo)
        idx += 1

    where = " AND ".join(conditions)
    params.append(limit)
    rows = await fetch_all(
        f"SELECT * FROM raw.scm_processo WHERE {where} LIMIT ${idx}",
        *params,
    )
    return success(rows)


@router.post("/update", summary="Atualizar Dados SCM")
async def scm_update():
    """
    NestJS: disparo manual de ScmCsvService.downloadAndExtractData().
    Nova arquitetura: retorna instrução para disparar DAG via Airflow UI.
    """
    return success({
        "message": "Para atualizar dados SCM, acesse o Airflow UI e dispare a DAG dag_scm_ingestao.",
        "airflowUrl": f"{settings.airflow_url}/dags/dag_scm_ingestao/grid",
    })
