"""
routers/layers.py — Camadas geoespaciais Sigmine (6 endpoints).
===============================================================
Substitui: src/sigmine/sigmine.controller.ts
1 SELECT PostGIS (ST_AsGeoJSON) por camada — substitui leitura de shapefile em disco.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from database import fetch_all
from models.sigmine import FeatureCollection

router = APIRouter(prefix="/layers", tags=["layers"])


async def _get_layer_geojson(layer_name: str) -> dict:
    """
    Retorna GeoJSON FeatureCollection para uma layer do Sigmine.
    Replica SigmineService.getLayer() — 1 SELECT PostGIS vs shapefile read em disco.
    """
    rows = await fetch_all(
        "SELECT ST_AsGeoJSON(geometry) as geom_json, properties "
        "FROM gold.gold_sigmine_layers WHERE layer_name = $1",
        layer_name,
    )
    if not rows:
        raise HTTPException(404, f"Layer '{layer_name}' não disponível. Execute dag_sigmine_ingestao.")

    features = []
    for r in rows:
        geom = json.loads(r["geom_json"])
        props = json.loads(r["properties"]) if isinstance(r["properties"], str) else (r["properties"] or {})
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    return {"type": "FeatureCollection", "features": features}


@router.get("/area-servidao", summary="GeoJSON Área de Servidão", response_model=FeatureCollection)
async def layer_area_servidao():
    return await _get_layer_geojson("AREA_SERVIDAO")


@router.get("/arrendamento", summary="GeoJSON Arrendamento", response_model=FeatureCollection)
async def layer_arrendamento():
    return await _get_layer_geojson("ARRENDAMENTO")


@router.get("/bloqueio", summary="GeoJSON Bloqueio", response_model=FeatureCollection)
async def layer_bloqueio():
    return await _get_layer_geojson("BLOQUEIO")


@router.get("/ce", summary="GeoJSON Processos Minerais CE", response_model=FeatureCollection)
async def layer_ce():
    return await _get_layer_geojson("CE")


@router.get("/protecao-fonte", summary="GeoJSON Proteção de Fonte", response_model=FeatureCollection)
async def layer_protecao_fonte():
    return await _get_layer_geojson("PROTECAO_FONTE")


@router.get("/reservas-garimpeiras", summary="GeoJSON Reservas Garimpeiras", response_model=FeatureCollection)
async def layer_reservas_garimpeiras():
    return await _get_layer_geojson("RESERVAS_GARIMPEIRAS")
