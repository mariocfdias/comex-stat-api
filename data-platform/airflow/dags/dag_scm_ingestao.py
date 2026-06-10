"""
dag_scm_ingestao.py
====================
Substitui: ScmSchedulerService + ScmCsvService + ScmRepositoryService

Pipeline diário que baixa microdados SCM da ANM, filtra para o Ceará
e carrega no PostgreSQL (schema raw → tabelas gold via dbt).
"""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import requests
import urllib3
from airflow.decorators import dag, task
from airflow.exceptions import AirflowSkipException
from dateutil.relativedelta import relativedelta
from utils import (
    df_to_postgres,
    download_bytes,
    execute_sql,
    get_object_age_hours,
    get_s3_client,
    query_to_df,
    upload_json,
    upload_parquet,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ANM_ZIP_URL = "https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip"
CEARA_UF = "CE"
FRESHNESS_HOURS = 48
CHUNK_SIZE = 500  # replica ScmRepositoryService.chunkSize

RAW_BUCKET = "raw-data"
STAGING_BUCKET = "staging-data"

# Arquivos dentro do ZIP e suas colunas
SCM_FILES = {
    "Processo.txt": [
        "DSProcesso", "NRProcesso", "NRAnoProcesso", "BTAtivo", "NRNUP",
        "IDTipoRequerimento", "IDFaseProcesso", "IDUnidadeAdministrativaRegional",
        "IDUnidadeProtocolizadora", "DTProtocolo", "DTPrioridade", "QTAreaHA",
    ],
    "FaseProcesso.txt": ["IDFaseProcesso", "DSFaseProcesso"],
    "TipoRequerimento.txt": ["IDTipoRequerimento", "DSTipoRequerimento"],
    "Municipio.txt": ["IDMunicipio", "NMMunicipio", "SGUF"],
    "Substancia.txt": ["IDSubstancia", "NMSubstancia"],
    "ProcessoMunicipio.txt": ["DSProcesso", "IDMunicipio"],
    "ProcessoSubstancia.txt": ["DSProcesso", "IDSubstancia", "IDTipoUsoSubstancia", "IDMotivoEncerramentoSubstancia"],
}

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
    description="Ingestão diária de microdados SCM/ANM para o Ceará → PostgreSQL",
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["scm", "anm", "diario", "ingestao"],
)
def dag_scm_ingestao():

    @task
    def check_freshness() -> bool:
        """
        Retorna True se o ZIP tem menos de 48h (dado ainda fresco).
        Replica: ScmCsvService — freshness check antes do download.
        """
        key = "scm/microdados-scm.zip"
        age = get_object_age_hours(RAW_BUCKET, key)
        if age is not None and age < FRESHNESS_HOURS:
            print(f"Dado SCM fresco ({age:.1f}h < {FRESHNESS_HOURS}h). Pulando download.")
            return True
        return False

    @task
    def download_zip(is_fresh: bool) -> str:
        """
        Baixa microdados-scm.zip da ANM para o MinIO (camada bronze/raw-data).
        Replica: ScmCsvService.downloadAndExtractData()
          - verify=False (rejectUnauthorized: false no NestJS)
          - timeout 600s (600_000 ms no NestJS)
          - User-Agent simulando navegador
          - 3 retentativas com backoff (tratadas pelo Airflow)
        """
        run_date = datetime.utcnow()
        key = (
            f"scm/ano={run_date.year}/mes={run_date.month:02d}"
            f"/dia={run_date.day:02d}/microdados-scm.zip"
        )
        latest_key = "scm/microdados-scm.zip"

        if is_fresh:
            print(f"Dado fresco — reutilizando {latest_key}")
            return latest_key

        print(f"Baixando {ANM_ZIP_URL} ...")
        resp = requests.get(
            ANM_ZIP_URL,
            verify=False,
            timeout=600,
            stream=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/zip, */*",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )
        resp.raise_for_status()

        content = resp.content
        print(f"Download concluído: {len(content) / 1024 / 1024:.1f} MB")

        s3 = get_s3_client()
        for upload_key in (key, latest_key):
            s3.put_object(Bucket=RAW_BUCKET, Key=upload_key, Body=content)
            print(f"Salvo em {RAW_BUCKET}/{upload_key}")

        return latest_key

    @task
    def extract_and_parse(zip_key: str) -> str:
        """
        Extrai o ZIP e parseia os 7 arquivos TXT (separador ;).
        Replica: ScmCsvService — parsing linha a linha com split(';').
        Salva cada arquivo como Parquet no MinIO staging-data/scm/raw/.
        """
        run_date = datetime.utcnow()
        prefix = f"scm/raw/ano={run_date.year}/mes={run_date.month:02d}/"

        zip_bytes = download_bytes(RAW_BUCKET, zip_key)
        print(f"ZIP carregado: {len(zip_bytes) / 1024 / 1024:.1f} MB")

        saved_keys = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for filename, columns in SCM_FILES.items():
                # Encontra o arquivo dentro do ZIP (pode estar em subdiretório)
                zip_path = next(
                    (n for n in zf.namelist() if n.endswith(filename)), None
                )
                if zip_path is None:
                    print(f"AVISO: {filename} não encontrado no ZIP")
                    continue

                with zf.open(zip_path) as f:
                    # Replica: encoding latin-1 típico dos arquivos da ANM
                    df = pd.read_csv(
                        f,
                        sep=";",
                        encoding="latin-1",
                        dtype=str,
                        on_bad_lines="skip",
                        header=0,
                    )

                # Normalizar nomes de colunas
                df.columns = [c.strip() for c in df.columns]

                # Ajustar se o arquivo não tem header (usar nomes definidos)
                if list(df.columns) != columns and len(df.columns) == len(columns):
                    df.columns = columns
                elif list(df.columns) != columns:
                    # Reconstruir sem header
                    with zf.open(zip_path) as f:
                        df = pd.read_csv(
                            f,
                            sep=";",
                            encoding="latin-1",
                            dtype=str,
                            on_bad_lines="skip",
                            header=None,
                            names=columns,
                        )

                # Limpar espaços dos valores de string
                str_cols = df.select_dtypes(include="object").columns
                df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

                parquet_key = f"{prefix}{filename.replace('.txt', '.parquet')}"
                upload_parquet(STAGING_BUCKET, parquet_key, df)
                saved_keys[filename] = parquet_key
                print(f"  {filename}: {len(df):,} linhas → {parquet_key}")

        upload_json(STAGING_BUCKET, f"{prefix}manifest.json", {
            "files": saved_keys,
            "extracted_at": datetime.utcnow().isoformat(),
            "zip_key": zip_key,
        })
        return prefix

    @task
    def filter_ceara(prefix: str) -> str:
        """
        Filtra dados para o Ceará em cascata.
        Replica EXATAMENTE: ScmCsvService.filterDataForCeara()

        Passos:
        1. Filtrar Municipio onde SGUF = 'CE'
        2. Filtrar ProcessoMunicipio onde IDMunicipio ∈ ids_ce
        3. Identificar DSProcesso vinculados ao CE
        4. Filtrar Processo onde DSProcesso ∈ processos_ce
        5. Filtrar ProcessoSubstancia onde DSProcesso ∈ processos_ce
        """
        run_date = datetime.utcnow()
        out_prefix = f"scm/ceara/ano={run_date.year}/mes={run_date.month:02d}/"

        def load(filename: str) -> pd.DataFrame:
            key = f"{prefix}{filename.replace('.txt', '.parquet')}"
            return download_parquet(STAGING_BUCKET, key)

        # 1. Municípios do Ceará
        municipios = load("Municipio.txt")
        municipios_ce = municipios[municipios["SGUF"] == CEARA_UF].copy()
        ids_municipios_ce = set(municipios_ce["IDMunicipio"].dropna().astype(str))
        print(f"Municípios CE: {len(municipios_ce):,}")

        # 2. Relações processo-município no CE
        proc_mun = load("ProcessoMunicipio.txt")
        proc_mun_ce = proc_mun[proc_mun["IDMunicipio"].astype(str).isin(ids_municipios_ce)]
        ids_processos_ce = set(proc_mun_ce["DSProcesso"].dropna().astype(str))
        print(f"Processos vinculados ao CE: {len(ids_processos_ce):,}")

        # 3. Processos do CE
        processos = load("Processo.txt")
        processos_ce = processos[processos["DSProcesso"].astype(str).isin(ids_processos_ce)].copy()
        processos_ce = processos_ce.drop_duplicates(subset=["DSProcesso"])
        print(f"Processos CE: {len(processos_ce):,}")

        # 4. Substâncias dos processos CE
        proc_sub = load("ProcessoSubstancia.txt")
        proc_sub_ce = proc_sub[proc_sub["DSProcesso"].astype(str).isin(ids_processos_ce)]
        print(f"Relações Processo-Substância CE: {len(proc_sub_ce):,}")

        # Tabelas de referência (mantidas integrais — pequenas, sem filtro)
        fases = load("FaseProcesso.txt")
        tipos = load("TipoRequerimento.txt")
        substancias = load("Substancia.txt")

        # Salvar tudo filtrado
        filtered = {
            "Processo": processos_ce,
            "ProcessoMunicipio": proc_mun_ce,
            "ProcessoSubstancia": proc_sub_ce,
            "Municipio": municipios_ce,
            "FaseProcesso": fases,
            "TipoRequerimento": tipos,
            "Substancia": substancias,
        }
        for name, df in filtered.items():
            upload_parquet(STAGING_BUCKET, f"{out_prefix}{name}.parquet", df)

        upload_json(STAGING_BUCKET, f"{out_prefix}manifest.json", {
            "filtered_at": datetime.utcnow().isoformat(),
            "counts": {k: len(v) for k, v in filtered.items()},
        })
        print(f"Filtragem concluída → {out_prefix}")
        return out_prefix

    @task
    def load_reference_tables(ceara_prefix: str) -> str:
        """
        Carrega tabelas de referência no PostgreSQL schema raw.
        Tabelas pequenas: REPLACE completo a cada execução.
        """
        tables = {
            "scm_fase_processo": "FaseProcesso.parquet",
            "scm_tipo_requerimento": "TipoRequerimento.parquet",
            "scm_municipio": "Municipio.parquet",
            "scm_substancia": "Substancia.parquet",
        }

        for table_name, parquet_file in tables.items():
            df = download_parquet(STAGING_BUCKET, f"{ceara_prefix}{parquet_file}")

            # Converter tipos numéricos
            for col in df.columns:
                if col.startswith("ID"):
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            rows = df_to_postgres(df, table_name, schema="raw", if_exists="replace")
            print(f"  raw.{table_name}: {rows:,} linhas")

        return "ok"

    @task
    def load_processos(ceara_prefix: str, ref_status: str) -> str:
        """
        Carrega processos e relações N:N em chunks de CHUNK_SIZE.
        Replica: ScmRepositoryService.insertInBatches() com chunkSize=500.
        """
        # Processos principais
        processos = download_parquet(STAGING_BUCKET, f"{ceara_prefix}Processo.parquet")

        # Converter tipos
        int_cols = ["IDTipoRequerimento", "IDFaseProcesso",
                    "IDUnidadeAdministrativaRegional", "IDUnidadeProtocolizadora"]
        for col in int_cols:
            if col in processos.columns:
                processos[col] = pd.to_numeric(processos[col], errors="coerce")

        # TRUNCATE antes de inserir (dados completos a cada execução)
        execute_sql("TRUNCATE TABLE raw.scm_processo CASCADE")
        total = df_to_postgres(
            processos, "scm_processo", schema="raw",
            if_exists="append", chunk_size=CHUNK_SIZE,
        )
        print(f"raw.scm_processo: {total:,} linhas (chunks de {CHUNK_SIZE})")

        # Relação Processo-Município
        pm = download_parquet(STAGING_BUCKET, f"{ceara_prefix}ProcessoMunicipio.parquet")
        pm["IDMunicipio"] = pd.to_numeric(pm["IDMunicipio"], errors="coerce")
        execute_sql("TRUNCATE TABLE raw.scm_processo_municipio")
        total_pm = df_to_postgres(pm, "scm_processo_municipio", schema="raw",
                                  if_exists="append", chunk_size=CHUNK_SIZE)
        print(f"raw.scm_processo_municipio: {total_pm:,} linhas")

        # Relação Processo-Substância
        ps = download_parquet(STAGING_BUCKET, f"{ceara_prefix}ProcessoSubstancia.parquet")
        for col in ["IDSubstancia", "IDTipoUsoSubstancia", "IDMotivoEncerramentoSubstancia"]:
            if col in ps.columns:
                ps[col] = pd.to_numeric(ps[col], errors="coerce")
        execute_sql("TRUNCATE TABLE raw.scm_processo_substancia")
        total_ps = df_to_postgres(ps, "scm_processo_substancia", schema="raw",
                                  if_exists="append", chunk_size=CHUNK_SIZE)
        print(f"raw.scm_processo_substancia: {total_ps:,} linhas")

        return "ok"

    @task
    def compute_gold(ceara_prefix: str, load_status: str) -> None:
        """
        Materializa tabelas gold de analytics do SCM.
        Replica as queries do ScmRepositoryService (getProcessosByFase, etc.).
        Executa SQL direto no PostgreSQL (sem dbt neste primeiro momento).
        """
        analytics = {
            "gold_scm_by_fase": """
                INSERT INTO gold.scm_by_fase (id_fase, descricao_fase, total_processos)
                SELECT
                    p."IDFaseProcesso"::int,
                    f."DSFaseProcesso",
                    COUNT(p."DSProcesso") AS total_processos
                FROM raw.scm_processo p
                LEFT JOIN raw.scm_fase_processo f
                    ON p."IDFaseProcesso"::int = f."IDFaseProcesso"::int
                GROUP BY p."IDFaseProcesso", f."DSFaseProcesso"
                ORDER BY total_processos DESC
            """,
            "gold_scm_by_tipo": """
                INSERT INTO gold.scm_by_tipo (id_tipo, descricao_tipo, total_processos)
                SELECT
                    p."IDTipoRequerimento"::int,
                    t."DSTipoRequerimento",
                    COUNT(p."DSProcesso") AS total_processos
                FROM raw.scm_processo p
                LEFT JOIN raw.scm_tipo_requerimento t
                    ON p."IDTipoRequerimento"::int = t."IDTipoRequerimento"::int
                GROUP BY p."IDTipoRequerimento", t."DSTipoRequerimento"
                ORDER BY total_processos DESC
            """,
            "gold_scm_by_municipio": """
                INSERT INTO gold.scm_by_municipio (id_municipio, nome_municipio, total_processos)
                SELECT
                    m."IDMunicipio"::int,
                    m."NMMunicipio",
                    COUNT(DISTINCT pm."DSProcesso") AS total_processos
                FROM raw.scm_municipio m
                LEFT JOIN raw.scm_processo_municipio pm
                    ON m."IDMunicipio"::text = pm."IDMunicipio"::text
                GROUP BY m."IDMunicipio", m."NMMunicipio"
                ORDER BY total_processos DESC
            """,
            "gold_scm_by_substancia": """
                INSERT INTO gold.scm_by_substancia (id_substancia, nome_substancia, total_processos)
                SELECT
                    s."IDSubstancia"::int,
                    s."NMSubstancia",
                    COUNT(DISTINCT ps."DSProcesso") AS total_processos
                FROM raw.scm_substancia s
                LEFT JOIN raw.scm_processo_substancia ps
                    ON s."IDSubstancia"::text = ps."IDSubstancia"::text
                GROUP BY s."IDSubstancia", s."NMSubstancia"
                ORDER BY total_processos DESC
            """,
        }

        # Criar tabelas gold se não existirem e popular
        execute_sql("""
            CREATE TABLE IF NOT EXISTS gold.scm_by_fase (
                id_fase          INTEGER,
                descricao_fase   TEXT,
                total_processos  INTEGER,
                updated_at       TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS gold.scm_by_tipo (
                id_tipo          INTEGER,
                descricao_tipo   TEXT,
                total_processos  INTEGER,
                updated_at       TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS gold.scm_by_municipio (
                id_municipio     INTEGER,
                nome_municipio   TEXT,
                total_processos  INTEGER,
                updated_at       TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS gold.scm_by_substancia (
                id_substancia    INTEGER,
                nome_substancia  TEXT,
                total_processos  INTEGER,
                updated_at       TIMESTAMP DEFAULT NOW()
            );
        """)

        for table, sql in analytics.items():
            gold_table = table.replace("gold_", "")
            execute_sql(f"TRUNCATE TABLE gold.{gold_table}")
            execute_sql(sql)
            result = query_to_df(f'SELECT COUNT(*) AS n FROM gold."{gold_table}"')
            print(f"  gold.{gold_table}: {result['n'].iloc[0]:,} linhas")

        # Registrar execução na tabela de auditoria
        execute_sql("""
            INSERT INTO raw.pipeline_runs (dag_id, run_id, finished_at, status)
            VALUES ('dag_scm_ingestao', %(run_id)s, NOW(), 'success')
        """, {"run_id": datetime.utcnow().isoformat()})

        print("SCM gold materializado com sucesso.")

    # Grafo de dependências
    fresh = check_freshness()
    zip_key = download_zip(fresh)
    prefix = extract_and_parse(zip_key)
    ceara_prefix = filter_ceara(prefix)
    ref_status = load_reference_tables(ceara_prefix)
    load_status = load_processos(ceara_prefix, ref_status)
    compute_gold(ceara_prefix, load_status)


dag_scm_ingestao()
