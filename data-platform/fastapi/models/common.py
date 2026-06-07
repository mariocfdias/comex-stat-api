"""
models/common.py — Bases compartilhadas para os DTOs.
=====================================================
- CamelModel: campos em snake_case no Python, serializados em camelCase no JSON.
- Envelopes de sucesso (SuccessResponse / PaginatedResponse) replicam o NestJS.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base: aceita snake_case na construção, emite camelCase no JSON."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class SuccessResponse(BaseModel, Generic[T]):
    """Envelope padrão: {"success": true, "data": ...}."""

    success: bool = True
    data: T


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope com metadados de paginação (RDE)."""

    success: bool = True
    data: list[T]
    total: int
    skip: int
    top: int
