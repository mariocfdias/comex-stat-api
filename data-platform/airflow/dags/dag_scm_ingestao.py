"""
dag_scm_ingestao.py
====================
Substitui: ScmSchedulerService (@Cron EVERY_DAY_AT_2AM) + ScmCsvService.downloadAndExtractData()

Fluxo original (NestJS):
  ScmSchedulerService → ScmCsvService.downloadAndExtractData()
    → download ZIP da ANM (~centenas de MB, timeout 10min, 3 retentativas)
    → adm-zip extract para data/scm/extracted/
    → parse 7 arquivos TXT (separador ;) em entidades TypeORM
    → filterDataForCeara() — cascata: municipios CE → processo-municipio → processos
    → ScmRepositoryService.insertInBatches() → SQLite (data/scm.db)

Fluxo novo (Airflow + PostgreSQL):
  check_freshness → download_zip → extract_and_parse → filter_ceara
    → load_reference_tables → load_processos → compute_analytics → load_postgresql
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

ANM_URL = "https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip"
FRESHNESS_HOURS = 48  # reutiliza arquivo com menos de 48h (mesmo que ScmCsvService)
CEARA_UF = "CE"
CHUNK_SIZE = 500  # registros por batch de INSERT

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "email_on_failure": False,
}


@dag(
    dag_id="dag_scm_ingestao",
    description="Ingere microdados SCM da ANM e carrega no PostgreSQL (substitui ScmSchedulerService)",
    schedule_interval="0 2 * * *",  # diariamente às 2h BRT (mesmo horário do NestJS)
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["scm", "anm", "diario", "ingestao"],
    doc_md=__doc__,
)
def dag_scm_ingestao():

    @task
    def check_freshness() -> bool:
        """
        Verifica se o arquivo SCM baixado tem menos de 48h.
        Replica: ScmCsvService — lógica de freshness check antes do download.

        TODO: Verificar timestamp do objeto no MinIO (bucket raw-data/scm/).
        Se fresher que FRESHNESS_HOURS, retorna True (skip download).
        Caso contrário, retorna False (precisa baixar).
        """
        # TODO: implementar verificação via MinIO client
        # import boto3
        # s3 = boto3.client('s3', endpoint_url=f"http://{os.environ['MINIO_ENDPOINT']}", ...)
        # try:
        #     obj = s3.head_object(Bucket='raw-data', Key='scm/microdados-scm.zip')
        #     age = datetime.utcnow() - obj['LastModified'].replace(tzinfo=None)
        #     return age.total_seconds() < FRESHNESS_HOURS * 3600
        # except s3.exceptions.NoSuchKey:
        #     return False
        return False  # placeholder: sempre baixa

    @task
    def download_zip(is_fresh: bool) -> str:
        """
        Baixa microdados-scm.zip da ANM para o MinIO (camada bronze/raw-data).
        Replica: ScmCsvService.downloadAndExtractData() — HTTP GET com timeout 600s e retry.

        Configurações replicadas do NestJS:
        - rejectUnauthorized: False (certificado ANM inválido)
        - Headers User-Agent simulando navegador
        - Timeout: 600s (10min)
        - 3 retentativas com exponential backoff

        TODO: implementar download em chunks para evitar OOM.
        Retorna: caminho do objeto no MinIO.
        """
        if is_fresh:
            print("Arquivo SCM ainda fresco (<48h). Pulando download.")
            return "raw-data/scm/microdados-scm.zip"  # usa arquivo existente

        # TODO: implementar download
        # import requests, boto3
        # session = requests.Session()
        # session.verify = False  # rejectUnauthorized: False
        # session.headers.update({'User-Agent': 'Mozilla/5.0 ...'})
        # response = session.get(ANM_URL, stream=True, timeout=600)
        # response.raise_for_status()
        # Fazer upload para MinIO em chunks
        minio_key = f"scm/ano={datetime.utcnow().year}/mes={datetime.utcnow().month:02d}/dia={datetime.utcnow().day:02d}/microdados-scm.zip"
        print(f"TODO: download de {ANM_URL} → MinIO raw-data/{minio_key}")
        return f"raw-data/{minio_key}"

    @task
    def extract_and_parse(minio_zip_key: str) -> dict:
        """
        Extrai o ZIP e parseia os 7 arquivos TXT (separador ;) para DataFrames.
        Replica: ScmCsvService — parsing linha a linha com split(';').

        Arquivos no ZIP (diretório microdados-scm/):
        - Processo.txt           → 12 colunas (DSProcesso PK, IDFaseProcesso FK, ...)
        - FaseProcesso.txt       → 2 colunas (IDFaseProcesso, DSFaseProcesso)
        - TipoRequerimento.txt   → 2 colunas (IDTipoRequerimento, DSTipoRequerimento)
        - Municipio.txt          → 3 colunas (IDMunicipio, NMMunicipio, SGUF)
        - Substancia.txt         → 2 colunas (IDSubstancia, NMSubstancia)
        - ProcessoMunicipio.txt  → 2 colunas (DSProcesso FK, IDMunicipio FK)
        - ProcessoSubstancia.txt → 4 colunas (DSProcesso FK, IDSubstancia FK, ...)

        TODO: baixar ZIP do MinIO, extrair em memória com zipfile, parsear com pandas.
        Retorna: dicionário com caminho dos Parquets salvos no MinIO staging-data/scm/
        """
        # TODO: implementar
        # import zipfile, io, pandas as pd, boto3
        # s3 = boto3.client(...)
        # zip_obj = s3.get_object(Bucket='raw-data', Key=minio_zip_key.replace('raw-data/', ''))
        # with zipfile.ZipFile(io.BytesIO(zip_obj['Body'].read())) as z:
        #     for filename in z.namelist():
        #         df = pd.read_csv(z.open(filename), sep=';', encoding='latin-1', dtype=str)
        #         s3.put_object(Bucket='staging-data', Key=f'scm/{filename}.parquet', Body=df.to_parquet())
        print(f"TODO: extrair e parsear {minio_zip_key}")
        return {"status": "TODO", "zip_key": minio_zip_key}

    @task
    def filter_ceara(parsed_data: dict) -> dict:
        """
        Filtra dados para o Ceará em cascata.
        Replica EXATAMENTE: ScmCsvService.filterDataForCeara()

        Lógica de filtragem (3 passos, mesma ordem do NestJS):
        1. Filtra municipios com SGUF = 'CE'
        2. Filtra ProcessoMunicipio onde IDMunicipio ∈ municipios_CE
        3. Identifica DSProcesso dos processos vinculados ao CE
        4. Filtra Processo onde DSProcesso ∈ processos_CE
        5. Filtra ProcessoSubstancia onde DSProcesso ∈ processos_CE

        TODO: carregar Parquets do staging, aplicar filtros, salvar resultado filtrado.
        """
        # TODO: implementar com pandas
        # municipios_ce = municipios_df[municipios_df['SGUF'] == CEARA_UF]
        # municipio_ids_ce = set(municipios_ce['IDMunicipio'])
        # pm_ce = processo_municipio_df[processo_municipio_df['IDMunicipio'].isin(municipio_ids_ce)]
        # processos_ce_ids = set(pm_ce['DSProcesso'])
        # processos_ce = processo_df[processo_df['DSProcesso'].isin(processos_ce_ids)]
        print(f"TODO: filtrar para Ceará")
        return {"status": "TODO", "upstream": parsed_data}

    @task
    def load_reference_tables(filtered_data: dict) -> str:
        """
        Carrega tabelas de referência (domínio) no PostgreSQL schema raw.
        Tabelas: fase_processo, tipo_requerimento, municipio, substancia

        TODO: usar psycopg2/sqlalchemy para COPY ou INSERT em batch.
        Estratégia: TRUNCATE + INSERT (tabelas pequenas, <10k linhas).
        """
        # TODO: implementar
        # engine = create_engine(os.environ['DATABASE_URL_DBT'])
        # for table_name, df in reference_dfs.items():
        #     df.to_sql(table_name, engine, schema='raw', if_exists='replace', index=False)
        print("TODO: carregar tabelas de referência no PostgreSQL")
        return "raw.scm_referencia"

    @task
    def load_processos(filtered_data: dict, ref_status: str) -> str:
        """
        Carrega processos e relações N:N no PostgreSQL schema raw.
        Tabelas: scm_processo, scm_processo_municipio, scm_processo_substancia

        Estratégia: chunks de CHUNK_SIZE registros para evitar OOM.
        Replica: ScmRepositoryService.insertInBatches()

        TODO: implementar INSERT em lote com chunk_size=500.
        """
        # TODO: implementar
        # for chunk in pd.read_parquet(...).pipe(chunked, CHUNK_SIZE):
        #     chunk.to_sql('scm_processo', engine, schema='raw', if_exists='append', index=False)
        print(f"TODO: carregar processos em chunks de {CHUNK_SIZE}")
        return "raw.scm_processo"

    @task
    def compute_analytics(processos_status: str) -> str:
        """
        Executa modelos dbt para criar as tabelas gold do SCM.
        Equivalente às queries de analytics do ScmService:
        - gold_scm_by_fase
        - gold_scm_by_tipo
        - gold_scm_by_municipio
        - gold_scm_by_substancia
        - gold_scm_by_uf

        TODO: executar 'dbt run --select scm' via subprocess ou DbtOperator.
        """
        # TODO: implementar
        # import subprocess
        # result = subprocess.run(
        #     ['dbt', 'run', '--select', 'scm', '--profiles-dir', '/opt/dbt'],
        #     capture_output=True, text=True
        # )
        # if result.returncode != 0:
        #     raise Exception(f"dbt run falhou: {result.stderr}")
        print("TODO: executar dbt run --select scm")
        return "gold.scm_*"

    @task
    def load_postgresql(analytics_status: str) -> None:
        """
        Valida que todas as tabelas gold foram criadas corretamente.
        Executa dbt test --select scm para verificar qualidade dos dados.

        TODO: executar 'dbt test --select scm' e verificar contagens.
        Comparar contagem de processos com o SQLite original para validação.
        """
        # TODO: implementar validação
        # Comparar: SELECT COUNT(*) FROM gold.gold_scm_processos
        # com: SELECT COUNT(*) FROM processos (SQLite)
        print("TODO: validar tabelas gold do SCM")
        print("TODO: executar dbt test --select scm")

    # Grafo de dependências (replica a lógica sequencial do NestJS)
    fresh = check_freshness()
    zip_key = download_zip(fresh)
    parsed = extract_and_parse(zip_key)
    filtered = filter_ceara(parsed)
    ref_status = load_reference_tables(filtered)
    proc_status = load_processos(filtered, ref_status)
    analytics_status = compute_analytics(proc_status)
    load_postgresql(analytics_status)


dag_scm_ingestao()
