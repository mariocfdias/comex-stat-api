"""DAG: ingestão diária RDE (BCB) → MinIO → PostgreSQL warehouse."""
from __future__ import annotations

import json
import logging
from datetime import datetime, date

import requests
from airflow.decorators import dag, task
from airflow.models import Variable

log = logging.getLogger(__name__)

BCB_BASE = "https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata"
PAGE_SIZE = 1000


def _get_minio_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=Variable.get("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=Variable.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=Variable.get("MINIO_SECRET_KEY", "minioadmin"),
    )


def _fetch_all(endpoint: str) -> list[dict]:
    records = []
    skip = 0
    while True:
        params = {
            "$format": "json",
            "$filter": "contains(UfPessoaNacional,'CE')",
            "$orderby": "Ano desc,Mes desc",
            "$top": PAGE_SIZE,
            "$skip": skip,
        }
        resp = requests.get(f"{BCB_BASE}/{endpoint}", params=params, timeout=60)
        resp.raise_for_status()
        batch = resp.json().get("value", [])
        records.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    return records


@dag(
    dag_id="rde_ingest",
    schedule="30 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["rde", "ingest"],
)
def rde_ingest():

    @task()
    def extract_todos_registros() -> str:
        records = _fetch_all("TodosRegistros")
        s3 = _get_minio_client()
        key = f"raw/rde/{date.today()}/todos_registros.json"
        s3.put_object(Bucket="data-lake", Key=key, Body=json.dumps(records).encode())
        log.info("TodosRegistros: %d records", len(records))
        return key

    @task()
    def extract_registros_ied() -> str:
        records = _fetch_all("RegistrosIED")
        s3 = _get_minio_client()
        key = f"raw/rde/{date.today()}/registros_ied.json"
        s3.put_object(Bucket="data-lake", Key=key, Body=json.dumps(records).encode())
        log.info("RegistrosIED: %d records", len(records))
        return key

    @task()
    def load_todos_registros(key: str) -> None:
        import boto3
        import psycopg2
        import os

        s3 = _get_minio_client()
        obj = s3.get_object(Bucket="data-lake", Key=key)
        records = json.loads(obj["Body"].read())

        conn = psycopg2.connect(os.getenv("AIRFLOW_CONN_POSTGRES_WAREHOUSE", "postgresql://warehouse:warehouse@postgres:5432/warehouse"))
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE rde_todos_registros")
        for r in records:
            cur.execute("""
                INSERT INTO rde_todos_registros
                  (codigo_rde, nome_pessoa_nacional, uf_pessoa_nacional,
                   nome_pessoa_estrangeira, pais_pessoa_estrangeira,
                   moeda_operacao, valor_operacao, sistema, ocorrencia,
                   modalidade, ano, mes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (codigo_rde) DO UPDATE SET
                  nome_pessoa_nacional=EXCLUDED.nome_pessoa_nacional,
                  uf_pessoa_nacional=EXCLUDED.uf_pessoa_nacional,
                  ano=EXCLUDED.ano, mes=EXCLUDED.mes, updated_at=NOW()
            """, (
                r.get("CodigoRDE"), r.get("NomePessoaNacional"),
                r.get("UfPessoaNacional"), r.get("NomePessoaEstrangeira"),
                r.get("PaisPessoaEstrangeira"), r.get("MoedaOperacao"),
                r.get("ValorOperacao"), r.get("Sistema"),
                r.get("Ocorrencia"), r.get("Modalidade"),
                r.get("Ano"), r.get("Mes"),
            ))
        conn.commit()
        cur.close()
        conn.close()
        log.info("Loaded %d TodosRegistros records", len(records))

    @task()
    def load_registros_ied(key: str) -> None:
        import psycopg2
        import os

        s3 = _get_minio_client()
        obj = s3.get_object(Bucket="data-lake", Key=key)
        records = json.loads(obj["Body"].read())

        conn = psycopg2.connect(os.getenv("AIRFLOW_CONN_POSTGRES_WAREHOUSE", "postgresql://warehouse:warehouse@postgres:5432/warehouse"))
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE rde_registros_ied")
        for r in records:
            cur.execute("""
                INSERT INTO rde_registros_ied
                  (codigo_rde, cnpj_base_receptora, nome_pessoa_nacional,
                   uf_pessoa_nacional, nome_pessoa_estrangeira,
                   pais_pessoa_estrangeira, moeda_operacao, valor_operacao,
                   sistema, ocorrencia, modalidade, ano, mes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (codigo_rde) DO UPDATE SET
                  cnpj_base_receptora=EXCLUDED.cnpj_base_receptora,
                  updated_at=NOW()
            """, (
                r.get("CodigoRDE"), r.get("CnpjBaseReceptora"),
                r.get("NomePessoaNacional"), r.get("UfPessoaNacional"),
                r.get("NomePessoaEstrangeira"), r.get("PaisPessoaEstrangeira"),
                r.get("MoedaOperacao"), r.get("ValorOperacao"),
                r.get("Sistema"), r.get("Ocorrencia"), r.get("Modalidade"),
                r.get("Ano"), r.get("Mes"),
            ))
        conn.commit()
        cur.close()
        conn.close()
        log.info("Loaded %d RegistrosIED records", len(records))

    todos_key = extract_todos_registros()
    ied_key = extract_registros_ied()
    load_todos_registros(todos_key)
    load_registros_ied(ied_key)


rde_ingest()
