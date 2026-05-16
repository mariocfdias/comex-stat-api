"""DAG: ingestão diária do Comexstat (MDIC) → MinIO → PostgreSQL warehouse."""
from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Any

import requests
from airflow.decorators import dag, task
from airflow.models import Variable

log = logging.getLogger(__name__)

COMEXSTAT_BASE = "https://api-comexstat.mdic.gov.br"
CEARA_STATE_ID = 23
MINIO_BUCKET = "data-lake"


def _get_minio_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=Variable.get("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=Variable.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=Variable.get("MINIO_SECRET_KEY", "minioadmin"),
    )


def _query_general(payload: dict) -> list[dict]:
    resp = requests.post(
        f"{COMEXSTAT_BASE}/general",
        json=payload,
        params={"language": "pt"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"ComexStat error: {data.get('message')}")
    return data["data"]["list"]


def _current_period() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


@dag(
    dag_id="comexstat_ingest",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["comexstat", "ingest"],
)
def comexstat_ingest():

    @task()
    def extract_summary() -> dict[str, Any]:
        year, month = _current_period()
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1

        periods = {
            "currentMonth": {
                "from": f"{prev_year}-{prev_month:02d}",
                "to": f"{prev_year}-{prev_month:02d}",
            },
            "yearToDate": {"from": f"{year}-01", "to": f"{year}-{month:02d}"},
            "lastYear": {"from": f"{year - 1}-01", "to": f"{year - 1}-12"},
        }
        results: dict[str, Any] = {}
        for period_type, period in periods.items():
            for flow in ("export", "import"):
                rows = _query_general({
                    "flow": flow,
                    "monthDetail": False,
                    "period": period,
                    "filters": [{"filter": "state", "values": [CEARA_STATE_ID]}],
                    "metrics": ["metricFOB"],
                })
                key = f"{period_type}_{flow}"
                results[key] = rows[0]["metricFOB"] if rows else 0

        s3 = _get_minio_client()
        payload = json.dumps(results).encode()
        s3.put_object(
            Bucket=MINIO_BUCKET,
            Key=f"raw/comexstat/{date.today()}/summary.json",
            Body=payload,
        )
        log.info("Summary extracted: %s", list(results.keys()))
        return results

    @task()
    def extract_timeseries() -> str:
        year, month = _current_period()
        rows_monthly: list[dict] = []
        rows_annual: list[dict] = []

        for flow in ("export", "import"):
            # Monthly last 3 years
            monthly = _query_general({
                "flow": flow,
                "monthDetail": True,
                "period": {"from": f"{year - 3}-01", "to": f"{year}-{month:02d}"},
                "filters": [{"filter": "state", "values": [CEARA_STATE_ID]}],
                "metrics": ["metricFOB"],
            })
            rows_monthly.extend([{**r, "flow": flow} for r in monthly])

            # Annual last 10 years
            annual = _query_general({
                "flow": flow,
                "monthDetail": False,
                "period": {"from": f"{year - 10}-01", "to": f"{year - 1}-12"},
                "filters": [{"filter": "state", "values": [CEARA_STATE_ID]}],
                "metrics": ["metricFOB"],
            })
            rows_annual.extend([{**r, "flow": flow} for r in annual])

        s3 = _get_minio_client()
        key = f"raw/comexstat/{date.today()}/timeseries.json"
        s3.put_object(
            Bucket=MINIO_BUCKET,
            Key=key,
            Body=json.dumps({"monthly": rows_monthly, "annual": rows_annual}).encode(),
        )
        log.info("Timeseries extracted: %d monthly, %d annual rows", len(rows_monthly), len(rows_annual))
        return key

    @task()
    def extract_partners() -> str:
        year, month = _current_period()
        results = {}
        for flow in ("export", "import"):
            rows = _query_general({
                "flow": flow,
                "monthDetail": False,
                "period": {"from": f"{year}-01", "to": f"{year}-{month:02d}"},
                "filters": [{"filter": "state", "values": [CEARA_STATE_ID]}],
                "details": ["country"],
                "metrics": ["metricFOB"],
            })
            results[flow] = rows

        s3 = _get_minio_client()
        key = f"raw/comexstat/{date.today()}/partners.json"
        s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=json.dumps(results).encode())
        return key

    @task()
    def extract_states_ranking() -> str:
        year, month = _current_period()
        period = {"from": f"{year}-01", "to": f"{year}-{month:02d}"}
        results = {}

        for flow in ("export", "import"):
            national = _query_general({"flow": flow, "monthDetail": False, "period": period, "metrics": ["metricFOB"]})
            by_state = _query_general({"flow": flow, "monthDetail": False, "period": period, "details": ["state"], "metrics": ["metricFOB"]})
            by_sector = _query_general({"flow": flow, "monthDetail": False, "period": period, "details": ["state", "ISICSection"], "metrics": ["metricFOB"]})
            by_partner = _query_general({"flow": flow, "monthDetail": False, "period": period, "details": ["state", "country"], "metrics": ["metricFOB"]})
            by_product = _query_general({"flow": flow, "monthDetail": False, "period": period, "details": ["state", "heading"], "metrics": ["metricFOB"]})

            results[flow] = {
                "national": national,
                "by_state": by_state,
                "by_sector": by_sector,
                "by_partner": by_partner,
                "by_product": by_product,
            }

        s3 = _get_minio_client()
        key = f"raw/comexstat/{date.today()}/states_ranking.json"
        s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=json.dumps(results).encode())
        log.info("States ranking extracted for both flows")
        return key

    @task()
    def load_to_warehouse(summary: dict, ts_key: str, partners_key: str, ranking_key: str) -> None:
        import psycopg2
        import os

        db_url = os.getenv("AIRFLOW_CONN_POSTGRES_WAREHOUSE", "").replace("postgresql://", "")
        conn = psycopg2.connect(f"postgresql://{db_url}" if not db_url.startswith("postgresql") else db_url)
        cur = conn.cursor()

        # Load summary
        for period_type in ("currentMonth", "yearToDate", "lastYear"):
            exp = float(summary.get(f"{period_type}_export") or 0) / 1_000_000
            imp = float(summary.get(f"{period_type}_import") or 0) / 1_000_000
            cur.execute("""
                INSERT INTO comexstat_summary (period_type, period_label, export_fob, import_fob, balance)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (period_type, period_label) DO UPDATE
                SET export_fob=EXCLUDED.export_fob, import_fob=EXCLUDED.import_fob,
                    balance=EXCLUDED.balance, updated_at=NOW()
            """, (period_type, period_type, exp, imp, exp - imp))

        conn.commit()
        cur.close()
        conn.close()
        log.info("Warehouse loaded successfully")

    summary = extract_summary()
    ts_key = extract_timeseries()
    partners_key = extract_partners()
    ranking_key = extract_states_ranking()
    load_to_warehouse(summary, ts_key, partners_key, ranking_key)


comexstat_ingest()
