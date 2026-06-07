"""
models/scm.py — DTOs do domínio SCM (Cadastro Mineiro / ANM).
=============================================================
Vários endpoints SCM retornam linhas cruas das tabelas raw (colunas variáveis);
para esses, mantemos dict[str, Any]. Os agregados gold têm forma estável.
"""

from __future__ import annotations

from typing import Any

from .common import CamelModel


class ScmHealth(CamelModel):
    status: str
    counts: dict[str, int]


class ScmAnalyticsByUf(CamelModel):
    uf: str | None = None
    total_processos: int
    area_total_ha: float | None = None


# Linhas cruas (raw.*) — colunas dependem do schema da tabela.
ScmRow = dict[str, Any]
