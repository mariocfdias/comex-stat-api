"""DAG: ingestão semanal Sigmine (ANM shapefiles) → MinIO → PostgreSQL."""
from __future__ import annotations

import json
import logging
from datetime import datetime, date
from pathlib import Path

from airflow.decorators import dag, task

log = logging.getLogger(__name__)

LAYERS = {
    "area-servidao": "AREA_SERVIDAO",
    "arrendamento": "ARRENDAMENTO",
    "bloqueio": "BLOQUEIO",
    "ce": "CE",
    "protecao-fonte": "PROTECAO_FONTE",
    "reservas-garimpeiras": "RESERVAS_GARIMPEIRAS",
}

STATIC_DIR = "/app/static"


def _get_minio_client():
    import boto3
    from airflow.models import Variable
    return boto3.client(
        "s3",
        endpoint_url=Variable.get("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=Variable.get("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=Variable.get("MINIO_SECRET_KEY", "minioadmin"),
    )


@dag(
    dag_id="sigmine_ingest",
    schedule="0 4 * * 1",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["sigmine", "ingest"],
)
def sigmine_ingest():

    @task()
    def process_and_load_layers() -> None:
        import shapefile
        import json
        import psycopg2
        import os

        ce_bounds_path = Path(STATIC_DIR) / "geojs-23-mun.json"
        ce_bounds = None
        if ce_bounds_path.exists():
            ce_bounds = json.loads(ce_bounds_path.read_text())

        conn = psycopg2.connect(
            os.getenv("AIRFLOW_CONN_POSTGRES_WAREHOUSE", "postgresql://warehouse:warehouse@postgres:5432/warehouse")
        )
        cur = conn.cursor()

        shp_files = {
            "area-servidao": "sigmine/AREA_SERVIDAO.shp",
            "arrendamento": "sigmine/ARRENDAMENTO.shp",
            "bloqueio": "sigmine/BLOQUEIO.shp",
            "ce": "sigmine/CE.shp",
            "protecao-fonte": "sigmine/PROTECAO_FONTE.shp",
            "reservas-garimpeiras": "sigmine/RESERVAS_GARIMPEIRAS.shp",
        }

        for layer_name, shp_rel in shp_files.items():
            shp_path = Path(STATIC_DIR) / shp_rel
            if not shp_path.exists():
                log.warning("Shapefile not found: %s", shp_path)
                continue

            try:
                geojson = shapefile.Reader(str(shp_path)).__geo_interface__
                features = geojson.get("features", [])
                feature_count = len(features)

                cur.execute("""
                    INSERT INTO sigmine_layers (layer_name, geojson, feature_count, updated_at)
                    VALUES (%s, %s::jsonb, %s, NOW())
                    ON CONFLICT (layer_name) DO UPDATE
                    SET geojson=EXCLUDED.geojson,
                        feature_count=EXCLUDED.feature_count,
                        updated_at=NOW()
                """, (layer_name, json.dumps(geojson), feature_count))

                log.info("Layer %s: %d features loaded", layer_name, feature_count)
            except Exception as e:
                log.error("Failed to process layer %s: %s", layer_name, e)

        conn.commit()
        cur.close()
        conn.close()

    process_and_load_layers()


sigmine_ingest()
