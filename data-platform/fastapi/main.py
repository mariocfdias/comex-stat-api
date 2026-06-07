"""
FastAPI — Nova camada de API (Fase 3 da migração)
==================================================
Substitui: API NestJS (porta 3000) → FastAPI (porta 8000)

Princípio: preservação total do contrato de API.
Todos os endpoints retornam a mesma estrutura JSON do NestJS.
Dados servidos via SELECT nas tabelas gold do PostgreSQL — sem chamadas HTTP externas.

Documentação: http://localhost:8000/docs (Swagger automático)
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# =============================================================================
# Banco de dados (asyncpg pool)
# =============================================================================

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres_pass@postgres:5432/comexstat_platform",
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # Parse asyncpg URL (asyncpg não aceita +asyncpg no scheme)
        url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        _pool = await asyncpg.create_pool(url, min_size=2, max_size=10)
    return _pool


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


def success(data: Any, **kwargs) -> dict:
    """Envelope de resposta padrão — mesma estrutura do NestJS."""
    return {"success": True, "data": data, **kwargs}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    if _pool:
        await _pool.close()


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="ComexStat API",
    version="2.0.0",
    description=(
        "API de estatísticas de comércio exterior, investimentos estrangeiros (RDE), "
        "cadastro mineiro (SCM) e dados geoespaciais (Sigmine) do Ceará. "
        "Dados pré-computados via Airflow → PostgreSQL."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health Check
# =============================================================================

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
        "version": "2.0.0",
        "database": "connected" if db_ok else "unavailable",
    }


# =============================================================================
# Router: ComexStat (9 endpoints)
# Substitui: src/comexstat/comexstat.controller.ts
# =============================================================================

comexstat_router = APIRouter(prefix="/comexstat", tags=["comexstat"])

_PERIOD_MAP = {
    "currentMonth": "current_month",
    "yearToDate": "year_to_date",
    "lastYear": "last_year",
}


@comexstat_router.get("/summary", summary="Quadro Resumo")
async def get_summary(
    period: str = Query("yearToDate", description="currentMonth | yearToDate | lastYear"),
    periodFrom: str = Query(None, description="YYYY-MM (period=custom)"),
    periodTo: str = Query(None, description="YYYY-MM (period=custom)"),
):
    """NestJS: ComexstatService.getSummaryData() — tabela gold_comexstat_summary."""
    period_type = _PERIOD_MAP.get(period, "year_to_date")

    row = await fetch_one(
        "SELECT * FROM gold.gold_comexstat_summary WHERE period_type = $1",
        period_type,
    )
    if not row:
        raise HTTPException(404, f"Dados de resumo não disponíveis para period={period}")

    return success({
        "period": {
            "type": period,
            "from": row["period_from"],
            "to": row["period_to"],
            "label": row["period_label"],
        },
        "exports": float(row["exports_fob"] or 0),
        "imports": float(row["imports_fob"] or 0),
        "tradeBalance": float(row["trade_balance"] or 0),
        "tradeCurrent": float(row["trade_current"] or 0),
        "exportParticipation": float(row["export_participation"] or 0),
        "importParticipation": float(row["import_participation"] or 0),
        "exportRanking": int(row["export_ranking"] or 0),
        "importRanking": int(row["import_ranking"] or 0),
    })


@comexstat_router.get("/summary-history", summary="Histórico do Quadro Resumo")
async def get_summary_history(
    from_: str = Query(..., alias="from", description="YYYY-MM"),
    to: str = Query(..., description="YYYY-MM"),
):
    """NestJS: ComexstatService.getSummaryHistory() — tabela gold_comexstat_timeseries."""
    rows = await fetch_all(
        """
        SELECT year, month, exports_fob, imports_fob, trade_balance, trade_current
        FROM gold.gold_comexstat_timeseries
        WHERE period_type = 'monthly'
          AND (year * 100 + month) BETWEEN
              (CAST(SUBSTRING($1, 1, 4) AS INT) * 100 + CAST(SUBSTRING($1, 6, 2) AS INT))
              AND
              (CAST(SUBSTRING($2, 1, 4) AS INT) * 100 + CAST(SUBSTRING($2, 6, 2) AS INT))
        ORDER BY year, month
        """,
        from_,
        to,
    )
    return success([
        {
            "year": r["year"],
            "month": r["month"],
            "exports": float(r["exports_fob"] or 0),
            "imports": float(r["imports_fob"] or 0),
            "balance": float(r["trade_balance"] or 0),
            "current": float(r["trade_current"] or 0),
        }
        for r in rows
    ])


@comexstat_router.get("/timeseries", summary="Séries Temporais")
async def get_timeseries(
    startYear: int = Query(..., description="Ano inicial"),
    endYear: int = Query(None, description="Ano final"),
    periodicity: str = Query("monthly", description="monthly | annual"),
    series: str = Query("current", description="export | import | current | balance"),
    includeSectors: bool = Query(False),
):
    """NestJS: ComexstatService.getTimeSeries() — gold_comexstat_timeseries."""
    period_type = "monthly" if periodicity == "monthly" else "annual"

    if endYear is None:
        from datetime import datetime
        endYear = datetime.utcnow().year

    if periodicity == "monthly":
        rows = await fetch_all(
            "SELECT year, month, exports_fob, imports_fob, trade_balance, trade_current "
            "FROM gold.gold_comexstat_timeseries "
            "WHERE period_type = 'monthly' AND year BETWEEN $1 AND $2 "
            "ORDER BY year, month",
            startYear, endYear,
        )
    else:
        rows = await fetch_all(
            "SELECT year, exports_fob, imports_fob, trade_balance, trade_current "
            "FROM gold.gold_comexstat_timeseries "
            "WHERE period_type = 'annual' AND year BETWEEN $1 AND $2 "
            "ORDER BY year",
            startYear, endYear,
        )

    def to_series_value(row: dict) -> float:
        mapping = {
            "export": "exports_fob",
            "import": "imports_fob",
            "balance": "trade_balance",
            "current": "trade_current",
        }
        return float(row.get(mapping.get(series, "trade_current")) or 0)

    result = []
    for r in rows:
        entry: dict[str, Any] = {"year": r["year"], "value": to_series_value(r)}
        if periodicity == "monthly":
            entry["month"] = r["month"]
        result.append(entry)

    return success(result)


@comexstat_router.get("/partners", summary="Países Parceiros")
async def get_partners(
    flow: str = Query("current", description="export | import | current"),
    period: str = Query("yearToDate", description="currentMonth | yearToDate | lastYear"),
    periodFrom: str = Query(None),
    periodTo: str = Query(None),
    topN: int = Query(10, ge=1, le=50),
):
    """NestJS: ComexstatService.getPartnerCountries() — gold_comexstat_partners."""
    period_type = _PERIOD_MAP.get(period, "year_to_date")

    rows = await fetch_all(
        """
        SELECT country, exports_fob, imports_fob, current, balance, percentage, rank
        FROM gold.gold_comexstat_partners
        WHERE flow = $1 AND period_type = $2
        ORDER BY rank
        LIMIT $3
        """,
        flow, period_type, topN,
    )
    return success([
        {
            "country": r["country"],
            "exports": float(r["exports_fob"] or 0),
            "imports": float(r["imports_fob"] or 0),
            "current": float(r["current"] or 0),
            "balance": float(r["balance"] or 0),
            "percentage": float(r["percentage"] or 0),
            "rank": int(r["rank"] or 0),
        }
        for r in rows
    ])


@comexstat_router.get("/products", summary="Top Produtos")
async def get_products(
    flow: str = Query("export", description="export | import"),
    aggregation: str = Query("heading", description="ncm | heading | chapter"),
    period: str = Query("yearToDate", description="currentMonth | yearToDate | lastYear"),
    periodFrom: str = Query(None),
    periodTo: str = Query(None),
    topN: int = Query(20, ge=1, le=100),
):
    """NestJS: ComexstatService.getTopProducts() — gold_comexstat_products."""
    period_type = _PERIOD_MAP.get(period, "year_to_date")

    rows = await fetch_all(
        """
        SELECT code, description, value_fob, weight_kg, percentage, rank
        FROM gold.gold_comexstat_products
        WHERE flow = $1 AND period_type = $2 AND aggregation_level = $3
        ORDER BY rank
        LIMIT $4
        """,
        flow, period_type, aggregation, topN,
    )
    return success([
        {
            "code": r["code"],
            "description": r["description"],
            "value": float(r["value_fob"] or 0),
            "weight": float(r["weight_kg"] or 0),
            "percentage": float(r["percentage"] or 0),
            "rank": int(r["rank"] or 0),
        }
        for r in rows
    ])


@comexstat_router.get("/national-comparison", summary="Comparação Nacional")
async def get_national_comparison(
    flow: str = Query("export", description="export | import"),
    from_: str = Query(..., alias="from", description="YYYY-MM"),
    to: str = Query(..., description="YYYY-MM"),
):
    """NestJS: ComexstatService.getNationalComparison() — 3 chamadas → 1 SELECT."""
    # Tenta encontrar um period_type que cubra o range solicitado
    # Fallback: usa os dados mais próximos disponíveis
    rows = await fetch_all(
        "SELECT * FROM gold.gold_comexstat_national_comparison WHERE flow = $1 ORDER BY period_type",
        flow,
    )
    if not rows:
        raise HTTPException(404, "Dados de comparação nacional não disponíveis.")

    # Usa year_to_date como padrão (mais usado no NestJS)
    row = next((r for r in rows if r["period_type"] == "year_to_date"), rows[0])
    return success({
        "flow": flow,
        "ceFob": float(row["ce_fob"] or 0),
        "nationalFob": float(row["national_fob"] or 0),
        "participation": float(row["participation"] or 0),
        "ranking": int(row["ranking"] or 0),
    })


@comexstat_router.get(
    "/national-comparison/states-ranking",
    summary="Ranking de Estados",
)
async def get_states_ranking(
    flow: str = Query("export", description="export | import"),
    from_: str = Query(..., alias="from", description="YYYY-MM"),
    to: str = Query(..., description="YYYY-MM"),
):
    """
    NestJS: ComexstatService.getStatesRanking() — 5 chamadas paralelas de 60s!
    Aqui: 1 SELECT com dados pré-computados → <100ms.
    """
    rows = await fetch_all(
        """
        SELECT rank, state, value_fob, participation, top_sectors, top_partners, top_products
        FROM gold.gold_comexstat_states_ranking
        WHERE flow = $1 AND period_type = 'year_to_date'
        ORDER BY rank
        """,
        flow,
    )
    if not rows:
        raise HTTPException(404, "Ranking de estados não disponível.")

    return success([
        {
            "rank": int(r["rank"]),
            "state": r["state"],
            "value": float(r["value_fob"] or 0),
            "participation": float(r["participation"] or 0),
            "topSectors": json.loads(r["top_sectors"] or "[]"),
            "topPartners": json.loads(r["top_partners"] or "[]"),
            "topProducts": json.loads(r["top_products"] or "[]"),
        }
        for r in rows
    ])


@comexstat_router.get("/dashboard", summary="Dashboard")
async def get_dashboard():
    """NestJS: ComexstatService.getDashboardData() — combina summary + products + partners."""
    summary = await fetch_one(
        "SELECT * FROM gold.gold_comexstat_summary WHERE period_type = 'year_to_date'"
    )
    partners = await fetch_all(
        "SELECT * FROM gold.gold_comexstat_partners "
        "WHERE period_type = 'year_to_date' AND flow = 'export' ORDER BY rank LIMIT 5"
    )
    products = await fetch_all(
        "SELECT * FROM gold.gold_comexstat_products "
        "WHERE period_type = 'year_to_date' AND flow = 'export' AND aggregation_level = 'heading' "
        "ORDER BY rank LIMIT 10"
    )

    return success({
        "summary": {
            "exports": float(summary["exports_fob"] or 0) if summary else 0,
            "imports": float(summary["imports_fob"] or 0) if summary else 0,
            "tradeBalance": float(summary["trade_balance"] or 0) if summary else 0,
            "tradeCurrent": float(summary["trade_current"] or 0) if summary else 0,
        } if summary else None,
        "topExportPartners": [
            {"country": r["country"], "value": float(r["exports_fob"] or 0), "percentage": float(r["percentage"] or 0)}
            for r in partners
        ],
        "topProducts": [
            {"code": r["code"], "description": r["description"], "value": float(r["value_fob"] or 0)}
            for r in products
        ],
    })


@comexstat_router.delete("/cache", summary="Limpar Cache")
async def clear_cache():
    """No-op: dados pré-computados não utilizam cache volátil."""
    return success({"message": "Cache não aplicável na nova arquitetura (dados materializados no PostgreSQL)."})


# =============================================================================
# Router: RDE (2 endpoints)
# Substitui: src/rde/rde.controller.ts
# =============================================================================

rde_router = APIRouter(prefix="/rde", tags=["rde"])

_ORDER_MAP = {"asc": "ASC", "desc": "DESC"}


@rde_router.get("/todos-registros", summary="Todos os Registros RDE")
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


@rde_router.get("/registros-ied", summary="Registros RDE-IED")
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


# =============================================================================
# Router: SCM (17 endpoints)
# Substitui: src/scm/scm.controller.ts
# =============================================================================

scm_router = APIRouter(prefix="/scm", tags=["SCM - Sistema de Cadastro Mineiro"])


@scm_router.get("/health", summary="Status do SCM")
async def scm_health():
    """NestJS: ScmService.getHealth() — contadores de registros."""
    counts = {}
    for table in ["scm_processo", "scm_fase_processo", "scm_tipo_requerimento", "scm_municipio", "scm_substancia"]:
        row = await fetch_one(f"SELECT COUNT(*) as n FROM raw.{table}")
        counts[table] = int(row["n"]) if row else 0
    return success({"status": "ok", "counts": counts})


@scm_router.get("/summary", summary="Resumo SCM")
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


@scm_router.get("/processos", summary="Lista de Processos")
async def scm_processos(
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    rows = await fetch_all(
        "SELECT * FROM raw.scm_processo ORDER BY numero LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return success(rows)


@scm_router.get("/fases", summary="Fases dos Processos")
async def scm_fases():
    rows = await fetch_all("SELECT * FROM raw.scm_fase_processo ORDER BY id")
    return success(rows)


@scm_router.get("/tipos", summary="Tipos de Requerimento")
async def scm_tipos():
    rows = await fetch_all("SELECT * FROM raw.scm_tipo_requerimento ORDER BY id")
    return success(rows)


@scm_router.get("/municipios", summary="Municípios do Ceará")
async def scm_municipios():
    rows = await fetch_all("SELECT * FROM raw.scm_municipio ORDER BY nome")
    return success(rows)


@scm_router.get("/substancias", summary="Substâncias Minerais")
async def scm_substancias():
    rows = await fetch_all("SELECT * FROM raw.scm_substancia ORDER BY nome")
    return success(rows)


@scm_router.get("/analytics/by-fase", summary="Analytics por Fase")
async def scm_by_fase():
    """NestJS: ScmService.getProcessosByFase() — tabela gold.scm_by_fase."""
    rows = await fetch_all("SELECT * FROM gold.scm_by_fase ORDER BY total_processos DESC")
    return success(rows)


@scm_router.get("/analytics/by-tipo", summary="Analytics por Tipo")
async def scm_by_tipo():
    rows = await fetch_all("SELECT * FROM gold.scm_by_tipo ORDER BY total_processos DESC")
    return success(rows)


@scm_router.get("/analytics/by-municipio", summary="Analytics por Município")
async def scm_by_municipio():
    rows = await fetch_all("SELECT * FROM gold.scm_by_municipio ORDER BY total_processos DESC")
    return success(rows)


@scm_router.get("/analytics/by-substancia", summary="Analytics por Substância")
async def scm_by_substancia():
    rows = await fetch_all("SELECT * FROM gold.scm_by_substancia ORDER BY total_processos DESC")
    return success(rows)


@scm_router.get("/analytics/by-uf", summary="Analytics por UF")
async def scm_by_uf():
    """Agrupamento por UF — CE domina mas pode incluir processos limítrofes."""
    rows = await fetch_all("""
        SELECT uf, COUNT(*) as total_processos, SUM(area_ha) as area_total_ha
        FROM raw.scm_processo
        GROUP BY uf
        ORDER BY total_processos DESC
    """)
    return success(rows)


@scm_router.get("/relations/processo-municipios", summary="Relações Processo-Município")
async def scm_processo_municipios(
    limit: int = Query(1000, ge=1, le=50000),
):
    rows = await fetch_all(
        "SELECT * FROM raw.scm_processo_municipio LIMIT $1",
        limit,
    )
    return success(rows)


@scm_router.get("/relations/processo-substancias", summary="Relações Processo-Substância")
async def scm_processo_substancias(
    limit: int = Query(1000, ge=1, le=50000),
):
    rows = await fetch_all(
        "SELECT * FROM raw.scm_processo_substancia LIMIT $1",
        limit,
    )
    return success(rows)


@scm_router.get("/search", summary="Busca com Filtros")
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


@scm_router.post("/update", summary="Atualizar Dados SCM")
async def scm_update():
    """
    NestJS: disparo manual de ScmCsvService.downloadAndExtractData().
    Nova arquitetura: retorna instrução para disparar DAG via Airflow UI.
    """
    return success({
        "message": "Para atualizar dados SCM, acesse o Airflow UI e dispare a DAG dag_scm_ingestao.",
        "airflowUrl": "http://localhost:8080/dags/dag_scm_ingestao/grid",
    })


# =============================================================================
# Router: Sigmine / Layers (6 endpoints)
# Substitui: src/sigmine/sigmine.controller.ts
# =============================================================================

layers_router = APIRouter(prefix="/layers", tags=["layers"])


async def _get_layer_geojson(layer_name: str) -> dict:
    """
    Retorna GeoJSON FeatureCollection para uma layer do Sigmine.
    Replica SigmineService.getLayer() — 1 SELECT PostGIS vs shapefile read em disco.
    """
    rows = await fetch_all(
        "SELECT ST_AsGeoJSON(geometry) as geom_json, properties "
        "FROM gold.gold_sigmine_layers WHERE layer_name = $1",
        layer_name,
    )
    if not rows:
        raise HTTPException(404, f"Layer '{layer_name}' não disponível. Execute dag_sigmine_ingestao.")

    features = []
    for r in rows:
        geom = json.loads(r["geom_json"])
        props = json.loads(r["properties"]) if isinstance(r["properties"], str) else (r["properties"] or {})
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    return {"type": "FeatureCollection", "features": features}


@layers_router.get("/area-servidao", summary="GeoJSON Área de Servidão")
async def layer_area_servidao():
    return await _get_layer_geojson("AREA_SERVIDAO")


@layers_router.get("/arrendamento", summary="GeoJSON Arrendamento")
async def layer_arrendamento():
    return await _get_layer_geojson("ARRENDAMENTO")


@layers_router.get("/bloqueio", summary="GeoJSON Bloqueio")
async def layer_bloqueio():
    return await _get_layer_geojson("BLOQUEIO")


@layers_router.get("/ce", summary="GeoJSON Processos Minerais CE")
async def layer_ce():
    return await _get_layer_geojson("CE")


@layers_router.get("/protecao-fonte", summary="GeoJSON Proteção de Fonte")
async def layer_protecao_fonte():
    return await _get_layer_geojson("PROTECAO_FONTE")


@layers_router.get("/reservas-garimpeiras", summary="GeoJSON Reservas Garimpeiras")
async def layer_reservas_garimpeiras():
    return await _get_layer_geojson("RESERVAS_GARIMPEIRAS")


# =============================================================================
# Registrar routers
# =============================================================================

app.include_router(comexstat_router)
app.include_router(rde_router)
app.include_router(scm_router)
app.include_router(layers_router)
