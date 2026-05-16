"""DAG: ingestão semanal SCM (ANM) → MinIO → PostgreSQL warehouse (sem SQLite)."""
from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, date

import requests
from airflow.decorators import dag, task

log = logging.getLogger(__name__)

ANM_URL = "https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip"
CE_UF = "CE"
CHUNK = 500


def _get_minio_client():
    import boto3
    from airflow.models import Variable
    return boto3.client(
        "s3",
        endpoint_url=Variable.get("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=Variable.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=Variable.get("MINIO_SECRET_KEY", "minioadmin"),
    )


def _parse_csv(content: bytes, delimiter: str = ";") -> list[dict]:
    lines = content.decode("latin-1").splitlines()
    if not lines:
        return []
    headers = [h.strip() for h in lines[0].split(delimiter)]
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(delimiter)]
        rows.append(dict(zip(headers, parts)))
    return rows


@dag(
    dag_id="scm_ingest",
    schedule="0 3 * * 1",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["scm", "ingest"],
)
def scm_ingest():

    @task()
    def download_and_upload_raw() -> str:
        log.info("Downloading SCM ZIP from ANM...")
        resp = requests.get(
            ANM_URL,
            timeout=900,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        zip_bytes = resp.content
        log.info("Downloaded %d bytes", len(zip_bytes))

        s3 = _get_minio_client()
        key = f"raw/scm/{date.today()}/microdados-scm.zip"
        s3.put_object(Bucket="data-lake", Key=key, Body=zip_bytes)
        return key

    @task()
    def parse_and_filter_ce(zip_key: str) -> str:
        import boto3

        s3 = _get_minio_client()
        obj = s3.get_object(Bucket="data-lake", Key=zip_key)
        zip_bytes = obj["Body"].read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            log.info("ZIP contents: %s", names)

            def read_file(filename: str) -> bytes:
                candidates = [n for n in names if n.endswith(filename)]
                if not candidates:
                    raise FileNotFoundError(f"{filename} not in ZIP")
                return zf.read(candidates[0])

            municipios = _parse_csv(read_file("Municipio.txt"))
            fases = _parse_csv(read_file("FaseProcesso.txt"))
            tipos = _parse_csv(read_file("TipoRequerimento.txt"))
            substancias = _parse_csv(read_file("Substancia.txt"))
            processos = _parse_csv(read_file("Processo.txt"))
            proc_mun = _parse_csv(read_file("ProcessoMunicipio.txt"))
            proc_sub = _parse_csv(read_file("ProcessoSubstancia.txt"))

        # Filter CE
        mun_ce = {m["IDMunicipio"] for m in municipios if m.get("SGUF") == CE_UF}
        municipios_ce = [m for m in municipios if m.get("SGUF") == CE_UF]
        proc_mun_ce = [pm for pm in proc_mun if pm.get("IDMunicipio") in mun_ce]
        processos_ce_ids = {pm["DSProcesso"] for pm in proc_mun_ce}
        processos_ce = [p for p in processos if p.get("DSProcesso") in processos_ce_ids]
        proc_sub_ce = [ps for ps in proc_sub if ps.get("DSProcesso") in processos_ce_ids]
        sub_ids_ce = {ps["IDSubstancia"] for ps in proc_sub_ce}
        substancias_ce = [s for s in substancias if s.get("IDSubstancia") in sub_ids_ce]

        payload = {
            "municipios": municipios_ce,
            "fases": fases,
            "tipos": tipos,
            "substancias": substancias_ce,
            "processos": processos_ce,
            "proc_mun": proc_mun_ce,
            "proc_sub": proc_sub_ce,
        }
        key = f"processed/scm/{date.today()}/filtered_ce.json"
        s3.put_object(Bucket="data-lake", Key=key, Body=json.dumps(payload).encode())
        log.info(
            "CE filter: %d municipios, %d processos, %d proc_mun",
            len(municipios_ce), len(processos_ce), len(proc_mun_ce),
        )
        return key

    @task()
    def load_to_warehouse(data_key: str) -> None:
        import psycopg2
        import os

        s3 = _get_minio_client()
        obj = s3.get_object(Bucket="data-lake", Key=data_key)
        data = json.loads(obj["Body"].read())

        db_url = os.getenv("AIRFLOW_CONN_POSTGRES_WAREHOUSE", "postgresql://warehouse:warehouse@postgres:5432/warehouse")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Truncate in FK order
        cur.execute("TRUNCATE TABLE scm_processo_substancia, scm_processo_municipio, scm_processos, scm_substancias, scm_municipios, scm_tipos, scm_fases")

        # Reference tables
        for f in data["fases"]:
            cur.execute("INSERT INTO scm_fases VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (f.get("IDFaseProcesso"), f.get("DSFaseProcesso")))
        for t in data["tipos"]:
            cur.execute("INSERT INTO scm_tipos VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (t.get("IDTipoRequerimento"), t.get("DSTipoRequerimento")))
        for m in data["municipios"]:
            cur.execute("INSERT INTO scm_municipios VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        (m.get("IDMunicipio"), m.get("NMMunicipio"), m.get("SGUF")))
        for s in data["substancias"]:
            cur.execute("INSERT INTO scm_substancias VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (s.get("IDSubstancia"), s.get("NMSubstancia")))
        conn.commit()

        # Processos in chunks
        processos = data["processos"]
        seen = set()
        unique = []
        for p in processos:
            k = p.get("DSProcesso")
            if k and k not in seen:
                seen.add(k)
                unique.append(p)

        for i in range(0, len(unique), CHUNK):
            chunk = unique[i:i + CHUNK]
            for p in chunk:
                cur.execute("""
                    INSERT INTO scm_processos
                      (ds_processo, nr_processo, nr_ano_processo, bt_ativo, nr_nup,
                       id_tipo_requerimento, id_fase_processo,
                       id_unidade_administrativa_regional, id_unidade_protocolizadora,
                       dt_protocolo, dt_prioridade, qt_area_ha)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ds_processo) DO NOTHING
                """, (
                    p.get("DSProcesso"), p.get("NRProcesso"), p.get("NRAnoProcesso"),
                    p.get("BTAtivo"), p.get("NRNUP"),
                    int(p["IDTipoRequerimento"]) if p.get("IDTipoRequerimento") and p["IDTipoRequerimento"].strip() else None,
                    int(p["IDFaseProcesso"]) if p.get("IDFaseProcesso") and p["IDFaseProcesso"].strip() else None,
                    int(p["IDUnidadeAdministrativaRegional"]) if p.get("IDUnidadeAdministrativaRegional") and p["IDUnidadeAdministrativaRegional"].strip() else None,
                    int(p["IDUnidadeProtocolizadora"]) if p.get("IDUnidadeProtocolizadora") and p["IDUnidadeProtocolizadora"].strip() else None,
                    p.get("DTProtocolo"), p.get("DTPrioridade"), p.get("QTAreaHA"),
                ))
            conn.commit()

        # Relations in chunks
        for rel_list, table, cols in [
            (data["proc_mun"], "scm_processo_municipio", ("DSProcesso", "IDMunicipio")),
            (data["proc_sub"], "scm_processo_substancia", ("DSProcesso", "IDSubstancia", "IDTipoUsoSubstancia", "IDMotivoEncerramentoSubstancia")),
        ]:
            for i in range(0, len(rel_list), CHUNK):
                chunk = rel_list[i:i + CHUNK]
                for r in chunk:
                    if table == "scm_processo_municipio":
                        cur.execute(
                            "INSERT INTO scm_processo_municipio (ds_processo, id_municipio) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (r.get("DSProcesso"), r.get("IDMunicipio")),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO scm_processo_substancia (ds_processo, id_substancia, id_tipo_uso_substancia, id_motivo_encerramento_substancia) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (
                                r.get("DSProcesso"), r.get("IDSubstancia"),
                                r.get("IDTipoUsoSubstancia") or None,
                                r.get("IDMotivoEncerramentoSubstancia") or None,
                            ),
                        )
                conn.commit()

        cur.close()
        conn.close()
        log.info("SCM warehouse load complete")

    zip_key = download_and_upload_raw()
    data_key = parse_and_filter_ce(zip_key)
    load_to_warehouse(data_key)


scm_ingest()
