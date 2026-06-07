"""
models/comexstat.py — DTOs do domínio ComexStat.
================================================
Campos em snake_case (Python) → camelCase (JSON) via CamelModel.
Aliases explícitos onde o nome do campo é palavra reservada (from/type).
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import CamelModel


class Period(CamelModel):
    type: str
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    label: str | None = None


class Summary(CamelModel):
    period: Period
    exports: float
    imports: float
    trade_balance: float
    trade_current: float
    export_participation: float
    import_participation: float
    export_ranking: int
    import_ranking: int


class SummaryHistoryPoint(CamelModel):
    year: int
    month: int
    exports: float
    imports: float
    balance: float
    current: float


class TimeSeriesPoint(CamelModel):
    year: int
    value: float
    month: int | None = None


class Partner(CamelModel):
    country: str
    exports: float
    imports: float
    current: float
    balance: float
    percentage: float
    rank: int


class Product(CamelModel):
    code: str
    description: str
    value: float
    weight: float
    percentage: float
    rank: int


class NationalComparison(CamelModel):
    flow: str
    ce_fob: float
    national_fob: float
    participation: float
    ranking: int


class StateRanking(CamelModel):
    rank: int
    state: str
    value: float
    participation: float
    top_sectors: list[Any]
    top_partners: list[Any]
    top_products: list[Any]


class DashboardSummary(CamelModel):
    exports: float
    imports: float
    trade_balance: float
    trade_current: float


class DashboardPartner(CamelModel):
    country: str
    value: float
    percentage: float


class DashboardProduct(CamelModel):
    code: str
    description: str
    value: float


class Dashboard(CamelModel):
    summary: DashboardSummary | None = None
    top_export_partners: list[DashboardPartner]
    top_products: list[DashboardProduct]
