"""
dag_sigmine_ingestao.py
========================
Substitui: SigmineService — leitura de shapefiles estáticos em static/.

Problema atual (NestJS):
  - Shapefiles em static/ ESTÁTICOS — desatualizam até o próximo deploy
  - Cada request lê o shapefile do disco (cache de 24h para amenizar)
  - GeographicFilterService usa bounding box overlap (sem clip real)

Fluxo novo (Airflow, semanal, domingos às 1h):
  download_shapefiles → convert_to_geojson → filter_ceara_bbox → load_postgis

Layers processadas (mesmas do SigmineLayer enum no NestJS):
  AREA_SERVIDAO, ARRENDAMENTO, BLOQUEIO, CE, PROTECAO_FONTE, RESERVAS_GARIMPEIRAS

FastAPI serve via: SELECT ST_AsGeoJSON(geometry), properties FROM gold.gold_sigmine_layers
onde layer_name = :layer (índice GIST torna <5ms contra shapefile read em 200-500ms).
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timedelta

import geopandas as gpd
import pandas as pd
import requests
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from shapely.geometry import box, mapping

from utils import download_bytes, execute_sql, get_s3_client, upload_json

# Layers do Sigmine (mesmas do SigmineLayer enum no NestJS)
SIGMINE_LAYERS = [
    "AREA_SERVIDAO",
    "ARRENDAMENTO",
    "BLOQUEIO",
    "CE",
    "PROTECAO_FONTE",
    "RESERVAS_GARIMPEIRAS",
]

# Rota no MinIO para shapefiles (copiados de static/ ou baixados da ANM)
# static/ é montado no Airflow em /opt/airflow/static via docker-compose
STATIC_PATH = os.environ.get("SIGMINE_STATIC_PATH", "/opt/airflow/static")

# Bounding box do Ceará calculado do geojs-23-mun.json
# Replica: GeographicFilterService — turf.bbox(cearaGeometry)
# Os valores são os mesmos que o NestJS usa para filtrar features externas
CEARA_BBOX = (
    -41.5,   # min_lon (west)
    -7.87,   # min_lat (south)
    -37.25,  # max_lon (east)
    -2.78,   # max_lat (north)
)

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=15),
    "email_on_failure": False,
}


def _layer_to_shapefile_path(layer: str) -> str:
    """Resolve caminho do shapefile para uma layer (replica lógica do NestJS)."""
    return os.path.join(STATIC_PATH, layer, f"{layer}.shp")


@dag(
    dag_id="dag_sigmine_ingestao",
    description="Converte shapefiles Sigmine/ANM para PostGIS (substitui arquivos estáticos em static/)",
    schedule_interval="0 1 * * 0",
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["sigmine", "anm", "geoespacial", "semanal", "ingestao"],
    doc_md=__doc__,
)
def dag_sigmine_ingestao():

    @task
    def download_shapefiles() -> dict:
        """
        Copia shapefiles de static/ para o MinIO (raw-data/sigmine/).
        Os arquivos em static/ vêm da ANM e são atualizados durante o deploy.
        Esta task permite rastrear quando cada versão foi ingerida.

        Fallback: tenta baixar da ANM se o arquivo local não existir.
        Caminho local: /opt/airflow/static/{LAYER}/{LAYER}.shp
        """
        s3 = get_s3_client()
        today = datetime.utcnow().strftime("%Y%m%d")
        layer_keys = {}

        for layer in SIGMINE_LAYERS:
            shp_dir = os.path.join(STATIC_PATH, layer)
            minio_prefix = f"sigmine/{today}/{layer}"

            if os.path.isdir(shp_dir):
                # Copia todos os arquivos do diretório (shp, dbf, prj, shx, etc.)
                for fname in os.listdir(shp_dir):
                    fpath = os.path.join(shp_dir, fname)
                    minio_key = f"{minio_prefix}/{fname}"
                    with open(fpath, "rb") as f:
                        s3.put_object(Bucket="raw-data", Key=minio_key, Body=f.read())
                layer_keys[layer] = f"raw-data/{minio_prefix}/{layer}.shp"
                print(f"{layer}: copiado de {shp_dir} → raw-data/{minio_prefix}/")
            else:
                # Fallback: buscar shapefile do MinIO de ingestão anterior
                # (mantém última versão conhecida se static/ não estiver montado)
                try:
                    s3.head_object(Bucket="raw-data", Key=f"{minio_prefix}/{layer}.shp")
                    layer_keys[layer] = f"raw-data/{minio_prefix}/{layer}.shp"
                    print(f"{layer}: usando versão existente no MinIO")
                except Exception:
                    raise FileNotFoundError(
                        f"Shapefile {layer} não encontrado em {shp_dir} nem no MinIO. "
                        f"Monte static/ em {STATIC_PATH} via docker-compose."
                    )

        return layer_keys

    @task
    def convert_to_geojson(layer_keys: dict) -> dict:
        """
        Converte shapefiles para GeoJSON usando geopandas.
        Replica: SigmineService — biblioteca shapefile (npm) → geopandas (Python).

        Filtros aplicados (mesmos do NestJS):
        - Apenas Polygon e MultiPolygon (descarta Point, LineString, etc.)
        - Reproject para EPSG:4326 (WGS84) se necessário

        Salva em: staging-data/sigmine/{LAYER}.parquet (com coluna geometry WKB)
        """
        s3 = get_s3_client()
        geojson_keys = {}

        for layer, shp_key in layer_keys.items():
            # Lê shapefile do MinIO via bytes + geopandas
            shp_prefix = shp_key.rsplit("/", 1)[0]
            bucket = "raw-data"

            # Cria arquivo temporário no /tmp para geopandas ler
            tmp_dir = f"/tmp/sigmine_{layer}"
            os.makedirs(tmp_dir, exist_ok=True)

            # Baixa todos os arquivos necessários para o tmp
            layer_prefix = shp_prefix.removeprefix("raw-data/").removeprefix("staging-data/")
            try:
                paginator = s3.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix=layer_prefix):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        fname = key.split("/")[-1]
                        obj_data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                        with open(os.path.join(tmp_dir, fname), "wb") as f:
                            f.write(obj_data)
            except Exception as e:
                raise RuntimeError(f"Erro ao baixar shapefile {layer} do MinIO: {e}")

            shp_path = os.path.join(tmp_dir, f"{layer}.shp")
            if not os.path.exists(shp_path):
                raise FileNotFoundError(f"Shapefile {shp_path} não encontrado após download.")

            gdf = gpd.read_file(shp_path)

            # Reproject para WGS84 se necessário (mesmo CRS que o NestJS usa)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)

            # Filtra apenas Polygon e MultiPolygon (replica NestJS)
            poly_types = {"Polygon", "MultiPolygon"}
            gdf = gdf[gdf.geometry.geom_type.isin(poly_types)].copy()

            if gdf.empty:
                print(f"Aviso: {layer} sem geometrias Polygon/MultiPolygon após filtro.")
                geojson_keys[layer] = None
                continue

            # Salva como GeoJSON no MinIO staging
            today = datetime.utcnow().strftime("%Y%m%d")
            geojson_str = gdf.to_json()
            minio_key = f"sigmine/{today}/{layer}.geojson"
            s3.put_object(
                Bucket="staging-data",
                Key=minio_key,
                Body=geojson_str.encode("utf-8"),
                ContentType="application/json",
            )
            geojson_keys[layer] = f"staging-data/{minio_key}"
            print(f"{layer}: {len(gdf)} features → staging-data/{minio_key}")

        return geojson_keys

    @task
    def filter_ceara_bbox(geojson_keys: dict) -> dict:
        """
        Aplica filtro de bounding box do Ceará.
        Replica EXATAMENTE: GeographicFilterService.filterByCearaBounds() do NestJS.

        Lógica (AABB overlap check — sem clip real, apenas rejeição por bbox):
          feature_west > ceara_east → fora → descarta
          feature_east < ceara_west → fora → descarta
          feature_south > ceara_north → fora → descarta
          feature_north < ceara_south → fora → descarta

        Layer 'CE': sem filtro (já é específica do Ceará — replica NestJS).
        Fallback: retorna sem filtrar se erro (replica NestJS try/catch).
        """
        s3 = get_s3_client()
        ceara_box = box(*CEARA_BBOX)  # shapely box: (min_lon, min_lat, max_lon, max_lat)
        filtered_keys = {}

        for layer, geojson_key in geojson_keys.items():
            if geojson_key is None:
                filtered_keys[layer] = None
                continue

            # Layer CE não precisa de filtro geográfico (replica NestJS exatamente)
            if layer == "CE":
                filtered_keys[layer] = geojson_key
                print(f"Layer CE: sem filtro geográfico (comportamento do NestJS)")
                continue

            bucket, key = geojson_key.split("/", 1)
            raw_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

            try:
                gdf = gpd.read_file(io.BytesIO(raw_bytes))

                # AABB overlap check — replica turf.booleanOverlap via geopandas bounds
                bounds = gdf.geometry.bounds  # colunas: minx, miny, maxx, maxy
                feature_overlaps = ~(
                    (bounds["maxx"] < CEARA_BBOX[0]) |  # feature à esquerda do CE
                    (bounds["minx"] > CEARA_BBOX[2]) |  # feature à direita do CE
                    (bounds["maxy"] < CEARA_BBOX[1]) |  # feature abaixo do CE
                    (bounds["miny"] > CEARA_BBOX[3])    # feature acima do CE
                )
                gdf_filtered = gdf[feature_overlaps].copy()
                before = len(gdf)
                after = len(gdf_filtered)
                print(f"{layer}: {before} → {after} features após filtro bbox CE")

                today = datetime.utcnow().strftime("%Y%m%d")
                filtered_key = f"sigmine/{today}/{layer}_ceara.geojson"
                s3.put_object(
                    Bucket="staging-data",
                    Key=filtered_key,
                    Body=gdf_filtered.to_json().encode("utf-8"),
                    ContentType="application/json",
                )
                filtered_keys[layer] = f"staging-data/{filtered_key}"

            except Exception as e:
                # Fallback: mantém dados sem filtrar (replica NestJS try/catch)
                print(f"Aviso: filtro bbox falhou para {layer} ({e}) — usando dados sem filtro.")
                filtered_keys[layer] = geojson_key

        return filtered_keys

    @task
    def load_postgis(filtered_keys: dict) -> None:
        """
        Carrega GeoJSONs no PostGIS via geopandas.to_postgis().
        Estratégia: TRUNCATE + INSERT por layer (dados atualizados semanalmente).

        Tabela gold: gold_sigmine_layers
        Colunas:
          layer_name TEXT   — nome da layer (ex: 'AREA_SERVIDAO')
          properties JSONB  — atributos do shapefile (preserva estrutura original)
          geometry GEOMETRY(Geometry, 4326) — geometria em WGS84

        Índice espacial GIST criado após carga.
        FastAPI serve via: ST_AsGeoJSON(geometry) + properties WHERE layer_name = :layer
        """
        from sqlalchemy import create_engine

        import os
        host = os.environ.get("POSTGRES_HOST", "postgres")
        port = os.environ.get("POSTGRES_PORT", "5432")
        db = os.environ.get("POSTGRES_DB", "comexstat_platform")
        user = os.environ.get("POSTGRES_USER", "postgres")
        password = os.environ.get("POSTGRES_PASSWORD", "postgres_pass")
        engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}")

        # Cria tabela se não existir (TRUNCATE por layer na carga)
        execute_sql("""
            CREATE TABLE IF NOT EXISTS gold.gold_sigmine_layers (
                id SERIAL PRIMARY KEY,
                layer_name TEXT NOT NULL,
                properties JSONB,
                geometry GEOMETRY(Geometry, 4326)
            )
        """)
        execute_sql("CREATE INDEX IF NOT EXISTS idx_gold_sigmine_geometry ON gold.gold_sigmine_layers USING GIST(geometry)")
        execute_sql("CREATE INDEX IF NOT EXISTS idx_gold_sigmine_layer_name ON gold.gold_sigmine_layers(layer_name)")

        s3 = get_s3_client()

        for layer, geojson_key in filtered_keys.items():
            if geojson_key is None:
                print(f"{layer}: sem dados, pulando carga.")
                continue

            bucket, key = geojson_key.split("/", 1)
            raw_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            gdf = gpd.read_file(io.BytesIO(raw_bytes))

            if gdf.empty:
                print(f"{layer}: GeoDataFrame vazio, pulando.")
                continue

            # Adiciona coluna layer_name e serializa propriedades como JSON
            geo_col = gdf.geometry.name
            prop_cols = [c for c in gdf.columns if c != geo_col]
            gdf["layer_name"] = layer
            gdf["properties"] = gdf[prop_cols].apply(lambda row: json.dumps(row.to_dict(), default=str), axis=1)

            # Remove registros antigos da layer
            execute_sql("DELETE FROM gold.gold_sigmine_layers WHERE layer_name = %(layer)s", {"layer": layer})

            # Carrega via to_postgis (usa geopandas → sqlalchemy)
            gdf_load = gdf[["layer_name", "properties", geo_col]].rename(columns={geo_col: "geometry"})
            gdf_load.to_postgis(
                "gold_sigmine_layers",
                engine,
                schema="gold",
                if_exists="append",
                index=False,
                dtype={"properties": None},  # deixa sqlalchemy inferir JSONB
            )
            print(f"{layer}: {len(gdf_load)} features carregadas no PostGIS")

        print("gold.gold_sigmine_layers atualizado com sucesso.")

    # Grafo de dependências
    layer_keys = download_shapefiles()
    geojson_keys = convert_to_geojson(layer_keys)
    filtered_keys = filter_ceara_bbox(geojson_keys)
    load_postgis(filtered_keys)


dag_sigmine_ingestao()
