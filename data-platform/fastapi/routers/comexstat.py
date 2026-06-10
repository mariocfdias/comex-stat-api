"""
routers/comexstat.py — Endpoints de comércio exterior (9 endpoints).
====================================================================
Substitui: src/comexstat/comexstat.controller.ts
Dados servidos por SELECT nas tabelas gold (pré-computadas via Airflow).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from database import fetch_all, fetch_one
from models.comexstat import (
    Dashboard,
    NationalComparison,
    Partner,
    Product,
    StateRanking,
    Summary,
    SummaryHistoryPoint,
    TimeSeriesPoint,
)
from models.common import SuccessResponse
from responses import success

router = APIRouter(prefix="/comexstat", tags=["comexstat"])

_PERIOD_MAP = {
    "currentMonth": "current_month",
    "yearToDate": "year_to_date",
    "lastYear": "last_year",
}


@router.get("/summary", summary="Quadro Resumo", response_model=SuccessResponse[Summary])
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


@router.get(
    "/summary-history",
    summary="Histórico do Quadro Resumo",
    response_model=SuccessResponse[list[SummaryHistoryPoint]],
)
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


@router.get(
    "/timeseries",
    summary="Séries Temporais",
    response_model=SuccessResponse[list[TimeSeriesPoint]],
    response_model_exclude_none=True,  # omite 'month' no modo anual (paridade com NestJS)
)
async def get_timeseries(
    startYear: int = Query(..., description="Ano inicial"),
    endYear: int = Query(None, description="Ano final"),
    periodicity: str = Query("monthly", description="monthly | annual"),
    series: str = Query("current", description="export | import | current | balance"),
    includeSectors: bool = Query(False),
):
    """NestJS: ComexstatService.getTimeSeries() — gold_comexstat_timeseries."""
    if endYear is None:
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


@router.get(
    "/partners",
    summary="Países Parceiros",
    response_model=SuccessResponse[list[Partner]],
)
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


@router.get(
    "/products",
    summary="Top Produtos",
    response_model=SuccessResponse[list[Product]],
)
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


@router.get(
    "/national-comparison",
    summary="Comparação Nacional",
    response_model=SuccessResponse[NationalComparison],
)
async def get_national_comparison(
    flow: str = Query("export", description="export | import"),
    from_: str = Query(..., alias="from", description="YYYY-MM"),
    to: str = Query(..., description="YYYY-MM"),
):
    """NestJS: ComexstatService.getNationalComparison() — 3 chamadas → 1 SELECT."""
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


@router.get(
    "/national-comparison/states-ranking",
    summary="Ranking de Estados",
    response_model=SuccessResponse[list[StateRanking]],
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


@router.get("/dashboard", summary="Dashboard", response_model=SuccessResponse[Dashboard])
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


@router.delete("/cache", summary="Limpar Cache")
async def clear_cache():
    """No-op: dados pré-computados não utilizam cache volátil."""
    return success({"message": "Cache não aplicável na nova arquitetura (dados materializados no PostgreSQL)."})
