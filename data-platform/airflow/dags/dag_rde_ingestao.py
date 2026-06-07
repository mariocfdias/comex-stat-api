"""
dag_rde_ingestao.py
====================
Substitui: RdeService — chamadas on-demand via OData para o Banco Central do Brasil.

Fluxo original (NestJS, sob demanda):
  RdeService.getTodosRegistros(query) / getRegistrosIed(query)
    → GET https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata/TodosRegistros
    → Parâmetros OData: $format=json, $filter=contains(UfPessoaNacional,'CE'),
                        $orderby=Ano desc,Mes desc, $skip, $top
    → Retorno direto ao cliente (sem agregação complexa)
    → Cache Redis/in-memory (TTL 24h)

Fluxo novo (Airflow, diariamente):
  [extract_todos_registros, extract_registros_ied]
    → store_bronze (MinIO raw-data/rde/)
    → transform_silver (deduplicação + tipagem)
    → load_postgresql (gold_rde_todos_registros, gold_rde_registros_ied)
"""

from __future__ import annotations

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

RDE_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata"
CEARA_UF_FILTER = "contains(UfPessoaNacional,'CE')"
PAGE_SIZE = 1000  # registros por página OData
API_TIMEOUT = 60  # segundos (mesmo que o NestJS)

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "email_on_failure": False,
}


@dag(
    dag_id="dag_rde_ingestao",
    description="Ingere dados RDE do Banco Central (OData) e carrega no PostgreSQL",
    schedule_interval="0 4 * * *",  # diariamente às 4h BRT
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
        Extrai todos os registros RDE do Ceará paginando pela API OData do BCB.
        Replica: RdeService.getTodosRegistros() — mas paginando até o fim.

        Endpoint: GET /TodosRegistros
        Filtro fixo: $filter=contains(UfPessoaNacional,'CE')
        Paginação: $skip=0, $top=PAGE_SIZE, incrementando até não ter mais registros.

        Quirks da API OData do BCB replicados do NestJS:
        - Header: Accept: application/json;odata.metadata=minimal
        - paramsSerializer: encodeURIComponent + replace(/%2C/g, ',')
        - Filtro contains() é case-sensitive no lado do BCB

        TODO: implementar paginação completa com checkpoint (skip) para retry seguro.
        """
        endpoint = f"{RDE_BASE_URL}/TodosRegistros"
        minio_key = "raw-data/rde/todos_registros.json"

        # TODO: implementar paginação
        # import requests, json, boto3
        # all_records = []
        # skip = 0
        # while True:
        #     response = requests.get(endpoint, params={
        #         '$format': 'json',
        #         '$filter': CEARA_UF_FILTER,
        #         '$orderby': 'Ano desc,Mes desc',
        #         '$skip': skip,
        #         '$top': PAGE_SIZE,
        #     }, headers={'Accept': 'application/json;odata.metadata=minimal'}, timeout=API_TIMEOUT)
        #     response.raise_for_status()
        #     data = response.json().get('value', [])
        #     if not data:
        #         break
        #     all_records.extend(data)
        #     skip += PAGE_SIZE
        # s3.put_object(Bucket='raw-data', Key='rde/todos_registros.json',
        #               Body=json.dumps({'value': all_records}))
        print(f"TODO: paginar {endpoint} → {minio_key}")
        return minio_key

    @task
    def extract_registros_ied() -> str:
        """
        Extrai registros IED (Investimento Estrangeiro Direto) do Ceará.
        Replica: RdeService.getRegistrosIed() — endpoint /RegistrosIED.

        Campo adicional em relação a TodosRegistros: CnpjBaseReceptora (CNPJ da empresa receptora).

        TODO: mesma lógica de paginação de extract_todos_registros().
        """
        endpoint = f"{RDE_BASE_URL}/RegistrosIED"
        minio_key = "raw-data/rde/registros_ied.json"

        print(f"TODO: paginar {endpoint} → {minio_key}")
        return minio_key

    @task
    def store_bronze(todos_key: str, ied_key: str) -> str:
        """
        Confirma armazenamento dos dados brutos no MinIO e registra metadados.
        TODO: criar manifesto de ingestão com contagem de registros e timestamp.
        """
        print(f"TODO: validar bronze {todos_key} + {ied_key}")
        return "raw-data/rde/manifest.json"

    @task
    def transform_silver(bronze_manifest: str) -> str:
        """
        Limpa e normaliza os dados RDE para Parquet.

        Transformações:
        - Deduplicação por CodigoRDE (chave única)
        - Tipagem: Ano/Mes → int, ValorOperacao → float
        - Verificação de filtro: todos os registros devem ter UfPessoaNacional contendo 'CE'
        - Remoção de registros sem CodigoRDE

        Campos preservados (mesmos nomes em PascalCase do DTO NestJS):
        CodigoRDE, NomePessoaNacional, UfPessoaNacional, NomePessoaEstrangeira,
        PaisPessoaEstrangeira, MoedaOperacao, ValorOperacao, Sistema,
        Ocorrencia, Modalidade, Ano, Mes [+ CnpjBaseReceptora para IED]

        TODO: implementar com pandas, salvar como Parquet.
        """
        # TODO: implementar
        # import pandas as pd
        # df = pd.read_json(...)
        # assert df['UfPessoaNacional'].str.contains('CE').all(), "Filtro CE não respeitado!"
        # df = df.drop_duplicates(subset=['CodigoRDE'])
        # df.to_parquet('staging-data/rde/todos_registros.parquet')
        print("TODO: normalizar RDE JSON → Parquet")
        return "staging-data/rde/"

    @task
    def load_postgresql(silver_path: str) -> None:
        """
        Carrega dados RDE no PostgreSQL e executa modelos dbt gold.

        Tabelas gold:
        - gold_rde_todos_registros (todos os registros paginados por Ano/Mes desc)
        - gold_rde_registros_ied (registros IED com CnpjBaseReceptora)

        Testes dbt:
        - CodigoRDE: not_null
        - Ano: not_null, >= 2011 (dados desde novembro/2011)
        - Mes: accepted_values [1..12]
        - UfPessoaNacional: todos devem conter 'CE'

        TODO: executar 'dbt run --select rde' + 'dbt test --select rde'
        """
        # TODO: implementar
        # subprocess.run(['dbt', 'run', '--select', 'rde', '--profiles-dir', '/opt/dbt'])
        # subprocess.run(['dbt', 'test', '--select', 'rde', '--profiles-dir', '/opt/dbt'])
        print("TODO: dbt run --select rde && dbt test --select rde")

    # Grafo de dependências
    todos_key = extract_todos_registros()
    ied_key = extract_registros_ied()
    bronze = store_bronze(todos_key, ied_key)
    silver = transform_silver(bronze)
    load_postgresql(silver)


dag_rde_ingestao()
