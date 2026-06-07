"""
responses.py — Envelope de resposta padrão.
============================================
Preserva exatamente o contrato do NestJS: {"success": true, "data": ...}.
Campos adicionais (total, skip, top) são incluídos no nível superior.
"""

from __future__ import annotations

from typing import Any


def success(data: Any, **kwargs) -> dict:
    """Envelope de resposta padrão — mesma estrutura do NestJS."""
    return {"success": True, "data": data, **kwargs}
