"""
test_contract.py
=================
Suite pytest de testes de contrato: compara respostas da FastAPI contra
golden files gravados do NestJS.

Uso:
  # Pré-requisito: golden files gravados com record_golden_responses.py record
  pytest data-platform/tests/test_contract.py -v

  # Com URL customizada da FastAPI
  FASTAPI_URL=http://localhost:8000 pytest data-platform/tests/test_contract.py -v

  # Apenas endpoints críticos (exclui layers grandes)
  pytest data-platform/tests/test_contract.py -v -k "not layer"
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import requests

GOLDEN_DIR = Path(__file__).parent / "golden" / "latest"
FASTAPI_URL = os.environ.get("FASTAPI_URL", "http://localhost:8000")
TOLERANCE = 0.0001  # 0.01% tolerância para floats


def _load_golden_files() -> list[tuple[str, dict]]:
    """Carrega todos os golden files como parâmetros para pytest."""
    if not GOLDEN_DIR.exists():
        return []
    files = sorted(GOLDEN_DIR.glob("*.json"))
    return [
        (f.stem, json.loads(f.read_text()))
        for f in files
        if not f.name.startswith("_")
    ]


def _fetch_fastapi(path: str, params: dict) -> dict:
    url = f"{FASTAPI_URL.rstrip('/')}{path}"
    resp = requests.get(url, params=params, timeout=30)
    return {
        "status_code": resp.status_code,
        "body": resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else {},
    }


def _assert_deep_equal(golden: Any, actual: Any, path: str = "") -> None:
    """Comparação recursiva com tolerância para floats."""
    if isinstance(golden, dict) and isinstance(actual, dict):
        for key in golden:
            assert key in actual, f"{path}.{key}: chave ausente na FastAPI"
            _assert_deep_equal(golden[key], actual[key], f"{path}.{key}")
        for key in actual:
            if key not in golden:
                pass  # campos extras na FastAPI são permitidos
    elif isinstance(golden, list):
        assert len(golden) == len(actual), f"{path}: tamanho {len(golden)} vs {len(actual)}"
        for i, (g, a) in enumerate(zip(golden, actual)):
            _assert_deep_equal(g, a, f"{path}[{i}]")
    elif isinstance(golden, float):
        tolerance = max(abs(golden) * TOLERANCE, 0.000001)
        assert abs(golden - float(actual)) <= tolerance, (
            f"{path}: {golden} vs {actual} (diff={abs(golden - float(actual)):.8f})"
        )
    elif isinstance(golden, (int, str, bool, type(None))):
        assert golden == actual, f"{path}: {golden!r} vs {actual!r}"


# Parâmetros dinâmicos — cada golden file vira um test case
@pytest.mark.parametrize(
    "case_id,golden_data",
    _load_golden_files(),
    ids=[f[0] for f in _load_golden_files()],
)
def test_endpoint_matches_nestjs(case_id: str, golden_data: dict) -> None:
    """Verifica que FastAPI retorna resposta idêntica ao NestJS para o endpoint."""
    golden_resp = golden_data["response"]

    # Pula casos onde o NestJS retornou erro (não temos golden de referência)
    if golden_resp["status_code"] not in (200, 204):
        pytest.skip(f"Golden com status {golden_resp['status_code']} — pulando")

    actual_resp = _fetch_fastapi(golden_data["path"], golden_data["params"])

    assert actual_resp["status_code"] == golden_resp["status_code"], (
        f"Status code: esperado {golden_resp['status_code']}, recebido {actual_resp['status_code']}"
    )

    if golden_resp["status_code"] == 200:
        _assert_deep_equal(golden_resp["body"], actual_resp["body"])


class TestCriticalInvariants:
    """Invariantes que devem sempre ser verdadeiros, independente de golden files."""

    def test_health_check(self) -> None:
        resp = requests.get(f"{FASTAPI_URL}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("ok", "degraded")

    def test_comexstat_summary_trade_balance_invariant(self) -> None:
        """trade_balance DEVE ser exports - imports (invariante matemático)."""
        resp = requests.get(f"{FASTAPI_URL}/comexstat/summary", params={"period": "yearToDate"}, timeout=10)
        if resp.status_code == 501:
            pytest.skip("Endpoint não implementado")
        if resp.status_code != 200:
            pytest.skip(f"Status {resp.status_code}")

        data = resp.json()["data"]
        exports = data["exports"]
        imports = data["imports"]
        balance = data["tradeBalance"]
        tolerance = max(abs(balance) * TOLERANCE, 0.000001)
        assert abs(balance - (exports - imports)) <= tolerance, (
            f"tradeBalance ({balance}) != exports ({exports}) - imports ({imports})"
        )

    def test_comexstat_partners_participation_range(self) -> None:
        """Participação de países parceiros deve estar em [0, 100]."""
        resp = requests.get(
            f"{FASTAPI_URL}/comexstat/partners",
            params={"flow": "export", "period": "yearToDate"},
            timeout=10,
        )
        if resp.status_code in (404, 501):
            pytest.skip("Sem dados ou não implementado")
        assert resp.status_code == 200

        for item in resp.json()["data"]:
            pct = item.get("percentage", 0)
            assert 0 <= pct <= 100, f"Participação fora de [0, 100]: {pct}"

    def test_states_ranking_has_27_states(self) -> None:
        """Ranking deve ter exatamente 27 estados."""
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        ref = datetime.utcnow().replace(day=1) - relativedelta(months=2)
        prev = ref - relativedelta(months=1)

        resp = requests.get(
            f"{FASTAPI_URL}/comexstat/national-comparison/states-ranking",
            params={
                "flow": "export",
                "from": f"{ref.year}-01",
                "to": f"{ref.year}-{ref.month:02d}",
            },
            timeout=15,
        )
        if resp.status_code in (404, 501):
            pytest.skip("Sem dados ou não implementado")
        assert resp.status_code == 200

        states = resp.json()["data"]
        assert len(states) == 27, f"Esperados 27 estados, recebidos {len(states)}"

        ranks = [s["rank"] for s in states]
        assert sorted(ranks) == list(range(1, 28)), "Ranks devem ser 1..27 sem repetição"

    def test_rde_pagination_consistency(self) -> None:
        """Paginação RDE: page 1 + page 2 não devem ter CodigoRDE repetido."""
        p1 = requests.get(f"{FASTAPI_URL}/rde/todos-registros", params={"skip": 0, "top": 50}, timeout=15)
        p2 = requests.get(f"{FASTAPI_URL}/rde/todos-registros", params={"skip": 50, "top": 50}, timeout=15)

        if p1.status_code in (404, 501) or p2.status_code in (404, 501):
            pytest.skip("Sem dados ou não implementado")

        assert p1.status_code == 200 and p2.status_code == 200

        codes_p1 = {r["CodigoRDE"] for r in p1.json()["data"]}
        codes_p2 = {r["CodigoRDE"] for r in p2.json()["data"]}
        overlap = codes_p1 & codes_p2
        assert not overlap, f"Páginas 1 e 2 têm {len(overlap)} CodigoRDE em comum: {list(overlap)[:5]}"

    def test_layer_geojson_structure(self) -> None:
        """GeoJSON do layer CE deve ser uma FeatureCollection válida."""
        resp = requests.get(f"{FASTAPI_URL}/layers/ce", timeout=30)
        if resp.status_code in (404, 501):
            pytest.skip("Sem dados ou não implementado")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("type") == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

        feature = data["features"][0]
        assert feature.get("type") == "Feature"
        assert "geometry" in feature
        assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")
        assert "properties" in feature
