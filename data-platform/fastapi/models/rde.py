"""
models/rde.py — DTOs do domínio RDE (BCB).
==========================================
PascalCase preservado exatamente como a API OData do BCB / NestJS,
para manter o contrato de resposta byte-a-byte.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RdeRecord(BaseModel):
    """Registro RDE genérico (todos-registros)."""

    model_config = ConfigDict(from_attributes=True)

    CodigoRDE: str | int | None = None
    NomePessoaNacional: str | None = None
    UfPessoaNacional: str | None = None
    NomePessoaEstrangeira: str | None = None
    PaisPessoaEstrangeira: str | None = None
    MoedaOperacao: str | None = None
    ValorOperacao: float | None = None
    Sistema: str | None = None
    Ocorrencia: str | None = None
    Modalidade: str | None = None
    Ano: int | None = None
    Mes: int | None = None


class RdeRecordIed(RdeRecord):
    """Registro RDE-IED — inclui CNPJ base da empresa receptora."""

    CnpjBaseReceptora: str | None = None
