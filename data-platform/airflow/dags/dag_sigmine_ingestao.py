"""
dag_sigmine_ingestao.py
========================
Substitui: SigmineService — leitura de shapefiles estáticos em static/.

Problema atual (NestJS):
  - Shapefiles em static/ são ESTÁTICOS — sem atualização automática
  - Dados ficam desatualizados até o próximo deploy
  - GeographicFilterService usa bounding box (não intersecção exata) — simplificação mantida

Fluxo novo (Airflow, semanal):
  download_shapefiles → convert_to_geojson → filter_ceara_bbox → load_postgis

Layers processadas (mesmas do NestJS):
  AREA_SERVIDAO, ARRENDAMENTO, BLOQUEIO, CE, PROTECAO_FONTE, RESERVAS_GARIMPEIRAS
"""

from __future__ import annotations

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

ANM_SIGMINE_BASE = "https://app.anm.gov.br/dadosabertos/SIGMINE"

# Layers do Sigmine (mesmas de SigmineLayer enum no NestJS)
SIGMINE_LAYERS = [
    "AREA_SERVIDAO",
    "ARRENDAMENTO",
    "BLOQUEIO",
    "CE",
    "PROTECAO_FONTE",
    "RESERVAS_GARIMPEIRAS",
]

# Bounding box do Ceará (usado em GeographicFilterService.createCearaBoundingPolygon())
# Replicado de static/geojs-23-mun.json — código IBGE 23
CEARA_BBOX = {
    "min_lon": -41.5,
    "max_lon": -37.25,
    "min_lat": -7.87,
    "max_lat": -2.78,
}

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}


@dag(
    dag_id="dag_sigmine_ingestao",
    description="Baixa shapefiles Sigmine/ANM e carrega no PostGIS (substitui arquivos estáticos em static/)",
    schedule_interval="0 1 * * 0",  # semanal, domingos à 1h BRT
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
        Baixa os 6 shapefiles do Sigmine/ANM para o MinIO.
        Substitui os arquivos estáticos em static/{LAYER}/{LAYER}.shp

        Cada layer possui 4 arquivos: .shp, .dbf, .shx, .prj

        TODO: verificar URL exata dos shapefiles na ANM (podem estar em ZIP por layer).
        Salvar em: raw-data/sigmine/ano=YYYY/semana=WW/{LAYER}.zip
        """
        layer_keys = {}
        for layer in SIGMINE_LAYERS:
            minio_key = f"raw-data/sigmine/{layer}.zip"
            # TODO: implementar download
            # url = f"{ANM_SIGMINE_BASE}/{layer}/{layer}.zip"
            # response = requests.get(url, timeout=120, verify=False)
            # s3.put_object(Bucket='raw-data', Key=minio_key, Body=response.content)
            print(f"TODO: download shapefile {layer} → {minio_key}")
            layer_keys[layer] = minio_key

        return layer_keys

    @task
    def convert_to_geojson(layer_keys: dict) -> dict:
        """
        Converte shapefiles para GeoJSON usando fiona/geopandas ou ogr2ogr.
        Replica: SigmineService — biblioteca shapefile do NestJS → Python equivalente.

        Formato de saída: FeatureCollection GeoJSON padrão.
        Filtro: apenas geometrias Polygon e MultiPolygon (replica o NestJS:
          geometry.type !== 'Polygon' && geometry.type !== 'MultiPolygon' → descartado)

        TODO: usar geopandas para leitura do shapefile e exportação GeoJSON.
        Salvar em: staging-data/sigmine/{LAYER}.geojson
        """
        geojson_keys = {}
        for layer, zip_key in layer_keys.items():
            geojson_key = f"staging-data/sigmine/{layer}.geojson"
            # TODO: implementar
            # import geopandas as gpd
            # gdf = gpd.read_file(f"/vsitar/vsis3/raw-data/{zip_key}")
            # gdf = gdf[gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])]
            # s3.put_object(Bucket='staging-data', Key=f'sigmine/{layer}.geojson',
            #               Body=gdf.to_json())
            print(f"TODO: converter {zip_key} → {geojson_key}")
            geojson_keys[layer] = geojson_key

        return geojson_keys

    @task
    def filter_ceara_bbox(geojson_keys: dict) -> dict:
        """
        Aplica filtro geográfico de bounding box do Ceará.
        Replica EXATAMENTE: GeographicFilterService.filterByCearaBounds()

        Lógica replicada do NestJS (bounding box overlap check):
          featureBbox[2] < cearaBbox[0] → feature à esquerda do CE → descarta
          featureBbox[0] > cearaBbox[2] → feature à direita do CE → descarta
          featureBbox[3] < cearaBbox[1] → feature abaixo do CE → descarta
          featureBbox[1] > cearaBbox[3] → feature acima do CE → descarta

        Nota: layer 'CE' NÃO passa pelo filtro (já é específica do Ceará).
        Fallback: se filtro falhar, retorna dados sem filtrar (replica NestJS).

        TODO: implementar com geopandas + bbox intersection.
        """
        filtered_keys = {}
        for layer, geojson_key in geojson_keys.items():
            if layer == "CE":
                # Layer CE não precisa de filtro geográfico (replica NestJS)
                filtered_keys[layer] = geojson_key
                print(f"Layer CE: sem filtro geográfico")
                continue

            filtered_key = f"staging-data/sigmine/{layer}_ceara.geojson"
            # TODO: implementar filtro de bounding box
            # import geopandas as gpd
            # from shapely.geometry import box
            # gdf = gpd.read_file(geojson_key)
            # ceara_box = box(CEARA_BBOX['min_lon'], CEARA_BBOX['min_lat'],
            #                  CEARA_BBOX['max_lon'], CEARA_BBOX['max_lat'])
            # gdf_filtered = gdf[gdf.geometry.intersects(ceara_box)]
            # s3.put_object(...)
            print(f"TODO: filtrar {layer} por bbox Ceará → {filtered_key}")
            filtered_keys[layer] = filtered_key

        return filtered_keys

    @task
    def load_postgis(filtered_keys: dict) -> None:
        """
        Carrega GeoJSONs filtrados no PostGIS (PostgreSQL com extensão PostGIS).
        Estratégia: TRUNCATE + INSERT para cada layer (dados mudam semanalmente).

        Tabela gold: gold_sigmine_layers
        Colunas: layer_name (text), feature_id (serial), properties (jsonb), geometry (geometry)

        Índice espacial: CREATE INDEX USING GIST(geometry) — replica cache de shapefile do NestJS.

        TODO: usar ogr2ogr ou geopandas.to_postgis() para carregar no PostGIS.
        Executar: dbt run --select gold_sigmine_layers
        """
        for layer, geojson_key in filtered_keys.items():
            # TODO: implementar
            # import geopandas as gpd
            # from sqlalchemy import create_engine
            # gdf = gpd.read_file(geojson_key)
            # gdf['layer_name'] = layer
            # gdf.to_postgis('gold_sigmine_layers', engine, schema='gold',
            #                if_exists='append', index=False)
            print(f"TODO: carregar {layer} no PostGIS gold.gold_sigmine_layers")

        print("TODO: dbt run --select gold_sigmine_layers")
        print("Ingestão Sigmine concluída.")

    # Grafo de dependências
    layer_keys = download_shapefiles()
    geojson_keys = convert_to_geojson(layer_keys)
    filtered_keys = filter_ceara_bbox(geojson_keys)
    load_postgis(filtered_keys)


dag_sigmine_ingestao()
