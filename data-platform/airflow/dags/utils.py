"""
utils.py — Utilitários compartilhados entre as DAGs da plataforma.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime
from typing import Any

import boto3
import pandas as pd
import psycopg2
from botocore.client import Config
from dateutil.relativedelta import relativedelta


# =============================================================================
# MinIO / S3
# =============================================================================

def get_s3_client():
    """Retorna cliente boto3 configurado para o MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=f"http://{os.environ.get('MINIO_ENDPOINT', 'minio:9000')}",
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin123"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_json(bucket: str, key: str, data: Any) -> None:
    """Salva objeto Python como JSON no MinIO."""
    s3 = get_s3_client()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
        ContentType="application/json",
    )


def upload_parquet(bucket: str, key: str, df: pd.DataFrame) -> None:
    """Salva DataFrame como Parquet no MinIO."""
    s3 = get_s3_client()
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def download_json(bucket: str, key: str) -> Any:
    """Lê JSON do MinIO e retorna objeto Python."""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def download_parquet(bucket: str, key: str) -> pd.DataFrame:
    """Lê Parquet do MinIO e retorna DataFrame."""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def download_bytes(bucket: str, key: str) -> bytes:
    """Lê bytes brutos do MinIO."""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def object_exists(bucket: str, key: str) -> bool:
    """Verifica se objeto existe no MinIO."""
    s3 = get_s3_client()
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


def get_object_age_hours(bucket: str, key: str) -> float | None:
    """Retorna a idade do objeto em horas, ou None se não existir."""
    s3 = get_s3_client()
    try:
        meta = s3.head_object(Bucket=bucket, Key=key)
        last_modified = meta["LastModified"].replace(tzinfo=None)
        return (datetime.utcnow() - last_modified).total_seconds() / 3600
    except Exception:
        return None


# =============================================================================
# PostgreSQL
# =============================================================================

def get_pg_conn():
    """Retorna conexão psycopg2 com o PostgreSQL."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "comexstat_platform"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres_pass"),
    )


def df_to_postgres(
    df: pd.DataFrame,
    table: str,
    schema: str = "raw",
    if_exists: str = "replace",
    chunk_size: int = 500,
) -> int:
    """
    Salva DataFrame no PostgreSQL usando COPY (mais rápido que INSERT).
    Retorna número de linhas inseridas.
    """
    from sqlalchemy import create_engine

    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "comexstat_platform")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres_pass")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(url)

    with engine.begin() as conn:
        df.to_sql(
            table,
            conn,
            schema=schema,
            if_exists=if_exists,
            index=False,
            chunksize=chunk_size,
            method="multi",
        )

    return len(df)


def execute_sql(sql: str, params: dict | None = None) -> None:
    """Executa SQL arbitrário no PostgreSQL."""
    conn = get_pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
        conn.commit()
    finally:
        conn.close()


def query_to_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Executa SELECT e retorna DataFrame."""
    conn = get_pg_conn()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


# =============================================================================
# Datas (replicando lógica do ComexstatService.getCurrentDateInfo())
# =============================================================================

def get_reference_date() -> datetime:
    """
    A API ComexStat tem delay de ~2 meses.
    Replica: ComexstatService.getCurrentDateInfo() — subtrai 2 meses da data atual.
    """
    now = datetime.utcnow()
    return (now.replace(day=1) - relativedelta(months=2))


def get_comexstat_periods() -> dict:
    """Retorna todos os períodos necessários para pré-computar os endpoints."""
    ref = get_reference_date()
    prev = ref - relativedelta(months=1)
    return {
        "reference": ref,
        "current_year": ref.year,
        "current_month": ref.month,
        "period_current_month": {
            "from": f"{prev.year}-{prev.month:02d}",
            "to": f"{prev.year}-{prev.month:02d}",
            "label": f"{prev.strftime('%b').upper()}/{prev.year}",
        },
        "period_year_to_date": {
            "from": f"{ref.year}-01",
            "to": f"{ref.year}-{ref.month:02d}",
            "label": f"Jan-{ref.strftime('%b').upper()}/{ref.year}",
        },
        "period_last_year": {
            "from": f"{ref.year - 1}-01",
            "to": f"{ref.year - 1}-12",
            "label": str(ref.year - 1),
        },
        "period_history": {
            "from": f"{ref.year - 5}-01",
            "to": f"{ref.year}-{ref.month:02d}",
        },
    }


def to_millions(value: Any) -> float:
    """
    Converte valor para milhões de USD.
    Replica: ComexstatService.toMillions()
    """
    if value is None:
        return 0.0
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        num = float(value)
    except (ValueError, TypeError):
        return 0.0
    if not (num == num):  # NaN check
        return 0.0
    return round(num / 1_000_000, 6)
