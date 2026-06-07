"""
models/sigmine.py — DTOs GeoJSON do domínio Sigmine (camadas geoespaciais).
===========================================================================
Estrutura GeoJSON padrão (RFC 7946): FeatureCollection → Feature → geometry.
geometry e properties permanecem livres (dict) por serem específicos por feição.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any]


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]
