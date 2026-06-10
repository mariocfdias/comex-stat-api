"""
dag_comexstat_ingestao.py
==========================
Substitui: ComexstatService — todas as chamadas on-demand para a API ComexStat/MDIC.

Fluxo original (NestJS, sob demanda por requisição):
  queryGeneral({ flow, monthDetail, period, filters, details, metrics })
    → POST https://api-comexstat.mdic.gov.br/general?language=pt (timeout 60s)
    → Agregação em memória (Map, forEach, sort)
  getStatesRanking(): 5 chamadas paralelas de 60s = até 60s por request!

Fluxo novo (Airflow, uma vez por dia às 3h):
  18 chamadas API → raw-data/comexstat/ (bronze)
  → staging-data/comexstat/ (silver Parquet)
  → [compute_gold_*] em paralelo com pandas
  → gold.gold_comexstat_* no PostgreSQL
  → API FastAPI serve via SELECT simples

Ganho: getStatesRanking de 10-60s → <100ms (pre-computado).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

from utils import (
    download_json,
    download_parquet,
    execute_sql,
    get_comexstat_periods,
    to_millions,
    upload_json,
    upload_parquet,
)

COMEXSTAT_API_URL = "https://api-comexstat.mdic.gov.br/general"
CEARA_STATE_ID = 23
API_TIMEOUT = 120
API_POOL = "comexstat_api"
TOP_N = 10  # top N parceiros/produtos por período

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(hours=1),
    "email_on_failure": False,
}


def _query_comexstat(
    flow: str,
    period: dict,
    *,
    month_detail: bool = False,
    filters: list | None = None,
    details: list | None = None,
    metrics: list | None = None,
) -> list[dict]:
    """
    Replica direta de ComexstatService.queryGeneral().
    POST /general?language=pt com body JSON.
    """
    body: dict[str, Any] = {
        "flow": flow,
        "monthDetail": month_detail,
        "period": period,
    }
    if filters:
        body["filters"] = filters
    if details:
        body["details"] = details
    if metrics:
        body["metrics"] = metrics

    resp = requests.post(
        COMEXSTAT_API_URL,
        json=body,
        params={"language": "pt"},
        timeout=API_TIMEOUT,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"ComexStat API error: {result.get('message')}")
    return result["data"]["list"]


def _filter_by_period(df: pd.DataFrame, from_ym: str, to_ym: str) -> pd.DataFrame:
    """
    Filtra DataFrame pelo período YYYY-MM (inclusive em ambos os lados).
    Suporta dois tipos de registros:
    - Com month > 0: dados mensais (monthDetail=True na API) → filtro por year*100+month
    - Com month == 0: dados anuais (monthDetail=False) → filtro por year apenas
    """
    from_y, from_m = int(from_ym[:4]), int(from_ym[5:7])
    to_y, to_m = int(to_ym[:4]), int(to_ym[5:7])

    monthly_mask = df["month"] > 0
    yearly_mask = df["month"] == 0

    monthly_rows = df[monthly_mask & (
        (df["year"] * 100 + df["month"] >= from_y * 100 + from_m)
        & (df["year"] * 100 + df["month"] <= to_y * 100 + to_m)
    )]
    yearly_rows = df[yearly_mask & (
        (df["year"] >= from_y) & (df["year"] <= to_y)
    )]
    return pd.concat([monthly_rows, yearly_rows], ignore_index=True)


def _normalize_row(row: dict) -> dict:
    """
    Normaliza campos do response da API ComexStat.
    Replica os operadores ?? do TypeScript no ComexstatService.
    """
    return {
        "year": int(row.get("year", 0)),
        "month": int(row.get("monthNumber") or row.get("month") or 0),
        "country": row.get("country") or row.get("countryName") or "",
        "state": row.get("state") or row.get("stateName") or "",
        "isic_section_code": row.get("coIsicSection") or row.get("ISICSectionCode") or "",
        "isic_section": row.get("ISICSection") or "",
        "ncm_code": row.get("ncmCode") or "",
        "ncm": row.get("ncm") or "",
        "heading_code": row.get("headingCode") or "",
        "heading": row.get("heading") or "",
        "chapter_code": row.get("chapterCode") or (row.get("headingCode") or "")[:2],
        "chapter": row.get("chapter") or "",
        "metric_fob": to_millions(row.get("metricFOB", 0)),
        "metric_cif": to_millions(row.get("metricCIF", 0)),
        "metric_kg": float(row.get("metricKG") or 0),
    }


@dag(
    dag_id="dag_comexstat_ingestao",
    description="Ingere dados ComexStat/MDIC e pré-computa todos os 9 endpoints",
    schedule_interval="0 3 * * *",
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["comexstat", "mdic", "diario", "ingestao"],
    doc_md=__doc__,
)
def dag_comexstat_ingestao():

    # =========================================================================
    # FASE 1: EXTRAÇÃO (18 chamadas API → raw-data/comexstat/)
    # Cada task extrai um slice específico dos dados para cobrir todos os
    # endpoints da API FastAPI sem necessidade de chamadas on-demand.
    # =========================================================================

    @task(pool=API_POOL)
    def extract_ce_export() -> str:
        """CE exportações mensais detalhadas (para summary + timeseries)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=True,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            metrics=["metricFOB", "metricKG"],
        )
        key = f"comexstat/ce_export_monthly_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_import() -> str:
        """CE importações mensais detalhadas (para summary + timeseries)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=True,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            metrics=["metricFOB", "metricCIF", "metricKG"],
        )
        key = f"comexstat/ce_import_monthly_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_partners_export() -> str:
        """CE exportações por país parceiro (para getPartnerCountries)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            details=["country"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/ce_export_partners_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_partners_import() -> str:
        """CE importações por país parceiro."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            details=["country"],
            metrics=["metricFOB", "metricCIF"],
        )
        key = f"comexstat/ce_import_partners_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_products_heading_export() -> str:
        """CE exportações por posição SH (heading, 4 dígitos) para getTopProducts."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            details=["heading"],
            metrics=["metricFOB", "metricKG"],
        )
        key = f"comexstat/ce_export_heading_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_products_heading_import() -> str:
        """CE importações por posição SH."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            details=["heading"],
            metrics=["metricFOB", "metricKG"],
        )
        key = f"comexstat/ce_import_heading_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_products_ncm_export() -> str:
        """CE exportações por NCM (8 dígitos)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            details=["ncm"],
            metrics=["metricFOB", "metricKG"],
        )
        key = f"comexstat/ce_export_ncm_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_ce_products_ncm_import() -> str:
        """CE importações por NCM."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            filters=[{"filter": "state", "values": [CEARA_STATE_ID]}],
            details=["ncm"],
            metrics=["metricFOB", "metricKG"],
        )
        key = f"comexstat/ce_import_ncm_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_export() -> str:
        """
        Total nacional de exportações mensais para calcular participação CE com precisão mensal.
        Usa monthDetail=True para que _filter_by_period funcione corretamente em todos
        os 3 tipos de período (current_month, ytd, last_year).
        """
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=True,  # necessário para filtrar por mês específico
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_export_total_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_import() -> str:
        """Total nacional de importações mensais."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=True,  # necessário para filtrar por mês específico
            metrics=["metricFOB", "metricCIF"],
        )
        key = f"comexstat/national_import_total_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_export() -> str:
        """Exportações nacionais por estado (todos os 27 UFs) para getStatesRanking."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            details=["state"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_export_states_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_import() -> str:
        """Importações nacionais por estado."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            details=["state"],
            metrics=["metricFOB", "metricCIF"],
        )
        key = f"comexstat/national_import_states_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_sectors_export() -> str:
        """Exportações por estado × setor ISIC (para top setores no states ranking)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            details=["state", "ISICSection"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_export_states_sectors_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_sectors_import() -> str:
        """Importações por estado × setor ISIC."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            details=["state", "ISICSection"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_import_states_sectors_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_partners_export() -> str:
        """Exportações por estado × país (para top parceiros no states ranking)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            details=["state", "country"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_export_states_partners_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_partners_import() -> str:
        """Importações por estado × país."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            details=["state", "country"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_import_states_partners_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_products_export() -> str:
        """Exportações por estado × posição SH (para top produtos no states ranking)."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "export",
            periods["period_history"],
            month_detail=False,
            details=["state", "heading"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_export_states_products_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    @task(pool=API_POOL)
    def extract_national_states_products_import() -> str:
        """Importações por estado × posição SH."""
        periods = get_comexstat_periods()
        data = _query_comexstat(
            "import",
            periods["period_history"],
            month_detail=False,
            details=["state", "heading"],
            metrics=["metricFOB"],
        )
        key = f"comexstat/national_import_states_products_{periods['current_year']}_{periods['current_month']:02d}.json"
        upload_json("raw-data", key, data)
        return f"raw-data/{key}"

    # =========================================================================
    # FASE 2: BRONZE → SILVER (normalização + Parquet)
    # =========================================================================

    @task
    def transform_silver(bronze_keys: list[str]) -> str:
        """
        Lê todos os JSONs bronze, normaliza campos e salva como Parquet.
        Replica normalização de campos do ComexstatService (operadores ?? TypeScript).
        """
        periods = get_comexstat_periods()
        prefix = f"comexstat/ano={periods['current_year']}/mes={periods['current_month']:02d}"

        # Mapeia nome do arquivo para dataset
        datasets: dict[str, list[dict]] = {}
        for key in bronze_keys:
            _, bucket_key = key.split("/", 1)
            raw = download_json("raw-data", bucket_key)
            name = bucket_key.split("/")[1].rsplit("_", 2)[0]  # ex: ce_export_monthly
            datasets.setdefault(name, []).extend([_normalize_row(r) for r in raw])

        for name, rows in datasets.items():
            if not rows:
                continue
            df = pd.DataFrame(rows)
            parquet_key = f"{prefix}/{name}.parquet"
            upload_parquet("staging-data", parquet_key, df)

        # Retorna apenas o prefixo dentro do bucket "staging-data" (sem incluir o nome do bucket)
        # As tasks compute_gold_* usam: download_parquet("staging-data", f"{silver_path}{name}.parquet")
        return f"{prefix}/"

    # =========================================================================
    # FASE 3: COMPUTE GOLD (pandas → PostgreSQL)
    # =========================================================================

    @task
    def compute_gold_summary(silver_path: str) -> str:
        """
        Pré-computa gold_comexstat_summary para 3 períodos.
        Replica getSummaryData() do NestJS para period_type em
        [current_month, year_to_date, last_year].
        """
        periods = get_comexstat_periods()
        prefix = silver_path

        exp_df = download_parquet("staging-data", f"{prefix}ce_export_monthly.parquet")
        imp_df = download_parquet("staging-data", f"{prefix}ce_import_monthly.parquet")
        nat_exp_df = download_parquet("staging-data", f"{prefix}national_export_total.parquet")
        nat_imp_df = download_parquet("staging-data", f"{prefix}national_import_total.parquet")
        nat_states_exp = download_parquet("staging-data", f"{prefix}national_export_states.parquet")
        nat_states_imp = download_parquet("staging-data", f"{prefix}national_import_states.parquet")

        period_defs = [
            ("current_month", periods["period_current_month"]["from"], periods["period_current_month"]["to"], periods["period_current_month"]["label"]),
            ("year_to_date", periods["period_year_to_date"]["from"], periods["period_year_to_date"]["to"], periods["period_year_to_date"]["label"]),
            ("last_year", periods["period_last_year"]["from"], periods["period_last_year"]["to"], periods["period_last_year"]["label"]),
        ]

        rows = []
        for period_type, p_from, p_to, label in period_defs:
            exp_filtered = _filter_by_period(exp_df, p_from, p_to)
            imp_filtered = _filter_by_period(imp_df, p_from, p_to)
            nat_exp_filtered = _filter_by_period(nat_exp_df, p_from, p_to)
            nat_imp_filtered = _filter_by_period(nat_imp_df, p_from, p_to)
            nat_states_exp_filtered = _filter_by_period(nat_states_exp, p_from, p_to)
            nat_states_imp_filtered = _filter_by_period(nat_states_imp, p_from, p_to)

            ce_exp = exp_filtered["metric_fob"].sum()
            ce_imp = imp_filtered["metric_fob"].sum()
            nat_exp = nat_exp_filtered["metric_fob"].sum()
            nat_imp = nat_imp_filtered["metric_fob"].sum()

            exp_participation = round((ce_exp / nat_exp * 100) if nat_exp > 0 else 0, 4)
            imp_participation = round((ce_imp / nat_imp * 100) if nat_imp > 0 else 0, 4)

            # Ranking do CE entre todos os estados no período
            states_exp_agg = nat_states_exp_filtered.groupby("state", as_index=False)["metric_fob"].sum()
            states_imp_agg = nat_states_imp_filtered.groupby("state", as_index=False)["metric_fob"].sum()

            states_exp_sorted = states_exp_agg.sort_values("metric_fob", ascending=False).reset_index(drop=True)
            states_imp_sorted = states_imp_agg.sort_values("metric_fob", ascending=False).reset_index(drop=True)

            ce_state_name = "Ceará"  # Nome que a API retorna para state_id=23
            exp_rank_rows = states_exp_sorted[states_exp_sorted["state"].str.contains(ce_state_name, case=False, na=False)]
            imp_rank_rows = states_imp_sorted[states_imp_sorted["state"].str.contains(ce_state_name, case=False, na=False)]

            exp_ranking = int(exp_rank_rows.index[0] + 1) if len(exp_rank_rows) > 0 else 0
            imp_ranking = int(imp_rank_rows.index[0] + 1) if len(imp_rank_rows) > 0 else 0

            rows.append({
                "period_type": period_type,
                "period_from": p_from,
                "period_to": p_to,
                "period_label": label,
                "exports_fob": round(ce_exp, 6),
                "imports_fob": round(ce_imp, 6),
                "trade_balance": round(ce_exp - ce_imp, 6),
                "trade_current": round(ce_exp + ce_imp, 6),
                "export_participation": exp_participation,
                "import_participation": imp_participation,
                "export_ranking": exp_ranking,
                "import_ranking": imp_ranking,
            })

        df_gold = pd.DataFrame(rows)
        execute_sql("DROP TABLE IF EXISTS gold.gold_comexstat_summary")
        execute_sql("""
            CREATE TABLE gold.gold_comexstat_summary (
                period_type TEXT NOT NULL,
                period_from TEXT,
                period_to TEXT,
                period_label TEXT,
                exports_fob NUMERIC,
                imports_fob NUMERIC,
                trade_balance NUMERIC,
                trade_current NUMERIC,
                export_participation NUMERIC,
                import_participation NUMERIC,
                export_ranking INT,
                import_ranking INT
            )
        """)
        from utils import df_to_postgres
        df_to_postgres(df_gold, "gold_comexstat_summary", schema="gold", if_exists="replace")
        return "gold.gold_comexstat_summary"

    @task
    def compute_gold_timeseries(silver_path: str) -> str:
        """
        Pré-computa séries temporais mensais e anuais para getTimeSeries().
        Inclui detalhamento por setor ISIC (getTimeSeriesWithSectors).
        """
        from utils import df_to_postgres

        exp_df = download_parquet("staging-data", f"{silver_path}ce_export_monthly.parquet")
        imp_df = download_parquet("staging-data", f"{silver_path}ce_import_monthly.parquet")

        # Série mensal
        exp_monthly = exp_df.groupby(["year", "month"], as_index=False)["metric_fob"].sum().rename(
            columns={"metric_fob": "exports_fob"}
        )
        imp_monthly = imp_df.groupby(["year", "month"], as_index=False)["metric_fob"].sum().rename(
            columns={"metric_fob": "imports_fob"}
        )
        monthly = exp_monthly.merge(imp_monthly, on=["year", "month"], how="outer").fillna(0)
        monthly["period_type"] = "monthly"
        monthly["trade_balance"] = monthly["exports_fob"] - monthly["imports_fob"]
        monthly["trade_current"] = monthly["exports_fob"] + monthly["imports_fob"]

        # Série anual
        exp_annual = exp_df.groupby("year", as_index=False)["metric_fob"].sum().rename(
            columns={"metric_fob": "exports_fob"}
        )
        imp_annual = imp_df.groupby("year", as_index=False)["metric_fob"].sum().rename(
            columns={"metric_fob": "imports_fob"}
        )
        annual = exp_annual.merge(imp_annual, on="year", how="outer").fillna(0)
        annual["month"] = 0
        annual["period_type"] = "annual"
        annual["trade_balance"] = annual["exports_fob"] - annual["imports_fob"]
        annual["trade_current"] = annual["exports_fob"] + annual["imports_fob"]

        df_gold = pd.concat([monthly, annual], ignore_index=True)
        df_to_postgres(df_gold, "gold_comexstat_timeseries", schema="gold", if_exists="replace")
        return "gold.gold_comexstat_timeseries"

    @task
    def compute_gold_partners(silver_path: str) -> str:
        """
        Pré-computa top países parceiros por fluxo e período.
        Replica getPartnerCountries() do NestJS — inclui percentual sobre total.
        """
        from utils import df_to_postgres

        periods = get_comexstat_periods()
        exp_df = download_parquet("staging-data", f"{silver_path}ce_export_partners.parquet")
        imp_df = download_parquet("staging-data", f"{silver_path}ce_import_partners.parquet")

        period_defs = [
            ("current_month", periods["period_current_month"]["from"], periods["period_current_month"]["to"]),
            ("year_to_date", periods["period_year_to_date"]["from"], periods["period_year_to_date"]["to"]),
            ("last_year", periods["period_last_year"]["from"], periods["period_last_year"]["to"]),
        ]

        rows = []
        for period_type, p_from, p_to in period_defs:
            exp_f = _filter_by_period(exp_df, p_from, p_to)
            imp_f = _filter_by_period(imp_df, p_from, p_to)

            exp_agg = exp_f.groupby("country", as_index=False)["metric_fob"].sum().rename(
                columns={"metric_fob": "exports_fob"}
            )
            imp_agg = imp_f.groupby("country", as_index=False)["metric_fob"].sum().rename(
                columns={"metric_fob": "imports_fob"}
            )

            merged = exp_agg.merge(imp_agg, on="country", how="outer").fillna(0)
            merged["current"] = merged["exports_fob"] + merged["imports_fob"]
            merged["balance"] = merged["exports_fob"] - merged["imports_fob"]

            total_exp = merged["exports_fob"].sum()
            total_imp = merged["imports_fob"].sum()
            total_cur = merged["current"].sum()

            for flow, sort_col, total in [
                ("export", "exports_fob", total_exp),
                ("import", "imports_fob", total_imp),
                ("total", "current", total_cur),
            ]:
                top = merged.sort_values(sort_col, ascending=False).head(TOP_N).reset_index(drop=True)
                for i, r in top.iterrows():
                    rows.append({
                        "period_type": period_type,
                        "flow": flow,
                        "country": r["country"],
                        "exports_fob": round(r["exports_fob"], 6),
                        "imports_fob": round(r["imports_fob"], 6),
                        "current": round(r["current"], 6),
                        "balance": round(r["balance"], 6),
                        "percentage": round((r[sort_col] / total * 100) if total > 0 else 0, 4),
                        "rank": i + 1,
                    })

        df_gold = pd.DataFrame(rows)
        df_to_postgres(df_gold, "gold_comexstat_partners", schema="gold", if_exists="replace")
        return "gold.gold_comexstat_partners"

    @task
    def compute_gold_products(silver_path: str) -> str:
        """
        Pré-computa top produtos por nível de agregação (ncm/heading/chapter).
        Replica getTopProducts() do NestJS nos 3 AggregationLevels.
        """
        from utils import df_to_postgres

        periods = get_comexstat_periods()
        exp_heading = download_parquet("staging-data", f"{silver_path}ce_export_heading.parquet")
        imp_heading = download_parquet("staging-data", f"{silver_path}ce_import_heading.parquet")
        exp_ncm = download_parquet("staging-data", f"{silver_path}ce_export_ncm.parquet")
        imp_ncm = download_parquet("staging-data", f"{silver_path}ce_import_ncm.parquet")

        period_defs = [
            ("current_month", periods["period_current_month"]["from"], periods["period_current_month"]["to"]),
            ("year_to_date", periods["period_year_to_date"]["from"], periods["period_year_to_date"]["to"]),
            ("last_year", periods["period_last_year"]["from"], periods["period_last_year"]["to"]),
        ]

        rows = []
        for period_type, p_from, p_to in period_defs:
            for flow, h_df, n_df in [("export", exp_heading, exp_ncm), ("import", imp_heading, imp_ncm)]:
                h_f = _filter_by_period(h_df, p_from, p_to)
                n_f = _filter_by_period(n_df, p_from, p_to)

                # Heading (4 dígitos) — AggregationLevel.HEADING
                h_agg = h_f.groupby(["heading_code", "heading"], as_index=False).agg(
                    value_fob=("metric_fob", "sum"), weight_kg=("metric_kg", "sum")
                )
                total_h = h_agg["value_fob"].sum()
                for i, r in h_agg.sort_values("value_fob", ascending=False).head(TOP_N).reset_index(drop=True).iterrows():
                    rows.append({
                        "period_type": period_type, "flow": flow,
                        "aggregation_level": "heading",
                        "code": r["heading_code"], "description": r["heading"],
                        "value_fob": round(r["value_fob"], 6), "weight_kg": round(r["weight_kg"], 3),
                        "percentage": round((r["value_fob"] / total_h * 100) if total_h > 0 else 0, 4),
                        "rank": i + 1,
                    })

                # Chapter (2 dígitos) — agrupado a partir de heading_code[:2]
                h_f = h_f.copy()
                h_f["chapter_code"] = h_f["heading_code"].str[:2]
                c_agg = h_f.groupby("chapter_code", as_index=False).agg(
                    chapter=("chapter", "first"), value_fob=("metric_fob", "sum"), weight_kg=("metric_kg", "sum")
                )
                total_c = c_agg["value_fob"].sum()
                for i, r in c_agg.sort_values("value_fob", ascending=False).head(TOP_N).reset_index(drop=True).iterrows():
                    rows.append({
                        "period_type": period_type, "flow": flow,
                        "aggregation_level": "chapter",
                        "code": r["chapter_code"], "description": r.get("chapter", ""),
                        "value_fob": round(r["value_fob"], 6), "weight_kg": round(r["weight_kg"], 3),
                        "percentage": round((r["value_fob"] / total_c * 100) if total_c > 0 else 0, 4),
                        "rank": i + 1,
                    })

                # NCM (8 dígitos) — AggregationLevel.NCM
                n_agg = n_f.groupby(["ncm_code", "ncm"], as_index=False).agg(
                    value_fob=("metric_fob", "sum"), weight_kg=("metric_kg", "sum")
                )
                total_n = n_agg["value_fob"].sum()
                for i, r in n_agg.sort_values("value_fob", ascending=False).head(TOP_N).reset_index(drop=True).iterrows():
                    rows.append({
                        "period_type": period_type, "flow": flow,
                        "aggregation_level": "ncm",
                        "code": r["ncm_code"], "description": r["ncm"],
                        "value_fob": round(r["value_fob"], 6), "weight_kg": round(r["weight_kg"], 3),
                        "percentage": round((r["value_fob"] / total_n * 100) if total_n > 0 else 0, 4),
                        "rank": i + 1,
                    })

        df_gold = pd.DataFrame(rows)
        df_to_postgres(df_gold, "gold_comexstat_products", schema="gold", if_exists="replace")
        return "gold.gold_comexstat_products"

    @task
    def compute_gold_national(silver_path: str) -> str:
        """
        Pré-computa comparação nacional e ranking de estados.
        Substitui:
          getNationalComparison() — 3 chamadas paralelas → 1 SELECT
          getStatesRanking()     — 5 chamadas paralelas → 1 SELECT com JOINs
        """
        from utils import df_to_postgres

        periods = get_comexstat_periods()

        # Carrega dados silver
        nat_exp = download_parquet("staging-data", f"{silver_path}national_export_total.parquet")
        nat_imp = download_parquet("staging-data", f"{silver_path}national_import_total.parquet")
        states_exp = download_parquet("staging-data", f"{silver_path}national_export_states.parquet")
        states_imp = download_parquet("staging-data", f"{silver_path}national_import_states.parquet")
        states_sectors_exp = download_parquet("staging-data", f"{silver_path}national_export_states_sectors.parquet")
        states_sectors_imp = download_parquet("staging-data", f"{silver_path}national_import_states_sectors.parquet")
        states_partners_exp = download_parquet("staging-data", f"{silver_path}national_export_states_partners.parquet")
        states_partners_imp = download_parquet("staging-data", f"{silver_path}national_import_states_partners.parquet")
        states_products_exp = download_parquet("staging-data", f"{silver_path}national_export_states_products.parquet")
        states_products_imp = download_parquet("staging-data", f"{silver_path}national_import_states_products.parquet")

        period_defs = [
            ("current_month", periods["period_current_month"]["from"], periods["period_current_month"]["to"]),
            ("year_to_date", periods["period_year_to_date"]["from"], periods["period_year_to_date"]["to"]),
            ("last_year", periods["period_last_year"]["from"], periods["period_last_year"]["to"]),
        ]

        comparison_rows = []
        ranking_rows = []

        for period_type, p_from, p_to in period_defs:
            for flow, n_df, s_df, sec_df, par_df, prod_df in [
                ("export", nat_exp, states_exp, states_sectors_exp, states_partners_exp, states_products_exp),
                ("import", nat_imp, states_imp, states_sectors_imp, states_partners_imp, states_products_imp),
            ]:
                n_f = _filter_by_period(n_df, p_from, p_to)
                s_f = _filter_by_period(s_df, p_from, p_to)
                sec_f = _filter_by_period(sec_df, p_from, p_to)
                par_f = _filter_by_period(par_df, p_from, p_to)
                prod_f = _filter_by_period(prod_df, p_from, p_to)

                # Agrega por estado — soma usada tanto para ranking quanto para total nacional
                # (consistente: total nacional = soma de todos os estados do mesmo dataset)
                # n_f (com monthDetail=True) é referência cruzada mais precisa quando disponível
                states_agg = s_f.groupby("state", as_index=False)["metric_fob"].sum()
                states_sorted = states_agg.sort_values("metric_fob", ascending=False).reset_index(drop=True)
                nat_total = states_sorted["metric_fob"].sum() or n_f["metric_fob"].sum()

                # Participação e ranking do CE
                ce_mask = states_sorted["state"].str.contains("Cear", case=False, na=False)
                ce_rows = states_sorted[ce_mask]
                ce_value = float(ce_rows["metric_fob"].iloc[0]) if len(ce_rows) > 0 else 0.0
                ce_rank = int(ce_rows.index[0] + 1) if len(ce_rows) > 0 else 0
                ce_participation = round((ce_value / nat_total * 100) if nat_total > 0 else 0, 4)

                comparison_rows.append({
                    "period_type": period_type,
                    "flow": flow,
                    "ce_fob": round(ce_value, 6),
                    "national_fob": round(nat_total, 6),
                    "participation": ce_participation,
                    "ranking": ce_rank,
                })

                # States ranking com top_sectors, top_partners, top_products
                for rank_i, row in states_sorted.iterrows():
                    state_name = row["state"]
                    value = row["metric_fob"]
                    participation = round((value / nat_total * 100) if nat_total > 0 else 0, 4)

                    # Top 5 setores
                    sec_state = sec_f[sec_f["state"] == state_name]
                    sec_agg = sec_state.groupby(["isic_section_code", "isic_section"], as_index=False)["metric_fob"].sum()
                    top_sectors = (
                        sec_agg.sort_values("metric_fob", ascending=False)
                        .head(5)[["isic_section_code", "isic_section", "metric_fob"]]
                        .rename(columns={"metric_fob": "value"})
                        .to_dict("records")
                    )

                    # Top 5 parceiros
                    par_state = par_f[par_f["state"] == state_name]
                    par_agg = par_state.groupby("country", as_index=False)["metric_fob"].sum()
                    top_partners = (
                        par_agg.sort_values("metric_fob", ascending=False)
                        .head(5)[["country", "metric_fob"]]
                        .rename(columns={"metric_fob": "value"})
                        .to_dict("records")
                    )

                    # Top 5 produtos (heading)
                    prod_state = prod_f[prod_f["state"] == state_name]
                    prod_agg = prod_state.groupby(["heading_code", "heading"], as_index=False)["metric_fob"].sum()
                    top_products = (
                        prod_agg.sort_values("metric_fob", ascending=False)
                        .head(5)[["heading_code", "heading", "metric_fob"]]
                        .rename(columns={"metric_fob": "value"})
                        .to_dict("records")
                    )

                    ranking_rows.append({
                        "period_type": period_type,
                        "flow": flow,
                        "rank": rank_i + 1,
                        "state": state_name,
                        "value_fob": round(value, 6),
                        "participation": participation,
                        "top_sectors": json.dumps(top_sectors),
                        "top_partners": json.dumps(top_partners),
                        "top_products": json.dumps(top_products),
                    })

        df_comparison = pd.DataFrame(comparison_rows)
        df_ranking = pd.DataFrame(ranking_rows)

        df_to_postgres(df_comparison, "gold_comexstat_national_comparison", schema="gold", if_exists="replace")
        df_to_postgres(df_ranking, "gold_comexstat_states_ranking", schema="gold", if_exists="replace")
        return "gold.gold_comexstat_national_comparison"

    @task
    def compute_gold_dashboard(summary: str, partners: str, products: str) -> str:
        """
        Pré-computa dashboard — combina summary + top partners + top products.
        Replica getDashboardData() do NestJS.
        """
        from utils import df_to_postgres

        # Busca dados já computados das tabelas gold
        from utils import query_to_df

        summary_df = query_to_df("SELECT * FROM gold.gold_comexstat_summary WHERE period_type = 'year_to_date'")
        partners_df = query_to_df(
            "SELECT * FROM gold.gold_comexstat_partners WHERE period_type = 'year_to_date' AND flow = 'total'"
        )
        products_df = query_to_df(
            "SELECT * FROM gold.gold_comexstat_products WHERE period_type = 'year_to_date' AND aggregation_level = 'heading'"
        )

        # Dashboard consolida tudo em uma tabela para resposta rápida
        dashboard = {
            "period_type": "year_to_date",
            "summary": summary_df.to_dict("records")[0] if not summary_df.empty else {},
            "top_export_partners": partners_df[partners_df.get("flow", pd.Series()) == "export"].head(5).to_dict("records"),
            "top_products": products_df.head(10).to_dict("records"),
        }

        df_meta = pd.DataFrame([{
            "period_type": "year_to_date",
            "generated_at": datetime.utcnow().isoformat(),
            "exports_fob": summary_df["exports_fob"].iloc[0] if not summary_df.empty else 0,
            "imports_fob": summary_df["imports_fob"].iloc[0] if not summary_df.empty else 0,
        }])
        df_to_postgres(df_meta, "gold_comexstat_dashboard_meta", schema="gold", if_exists="replace")
        return "gold.gold_comexstat_dashboard"

    @task
    def load_postgresql(
        summary: str,
        timeseries: str,
        partners: str,
        products: str,
        national: str,
        dashboard: str,
    ) -> None:
        """
        Valida que todas as tabelas gold foram criadas e executa verificações básicas.
        Replica as assertions do NestJS: trade_balance = exports - imports,
        participation em [0, 100], rank em [1, 27].
        """
        from utils import query_to_df

        checks = {
            "summary": "SELECT COUNT(*) FROM gold.gold_comexstat_summary",
            "timeseries": "SELECT COUNT(*) FROM gold.gold_comexstat_timeseries",
            "partners": "SELECT COUNT(*) FROM gold.gold_comexstat_partners",
            "products": "SELECT COUNT(*) FROM gold.gold_comexstat_products",
            "national_comparison": "SELECT COUNT(*) FROM gold.gold_comexstat_national_comparison",
            "states_ranking": "SELECT COUNT(*) FROM gold.gold_comexstat_states_ranking",
        }

        for table, sql in checks.items():
            df = query_to_df(sql)
            count = int(df.iloc[0, 0])
            if count == 0:
                raise ValueError(f"Tabela {table} está vazia após computação!")
            print(f"  {table}: {count} linhas")

        # Invariante: trade_balance = exports - imports (tolerância float)
        balance_check = query_to_df("""
            SELECT MAX(ABS(trade_balance - (exports_fob - imports_fob))) AS max_drift
            FROM gold.gold_comexstat_summary
        """)
        drift = float(balance_check.iloc[0, 0] or 0)
        if drift > 0.001:
            raise ValueError(f"trade_balance inconsistente — drift={drift}")

        print(f"Todas as {len(checks)} tabelas gold validadas com sucesso.")

    # =========================================================================
    # GRAFO DE DEPENDÊNCIAS
    # =========================================================================

    # Extração paralela (limitada pelo pool comexstat_api)
    ce_exp = extract_ce_export()
    ce_imp = extract_ce_import()
    ce_par_exp = extract_ce_partners_export()
    ce_par_imp = extract_ce_partners_import()
    ce_prod_h_exp = extract_ce_products_heading_export()
    ce_prod_h_imp = extract_ce_products_heading_import()
    ce_prod_n_exp = extract_ce_products_ncm_export()
    ce_prod_n_imp = extract_ce_products_ncm_import()
    nat_exp = extract_national_export()
    nat_imp = extract_national_import()
    nat_st_exp = extract_national_states_export()
    nat_st_imp = extract_national_states_import()
    nat_st_sec_exp = extract_national_states_sectors_export()
    nat_st_sec_imp = extract_national_states_sectors_import()
    nat_st_par_exp = extract_national_states_partners_export()
    nat_st_par_imp = extract_national_states_partners_import()
    nat_st_prod_exp = extract_national_states_products_export()
    nat_st_prod_imp = extract_national_states_products_import()

    all_keys = [
        ce_exp, ce_imp, ce_par_exp, ce_par_imp,
        ce_prod_h_exp, ce_prod_h_imp, ce_prod_n_exp, ce_prod_n_imp,
        nat_exp, nat_imp, nat_st_exp, nat_st_imp,
        nat_st_sec_exp, nat_st_sec_imp, nat_st_par_exp, nat_st_par_imp,
        nat_st_prod_exp, nat_st_prod_imp,
    ]

    silver = transform_silver(all_keys)

    # Computação gold em paralelo após o silver estar pronto
    summary = compute_gold_summary(silver)
    timeseries = compute_gold_timeseries(silver)
    partners = compute_gold_partners(silver)
    products = compute_gold_products(silver)
    national = compute_gold_national(silver)
    dashboard = compute_gold_dashboard(summary, partners, products)

    load_postgresql(summary, timeseries, partners, products, national, dashboard)


dag_comexstat_ingestao()
