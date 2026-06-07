"""
dag_comexstat_ingestao.py
==========================
Substitui: ComexstatService — todas as chamadas on-demand para a API ComexStat/MDIC.

Fluxo original (NestJS, sob demanda):
  queryGeneral({ flow, monthDetail, period, filters, details, metrics })
    → POST https://api-comexstat.mdic.gov.br/general?language=pt (timeout 60s)
    → Agregação em memória (Map, forEach, sort)
    → Cache Redis/in-memory (TTL 24h)

  Endpoint mais pesado — getStatesRanking(): 5 chamadas paralelas de 60s cada!

Fluxo novo (Airflow, diariamente):
  [extract_export_data, extract_import_data]
    → store_bronze (MinIO raw-data/comexstat/)
    → transform_silver (Parquet normalizado)
    → [compute_gold_summary, compute_gold_timeseries, compute_gold_partners,
       compute_gold_products, compute_gold_national, compute_gold_dashboard]
    → load_postgresql

Ganho esperado: getStatesRanking de 10-60s → <100ms (1 SELECT com JOINs pré-computados).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from dateutil.relativedelta import relativedelta

COMEXSTAT_API_URL = "https://api-comexstat.mdic.gov.br/general"
CEARA_STATE_ID = 23  # ID do Ceará na API ComexStat (mesmo que CEARA_STATE_ID no NestJS)
API_TIMEOUT = 60  # segundos (mesmo que o NestJS)
API_POOL = "comexstat_api"  # pool do Airflow para limitar concorrência

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(hours=1),
    "email_on_failure": False,
    "pool": API_POOL,
}


def _get_reference_periods() -> dict:
    """
    Replica ComexstatService.getCurrentDateInfo().
    A API ComexStat tem delay de ~2 meses — mesmo cálculo do NestJS.
    """
    now = datetime.utcnow()
    reference = now.replace(day=1) - relativedelta(months=2)
    current_year = reference.year
    current_month = reference.month
    previous = reference - relativedelta(months=1)

    return {
        "current_year": current_year,
        "current_month": current_month,
        "previous_year": previous.year,
        "previous_month": previous.month,
        "previous_year_full": current_year - 1,
        # Períodos para pré-computar todos os tipos de SummaryPeriod
        "period_current_month": {
            "from": f"{previous.year}-{previous.month:02d}",
            "to": f"{previous.year}-{previous.month:02d}",
        },
        "period_year_to_date": {
            "from": f"{current_year}-01",
            "to": f"{current_year}-{current_month:02d}",
        },
        "period_last_year": {
            "from": f"{current_year - 1}-01",
            "to": f"{current_year - 1}-12",
        },
        # Histórico completo (últimos 5 anos) para timeseries
        "period_history": {
            "from": f"{current_year - 5}-01",
            "to": f"{current_year}-{current_month:02d}",
        },
    }


@dag(
    dag_id="dag_comexstat_ingestao",
    description="Ingere dados ComexStat/MDIC e pré-computa todos os 9 endpoints (substitui queryGeneral on-demand)",
    schedule_interval="0 3 * * *",  # diariamente às 3h BRT
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["comexstat", "mdic", "diario", "ingestao"],
    doc_md=__doc__,
)
def dag_comexstat_ingestao():

    @task
    def extract_export_data() -> str:
        """
        Extrai dados de exportação do Ceará da API ComexStat.
        Replica: queryGeneral({ flow: 'export', ... }) com máximo de detalhes
        para permitir todas as agregações (summary, timeseries, partners, products).

        Configurações da API (mesmas do NestJS):
        - POST /general com Content-Type: application/json
        - Query param: ?language=pt
        - filters: [{ filter: 'state', values: [23] }]  ← Ceará
        - details: ['country', 'ISICSection', 'heading', 'chapter', 'ncm']
        - metrics: ['metricFOB', 'metricKG', 'metricCIF']

        TODO: implementar múltiplas requisições para cobrir diferentes períodos
        e dimensões necessárias para pré-computar todos os endpoints.
        """
        periods = _get_reference_periods()
        minio_key = f"comexstat/ano={periods['current_year']}/mes={periods['current_month']:02d}/export_ceara.json"

        # TODO: implementar
        # import requests, boto3, json
        # configs = [
        #     {"name": "export_ceara_monthly", "params": {
        #         "flow": "export", "monthDetail": True,
        #         "period": periods["period_history"],
        #         "filters": [{"filter": "state", "values": [CEARA_STATE_ID]}],
        #         "details": ["country", "ISICSection", "heading"],
        #         "metrics": ["metricFOB", "metricKG"],
        #     }},
        #     # ... outras combinações para pré-computar todos os endpoints
        # ]
        # for config in configs:
        #     response = requests.post(COMEXSTAT_API_URL, json=config["params"],
        #                              params={"language": "pt"}, timeout=API_TIMEOUT)
        #     response.raise_for_status()
        #     s3.put_object(Bucket='raw-data', Key=f'comexstat/{config["name"]}.json',
        #                   Body=json.dumps(response.json()))
        print(f"TODO: extrair exportações → raw-data/{minio_key}")
        return f"raw-data/{minio_key}"

    @task
    def extract_import_data() -> str:
        """
        Extrai dados de importação do Ceará e dados nacionais (todos os estados).
        Necessário para: getNationalComparison() e getStatesRanking().

        Replica as chamadas de getNationalComparison() e getStatesRanking():
        - nacional (sem filtro de estado): para calcular participação do CE
        - por estado (details: ['state']): ranking de todos os 27 estados
        - por estado+setor: top setores por estado
        - por estado+país: top parceiros por estado
        - por estado+produto: top produtos por estado

        TODO: implementar extração com dados nacionais (sem filtro state=CE).
        """
        periods = _get_reference_periods()
        minio_key = f"comexstat/ano={periods['current_year']}/mes={periods['current_month']:02d}/import_nacional.json"

        # TODO: implementar
        # Inclui extração SEM filtro de estado para dados nacionais
        # e COM filtro de estado para todos os estados (details: ['state'])
        print(f"TODO: extrair importações + dados nacionais → raw-data/{minio_key}")
        return f"raw-data/{minio_key}"

    @task
    def store_bronze(export_key: str, import_key: str) -> str:
        """
        Confirma que os dados brutos estão salvos no MinIO camada bronze.
        Adiciona metadados de ingestão (timestamp, versão, hash).

        TODO: verificar integridade dos arquivos e criar manifesto de ingestão.
        """
        print(f"TODO: validar bronze {export_key} + {import_key}")
        return "raw-data/comexstat/manifest.json"

    @task
    def transform_silver(bronze_manifest: str) -> str:
        """
        Normaliza e converte JSONs brutos para Parquet na camada silver.
        Replica a normalização de campos do ComexstatService:
        - monthNumber vs month (operador ??)
        - country vs countryName (operador ??)
        - state vs stateName (operador ??)
        - coIsicSection vs ISICSectionCode (operador ??)
        - Valores FOB/KG/CIF: tratamento de string com vírgula → número

        TODO: usar pandas para normalizar e salvar como Parquet particionado.
        """
        # TODO: implementar
        # import pandas as pd
        # df = pd.read_json(...)
        # df['metricFOB'] = pd.to_numeric(df['metricFOB'].astype(str).str.replace(',', '.'), errors='coerce')
        # df['country'] = df['country'].fillna(df['countryName'])
        # df.to_parquet('staging-data/comexstat/...', partition_cols=['year', 'month', 'flow'])
        print("TODO: normalizar JSON → Parquet na camada silver")
        return "staging-data/comexstat/"

    @task
    def compute_gold_summary(silver_path: str) -> str:
        """
        Pré-computa tabela gold_comexstat_summary para os 3 períodos padrão.
        Replica: ComexstatService.getSummaryData() para period_type em
        [currentMonth, yearToDate, lastYear].

        Colunas da tabela gold:
        period_type, period_from, period_to, period_label,
        exports, imports, trade_balance, trade_current,
        export_participation, import_participation,
        export_ranking, import_ranking

        dbt model: models/gold/gold_comexstat_summary.sql
        TODO: executar 'dbt run --select gold_comexstat_summary'
        """
        print("TODO: dbt run --select gold_comexstat_summary")
        return "gold.gold_comexstat_summary"

    @task
    def compute_gold_timeseries(silver_path: str) -> str:
        """
        Pré-computa séries temporais mensais e anuais.
        Replica: ComexstatService.getTimeSeries() e getTimeSeriesWithSectors()

        Tabelas gold:
        - gold_comexstat_timeseries (mensal e anual, pivotado: export/import/balance/current)
        - gold_comexstat_timeseries_sectors (detalhamento por setor ISIC)

        dbt models: models/gold/gold_comexstat_timeseries*.sql
        TODO: executar 'dbt run --select gold_comexstat_timeseries*'
        """
        print("TODO: dbt run --select gold_comexstat_timeseries*")
        return "gold.gold_comexstat_timeseries"

    @task
    def compute_gold_partners(silver_path: str) -> str:
        """
        Pré-computa top países parceiros por fluxo e período.
        Replica: ComexstatService.getPartnerCountries()

        Inclui cálculo de percentual sobre total (toMillions() + percentual).

        dbt model: models/gold/gold_comexstat_partners.sql
        TODO: executar 'dbt run --select gold_comexstat_partners'
        """
        print("TODO: dbt run --select gold_comexstat_partners")
        return "gold.gold_comexstat_partners"

    @task
    def compute_gold_products(silver_path: str) -> str:
        """
        Pré-computa top produtos por nível de agregação (ncm/heading/chapter).
        Replica: ComexstatService.getTopProducts()

        Suporta os 3 AggregationLevels: NCM (8 dígitos), HEADING (4), CHAPTER (2).

        dbt model: models/gold/gold_comexstat_products.sql
        TODO: executar 'dbt run --select gold_comexstat_products'
        """
        print("TODO: dbt run --select gold_comexstat_products")
        return "gold.gold_comexstat_products"

    @task
    def compute_gold_national(silver_path: str) -> str:
        """
        Pré-computa comparação nacional e ranking de estados.
        Replica:
        - ComexstatService.getNationalComparison() — 3 chamadas paralelas originalmente
        - ComexstatService.getStatesRanking() — 5 chamadas paralelas originalmente!

        Tabelas gold:
        - gold_comexstat_national_comparison (participação e ranking do CE)
        - gold_comexstat_states_ranking_base (27 estados com valor e participação)
        - gold_comexstat_states_top_sectors (top 5 setores por estado — window function)
        - gold_comexstat_states_top_partners (top 5 parceiros por estado)
        - gold_comexstat_states_top_products (top 5 produtos por estado)

        dbt models: models/gold/gold_comexstat_national*.sql, gold_comexstat_states*.sql
        TODO: executar 'dbt run --select gold_comexstat_national* gold_comexstat_states*'
        """
        print("TODO: dbt run --select gold_comexstat_national* gold_comexstat_states*")
        return "gold.gold_comexstat_states_ranking"

    @task
    def compute_gold_dashboard(
        summary_status: str, partners_status: str, products_status: str
    ) -> str:
        """
        Pré-computa o painel consolidado (dashboard).
        Replica: ComexstatService.getDashboardData() — combina summary + products + partners.

        dbt model: models/gold/gold_comexstat_dashboard.sql
        TODO: executar 'dbt run --select gold_comexstat_dashboard'
        """
        print("TODO: dbt run --select gold_comexstat_dashboard")
        return "gold.gold_comexstat_dashboard"

    @task
    def load_postgresql(
        summary: str, timeseries: str, partners: str,
        products: str, national: str, dashboard: str,
    ) -> None:
        """
        Valida que todas as tabelas gold foram criadas e executa dbt test.
        Verifica que as respostas são numericamente equivalentes ao NestJS:
        - trade_balance = exports - imports
        - trade_current = exports + imports
        - participation in [0, 100]
        - rank in [1, 27] para states_ranking

        TODO: executar 'dbt test --select comexstat' e verificar contagens.
        """
        print("TODO: dbt test --select comexstat")
        print(f"Tabelas validadas: {[summary, timeseries, partners, products, national, dashboard]}")

    # Grafo de dependências
    export_key = extract_export_data()
    import_key = extract_import_data()
    bronze = store_bronze(export_key, import_key)
    silver = transform_silver(bronze)

    summary = compute_gold_summary(silver)
    timeseries = compute_gold_timeseries(silver)
    partners = compute_gold_partners(silver)
    products = compute_gold_products(silver)
    national = compute_gold_national(silver)
    dashboard = compute_gold_dashboard(summary, partners, products)

    load_postgresql(summary, timeseries, partners, products, national, dashboard)


dag_comexstat_ingestao()
