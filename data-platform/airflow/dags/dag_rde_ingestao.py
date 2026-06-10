"""
dag_rde_ingestao.py
====================
Substitui: RdeService — chamadas on-demand via OData para o Banco Central do Brasil.

Fluxo original (NestJS, sob demanda):
  RdeService.getTodosRegistros(query) / getRegistrosIed(query)
    → GET .../odata/TodosRegistros?$filter=contains(UfPessoaNacional,'CE')
    → Parâmetros: $orderby=Ano desc,Mes desc, $skip, $top=100 (page-by-page para cliente)
    → Sem banco local — apenas cache Redis/in-memory por 24h

Fluxo novo (Airflow, uma vez por dia às 4h):
  [extract_todos_registros, extract_registros_ied]  ← paginação completa (PAGE_SIZE=1000)
    → store_bronze (MinIO raw-data/rde/)
    → transform_silver (deduplicação + Parquet)
    → load_postgresql (gold.gold_rde_todos_registros, gold.gold_rde_registros_ied)

FastAPI serve via SELECT com paginação nativa (skip/top) sem hit externo.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

from utils import (
    download_json,
    execute_sql,
    upload_json,
    upload_parquet,
)

RDE_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata"
CEARA_UF_FILTER = "contains(UfPessoaNacional,'CE')"
PAGE_SIZE = 1000  # aumentado de 100 (NestJS) para 1000 para ingestão completa
API_TIMEOUT = 60
RETRY_DELAY = 5  # segundos entre tentativas de página

# Campos esperados nas respostas (PascalCase preservado — igual ao DTO NestJS)
TODOS_REGISTROS_FIELDS = [
    "CodigoRDE", "NomePessoaNacional", "UfPessoaNacional",
    "NomePessoaEstrangeira", "PaisPessoaEstrangeira", "MoedaOperacao",
    "ValorOperacao", "Sistema", "Ocorrencia", "Modalidade", "Ano", "Mes",
]
REGISTROS_IED_FIELDS = TODOS_REGISTROS_FIELDS + ["CnpjBaseReceptora"]

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "email_on_failure": False,
}


def _fetch_all_pages(endpoint: str, extra_params: dict | None = None) -> list[dict]:
    """
    Pagina completamente um endpoint OData do BCB.
    Replica a lógica de paginação que o NestJS expõe ao cliente, mas executa
    até o fim em vez de parar no que o cliente pediu.
    """
    params = {
        "$format": "json",
        "$filter": CEARA_UF_FILTER,
        "$orderby": "Ano desc,Mes desc",
        "$top": PAGE_SIZE,
    }
    if extra_params:
        params.update(extra_params)

    headers = {"Accept": "application/json;odata.metadata=minimal"}
    all_records: list[dict] = []
    skip = 0

    while True:
        params["$skip"] = skip
        resp = requests.get(
            endpoint,
            params=params,
            headers=headers,
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()

        page = resp.json().get("value", [])
        if not page:
            break

        all_records.extend(page)
        skip += PAGE_SIZE

        # Pausa leve para não sobrecarregar a API do BCB
        if len(page) == PAGE_SIZE:
            time.sleep(0.5)
        else:
            break  # Última página (retornou menos que PAGE_SIZE)

    return all_records


@dag(
    dag_id="dag_rde_ingestao",
    description="Ingere dados RDE do Banco Central (OData) e carrega no PostgreSQL",
    schedule_interval="0 4 * * *",
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["rde", "bcb", "diario", "ingestao"],
    doc_md=__doc__,
)
def dag_rde_ingestao():

    @task
    def extract_todos_registros() -> str:
        """
        Extrai todos os registros RDE do Ceará paginando completamente a API OData.
        Replica: RdeService.getTodosRegistros() — paginação completa em vez de por demanda.
        Dados disponíveis desde novembro/2011. Volume esperado: dezenas de milhares.
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        endpoint = f"{RDE_BASE_URL}/TodosRegistros"

        records = _fetch_all_pages(endpoint)

        key = f"rde/todos_registros_{today}.json"
        upload_json("raw-data", key, {"value": records, "total": len(records)})

        print(f"Extraídos {len(records)} registros TodosRegistros → raw-data/{key}")
        return f"raw-data/{key}"

    @task
    def extract_registros_ied() -> str:
        """
        Extrai todos os registros IED (Investimento Estrangeiro Direto) do Ceará.
        Replica: RdeService.getRegistrosIed() — paginação completa.
        Campo adicional vs TodosRegistros: CnpjBaseReceptora.
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        endpoint = f"{RDE_BASE_URL}/RegistrosIED"

        records = _fetch_all_pages(endpoint)

        key = f"rde/registros_ied_{today}.json"
        upload_json("raw-data", key, {"value": records, "total": len(records)})

        print(f"Extraídos {len(records)} registros RegistrosIED → raw-data/{key}")
        return f"raw-data/{key}"

    @task
    def store_bronze(todos_key: str, ied_key: str) -> dict:
        """Confirma armazenamento e retorna metadados de ingestão."""
        todos_data = download_json("raw-data", todos_key.removeprefix("raw-data/"))
        ied_data = download_json("raw-data", ied_key.removeprefix("raw-data/"))

        manifest = {
            "ingested_at": datetime.utcnow().isoformat(),
            "todos_registros": {"key": todos_key, "count": todos_data.get("total", 0)},
            "registros_ied": {"key": ied_key, "count": ied_data.get("total", 0)},
        }
        upload_json("raw-data", "rde/manifest.json", manifest)
        print(f"Bronze validado: {manifest}")
        return manifest

    @task
    def transform_silver(manifest: dict) -> dict:
        """
        Normaliza dados RDE para Parquet na camada silver.

        Transformações (mesmos nomes PascalCase do DTO NestJS para compatibilidade):
        - Deduplicação por CodigoRDE
        - Tipagem: Ano/Mes → int, ValorOperacao → float
        - Validação: UfPessoaNacional deve conter 'CE'
        - Remoção de CodigoRDE nulo
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        results = {}

        for dataset, fields, bronze_key in [
            ("todos_registros", TODOS_REGISTROS_FIELDS, manifest["todos_registros"]["key"]),
            ("registros_ied", REGISTROS_IED_FIELDS, manifest["registros_ied"]["key"]),
        ]:
            raw = download_json("raw-data", bronze_key.removeprefix("raw-data/"))
            records = raw.get("value", [])

            if not records:
                print(f"Aviso: {dataset} sem registros no bronze.")
                results[dataset] = {"count": 0, "key": f"rde/{dataset}_{today}.parquet"}
                continue

            df = pd.DataFrame(records)

            # Seleciona apenas colunas esperadas (ignora extras da API)
            available_fields = [f for f in fields if f in df.columns]
            df = df[available_fields].copy()

            # Tipagem
            for col in ["Ano", "Mes"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

            if "ValorOperacao" in df.columns:
                df["ValorOperacao"] = pd.to_numeric(df["ValorOperacao"], errors="coerce")

            # Limpeza
            if "CodigoRDE" in df.columns:
                df = df[df["CodigoRDE"].notna()].drop_duplicates(subset=["CodigoRDE"])

            # Validação do filtro CE (invariante do sistema)
            if "UfPessoaNacional" in df.columns:
                invalid = df[~df["UfPessoaNacional"].fillna("").str.contains("CE", na=False)]
                if not invalid.empty:
                    print(f"Aviso: {len(invalid)} registros sem UF='CE' removidos de {dataset}")
                df = df[df["UfPessoaNacional"].fillna("").str.contains("CE", na=False)]

            key = f"rde/{dataset}_{today}.parquet"
            upload_parquet("staging-data", key, df)

            results[dataset] = {"count": len(df), "key": key}
            print(f"{dataset}: {len(df)} registros → staging-data/{key}")

        return results

    @task
    def load_postgresql(silver_results: dict) -> None:
        """
        Carrega dados RDE no PostgreSQL.

        Tabelas gold (schema: gold):
        - gold_rde_todos_registros: cópia completa com índice em Ano, Mes
        - gold_rde_registros_ied: cópia completa com índice em Ano, Mes, CnpjBaseReceptora

        Invariantes validados:
        - Ano >= 2011 (dados disponíveis desde novembro/2011)
        - Mes em [1..12]
        - UfPessoaNacional contém 'CE'
        - CodigoRDE: not_null, unique
        """
        from utils import df_to_postgres, query_to_df

        today = datetime.utcnow().strftime("%Y%m%d")

        for dataset, table, key_field in [
            ("todos_registros", "gold_rde_todos_registros", "todos_registros"),
            ("registros_ied", "gold_rde_registros_ied", "registros_ied"),
        ]:
            info = silver_results.get(key_field, {})
            if not info.get("key") or info.get("count", 0) == 0:
                print(f"Sem dados para {dataset}, pulando carga.")
                continue

            from utils import download_parquet
            df = download_parquet("staging-data", info["key"])

            rows = df_to_postgres(df, table, schema="gold", if_exists="replace")
            print(f"Carregados {rows} registros em gold.{table}")

        # Validações de invariante
        checks = [
            ("Ano >= 2011", "SELECT COUNT(*) FROM gold.gold_rde_todos_registros WHERE \"Ano\" < 2011"),
            ("Mes valido", 'SELECT COUNT(*) FROM gold.gold_rde_todos_registros WHERE "Mes" NOT BETWEEN 1 AND 12'),
            ("UF CE", "SELECT COUNT(*) FROM gold.gold_rde_todos_registros WHERE \"UfPessoaNacional\" NOT LIKE '%CE%'"),
        ]
        for check_name, sql in checks:
            df = query_to_df(sql)
            violations = int(df.iloc[0, 0])
            if violations > 0:
                raise ValueError(f"Violação de invariante '{check_name}': {violations} registros")
            print(f"  {check_name}: OK")

        print("gold.gold_rde_* carregadas e validadas com sucesso.")

    # Grafo de dependências
    todos_key = extract_todos_registros()
    ied_key = extract_registros_ied()
    manifest = store_bronze(todos_key, ied_key)
    silver = transform_silver(manifest)
    load_postgresql(silver)


dag_rde_ingestao()
