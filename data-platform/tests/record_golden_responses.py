"""
record_golden_responses.py
===========================
Grava as respostas do NestJS (API atual) como "golden files" para servir
de referência na validação da FastAPI (nova API).

Uso:
  # 1. Gravar respostas do NestJS (com API atual rodando em :3000)
  python record_golden_responses.py record --nestjs-url http://localhost:3000

  # 2. Comparar respostas da FastAPI contra golden files gravados
  python record_golden_responses.py compare --fastapi-url http://localhost:8000

  # 3. Comparar continuamente (modo shadow traffic)
  python record_golden_responses.py shadow --nestjs-url http://localhost:3000 --fastapi-url http://localhost:8000

O script grava os resultados em data-platform/tests/golden/ como JSONs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

GOLDEN_DIR = Path(__file__).parent / "golden"

# ============================================================
# Definição de todos os endpoints e suas variações de parâmetro
# ============================================================

# Períodos padrão computados pelo get_comexstat_periods()
# Atualizar manualmente ou via script para refletir referenceDate atual
PERIODS = {
    "current_month": {"from": None, "to": None},  # preenchido dinamicamente
    "year_to_date": {"from": None, "to": None},
    "last_year": {"from": None, "to": None},
}


def _get_reference_date() -> tuple[int, int]:
    """Retorna (ano, mês) do período de referência (data atual - 2 meses)."""
    from dateutil.relativedelta import relativedelta
    ref = datetime.utcnow().replace(day=1) - relativedelta(months=2)
    return ref.year, ref.month


def _build_periods() -> dict:
    from dateutil.relativedelta import relativedelta
    year, month = _get_reference_date()
    ref = datetime(year, month, 1)
    prev = ref - relativedelta(months=1)
    return {
        "current_month": {
            "from": f"{prev.year}-{prev.month:02d}",
            "to": f"{prev.year}-{prev.month:02d}",
        },
        "year_to_date": {
            "from": f"{year}-01",
            "to": f"{year}-{month:02d}",
        },
        "last_year": {
            "from": f"{year-1}-01",
            "to": f"{year-1}-12",
        },
    }


def build_test_cases() -> list[dict]:
    """Constrói todos os casos de teste — cada endpoint com variações de parâmetro."""
    periods = _build_periods()
    p_cm = periods["current_month"]
    p_ytd = periods["year_to_date"]
    p_ly = periods["last_year"]
    year, month = _get_reference_date()

    cases = [
        # ── Health ─────────────────────────────────────────────────────────
        {"id": "health", "path": "/health", "params": {}},

        # ── ComexStat Summary ──────────────────────────────────────────────
        {"id": "comexstat_summary_cm", "path": "/comexstat/summary", "params": {"period": "currentMonth"}},
        {"id": "comexstat_summary_ytd", "path": "/comexstat/summary", "params": {"period": "yearToDate"}},
        {"id": "comexstat_summary_ly", "path": "/comexstat/summary", "params": {"period": "lastYear"}},

        # ── ComexStat Summary History ──────────────────────────────────────
        {
            "id": "comexstat_summary_history",
            "path": "/comexstat/summary-history",
            "params": {"from": p_ytd["from"], "to": p_ytd["to"]},
        },

        # ── ComexStat Timeseries ───────────────────────────────────────────
        {
            "id": "comexstat_timeseries_monthly",
            "path": "/comexstat/timeseries",
            "params": {"startYear": year - 2, "endYear": year, "periodicity": "monthly", "series": "current"},
        },
        {
            "id": "comexstat_timeseries_annual",
            "path": "/comexstat/timeseries",
            "params": {"startYear": year - 5, "endYear": year, "periodicity": "annual", "series": "current"},
        },

        # ── ComexStat Partners ────────────────────────────────────────────
        {"id": "comexstat_partners_export_ytd", "path": "/comexstat/partners", "params": {"flow": "export", "period": "yearToDate"}},
        {"id": "comexstat_partners_import_ytd", "path": "/comexstat/partners", "params": {"flow": "import", "period": "yearToDate"}},
        {"id": "comexstat_partners_total_ly", "path": "/comexstat/partners", "params": {"flow": "current", "period": "lastYear"}},

        # ── ComexStat Products ────────────────────────────────────────────
        {"id": "comexstat_products_export_heading_ytd", "path": "/comexstat/products", "params": {"flow": "export", "aggregation": "heading", "period": "yearToDate"}},
        {"id": "comexstat_products_import_heading_ytd", "path": "/comexstat/products", "params": {"flow": "import", "aggregation": "heading", "period": "yearToDate"}},
        {"id": "comexstat_products_export_ncm_ytd", "path": "/comexstat/products", "params": {"flow": "export", "aggregation": "ncm", "period": "yearToDate"}},
        {"id": "comexstat_products_export_chapter_ytd", "path": "/comexstat/products", "params": {"flow": "export", "aggregation": "chapter", "period": "yearToDate"}},

        # ── ComexStat National Comparison ────────────────────────────────
        {"id": "comexstat_national_export_ytd", "path": "/comexstat/national-comparison", "params": {"flow": "export", "from": p_ytd["from"], "to": p_ytd["to"]}},
        {"id": "comexstat_national_import_ytd", "path": "/comexstat/national-comparison", "params": {"flow": "import", "from": p_ytd["from"], "to": p_ytd["to"]}},
        {"id": "comexstat_national_export_ly", "path": "/comexstat/national-comparison", "params": {"flow": "export", "from": p_ly["from"], "to": p_ly["to"]}},

        # ── ComexStat States Ranking ──────────────────────────────────────
        {"id": "comexstat_states_export_ytd", "path": "/comexstat/national-comparison/states-ranking", "params": {"flow": "export", "from": p_ytd["from"], "to": p_ytd["to"]}},
        {"id": "comexstat_states_import_ytd", "path": "/comexstat/national-comparison/states-ranking", "params": {"flow": "import", "from": p_ytd["from"], "to": p_ytd["to"]}},
        {"id": "comexstat_states_export_ly", "path": "/comexstat/national-comparison/states-ranking", "params": {"flow": "export", "from": p_ly["from"], "to": p_ly["to"]}},

        # ── ComexStat Dashboard ──────────────────────────────────────────
        {"id": "comexstat_dashboard", "path": "/comexstat/dashboard", "params": {}},

        # ── RDE ──────────────────────────────────────────────────────────
        {"id": "rde_todos_registros_p1", "path": "/rde/todos-registros", "params": {"skip": 0, "top": 100}},
        {"id": "rde_todos_registros_p2", "path": "/rde/todos-registros", "params": {"skip": 100, "top": 100}},
        {"id": "rde_registros_ied_p1", "path": "/rde/registros-ied", "params": {"skip": 0, "top": 100}},

        # ── SCM ──────────────────────────────────────────────────────────
        {"id": "scm_health", "path": "/scm/health", "params": {}},
        {"id": "scm_summary", "path": "/scm/summary", "params": {}},
        {"id": "scm_fases", "path": "/scm/fases", "params": {}},
        {"id": "scm_tipos", "path": "/scm/tipos", "params": {}},
        {"id": "scm_municipios", "path": "/scm/municipios", "params": {}},
        {"id": "scm_substancias", "path": "/scm/substancias", "params": {}},
        {"id": "scm_by_fase", "path": "/scm/analytics/by-fase", "params": {}},
        {"id": "scm_by_tipo", "path": "/scm/analytics/by-tipo", "params": {}},
        {"id": "scm_by_municipio", "path": "/scm/analytics/by-municipio", "params": {}},
        {"id": "scm_by_substancia", "path": "/scm/analytics/by-substancia", "params": {}},

        # ── Layers / Sigmine ─────────────────────────────────────────────
        {"id": "layer_ce", "path": "/layers/ce", "params": {}},
        {"id": "layer_area_servidao", "path": "/layers/area-servidao", "params": {}},
        {"id": "layer_arrendamento", "path": "/layers/arrendamento", "params": {}},
        {"id": "layer_bloqueio", "path": "/layers/bloqueio", "params": {}},
        {"id": "layer_protecao_fonte", "path": "/layers/protecao-fonte", "params": {}},
        {"id": "layer_reservas_garimpeiras", "path": "/layers/reservas-garimpeiras", "params": {}},
    ]
    return cases


# ============================================================
# Funções de request e comparação
# ============================================================

def fetch(base_url: str, path: str, params: dict, timeout: int = 90) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        return {
            "status_code": resp.status_code,
            "body": resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else resp.text,
            "latency_ms": round(resp.elapsed.total_seconds() * 1000, 1),
        }
    except requests.Timeout:
        return {"status_code": 0, "body": {"error": "timeout"}, "latency_ms": timeout * 1000}
    except Exception as e:
        return {"status_code": 0, "body": {"error": str(e)}, "latency_ms": 0}


def deep_diff(golden: Any, actual: Any, path: str = "") -> list[str]:
    """
    Compara dois valores recursivamente e retorna lista de divergências.
    Aceita tolerância de 0.01% para valores numéricos (float arithmetic).
    """
    diffs = []

    if type(golden) != type(actual):
        # Tenta conversão numérica antes de reportar divergência
        try:
            g, a = float(golden), float(actual)
            if abs(g - a) > max(abs(g) * 0.0001, 0.000001):
                diffs.append(f"{path}: type mismatch {type(golden).__name__} vs {type(actual).__name__} (golden={golden!r}, actual={actual!r})")
            return diffs
        except (TypeError, ValueError):
            diffs.append(f"{path}: type mismatch {type(golden).__name__} vs {type(actual).__name__}")
            return diffs

    if isinstance(golden, dict):
        for key in set(list(golden.keys()) + list(actual.keys())):
            if key not in golden:
                diffs.append(f"{path}.{key}: key missing in golden (actual={actual[key]!r})")
            elif key not in actual:
                diffs.append(f"{path}.{key}: key missing in actual (golden={golden[key]!r})")
            else:
                diffs.extend(deep_diff(golden[key], actual[key], f"{path}.{key}"))

    elif isinstance(golden, list):
        if len(golden) != len(actual):
            diffs.append(f"{path}: list length {len(golden)} vs {len(actual)}")
        for i, (g, a) in enumerate(zip(golden, actual)):
            diffs.extend(deep_diff(g, a, f"{path}[{i}]"))

    elif isinstance(golden, float):
        tolerance = max(abs(golden) * 0.0001, 0.000001)
        if abs(golden - actual) > tolerance:
            diffs.append(f"{path}: {golden} vs {actual} (diff={abs(golden-actual):.6f})")

    else:
        if golden != actual:
            diffs.append(f"{path}: {golden!r} vs {actual!r}")

    return diffs


# ============================================================
# Comandos principais
# ============================================================

def cmd_record(nestjs_url: str, output_dir: Path) -> None:
    """Grava respostas do NestJS como golden files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = build_test_cases()
    print(f"Gravando {len(cases)} golden files de {nestjs_url}...")

    results = {"recorded_at": datetime.utcnow().isoformat(), "nestjs_url": nestjs_url, "cases": []}
    errors = 0

    for case in cases:
        resp = fetch(nestjs_url, case["path"], case["params"])
        golden_path = output_dir / f"{case['id']}.json"
        golden_path.write_text(json.dumps({
            "case_id": case["id"],
            "path": case["path"],
            "params": case["params"],
            "response": resp,
        }, ensure_ascii=False, indent=2))

        status = "OK" if resp["status_code"] in (200, 204) else "ERROR"
        if status == "ERROR":
            errors += 1
        print(f"  [{status}] {case['id']} — {resp['status_code']} ({resp['latency_ms']}ms)")
        results["cases"].append({"id": case["id"], "status": status, "latency_ms": resp["latency_ms"]})

    summary_path = output_dir / "_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nGravados {len(cases) - errors}/{len(cases)} com sucesso → {output_dir}")


def cmd_compare(fastapi_url: str, golden_dir: Path, strict: bool = False) -> int:
    """Compara FastAPI contra golden files gravados do NestJS. Retorna 0 se OK."""
    golden_files = sorted(golden_dir.glob("*.json"))
    golden_files = [f for f in golden_files if not f.name.startswith("_")]

    if not golden_files:
        print(f"Nenhum golden file encontrado em {golden_dir}. Execute 'record' primeiro.")
        return 1

    print(f"Comparando {len(golden_files)} endpoints contra {fastapi_url}...\n")
    total_diffs = 0
    failed_cases = []

    for golden_file in golden_files:
        golden_data = json.loads(golden_file.read_text())
        case_id = golden_data["case_id"]
        path = golden_data["path"]
        params = golden_data["params"]
        golden_resp = golden_data["response"]

        actual_resp = fetch(fastapi_url, path, params)

        # Status code deve coincidir
        if golden_resp["status_code"] != actual_resp["status_code"]:
            print(f"  [FAIL] {case_id}: status {golden_resp['status_code']} → {actual_resp['status_code']}")
            failed_cases.append(case_id)
            total_diffs += 1
            continue

        if golden_resp["status_code"] != 200:
            print(f"  [SKIP] {case_id}: status {golden_resp['status_code']} (ambos não-200)")
            continue

        # Comparação deep de corpo JSON
        diffs = deep_diff(golden_resp["body"], actual_resp["body"])

        if diffs:
            print(f"  [FAIL] {case_id} ({actual_resp['latency_ms']}ms): {len(diffs)} divergência(s)")
            for d in diffs[:5]:  # mostra só as 5 primeiras
                print(f"         {d}")
            if len(diffs) > 5:
                print(f"         ... +{len(diffs) - 5} mais")
            failed_cases.append(case_id)
            total_diffs += len(diffs)
        else:
            print(f"  [OK]   {case_id} ({actual_resp['latency_ms']}ms)")

    print(f"\n{'='*60}")
    print(f"Resultado: {len(golden_files) - len(failed_cases)}/{len(golden_files)} endpoints OK")
    if total_diffs:
        print(f"Total de divergências: {total_diffs}")
        print(f"Falhas: {', '.join(failed_cases)}")
        return 1
    else:
        print("Zero divergências — FastAPI está compatível com NestJS!")
        return 0


def cmd_shadow(nestjs_url: str, fastapi_url: str, interval_minutes: int = 15) -> None:
    """Modo shadow: compara periodicamente NestJS vs FastAPI."""
    golden_dir = GOLDEN_DIR / "shadow"
    print(f"Shadow mode: comparando a cada {interval_minutes}min")
    print(f"  NestJS:  {nestjs_url}")
    print(f"  FastAPI: {fastapi_url}")
    print("  Ctrl+C para parar.\n")

    iteration = 0
    while True:
        iteration += 1
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        print(f"\n{'='*60}")
        print(f"Iteração {iteration} — {ts}")
        print(f"{'='*60}")

        # Grava snapshot atual do NestJS
        iter_dir = golden_dir / ts
        cmd_record(nestjs_url, iter_dir)

        # Compara FastAPI
        result = cmd_compare(fastapi_url, iter_dir)

        if result != 0:
            print(f"\n⚠️  Divergências encontradas! Log salvo em {iter_dir}")

        print(f"\nPróxima verificação em {interval_minutes} minutos...")
        try:
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\nShadow mode encerrado.")
            break


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Testes de contrato: NestJS (golden) vs FastAPI (actual)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # record
    p_record = sub.add_parser("record", help="Grava respostas do NestJS como golden files")
    p_record.add_argument("--nestjs-url", default="http://localhost:3000", help="URL base do NestJS")
    p_record.add_argument("--output-dir", type=Path, default=GOLDEN_DIR / "latest", help="Diretório de saída")

    # compare
    p_compare = sub.add_parser("compare", help="Compara FastAPI contra golden files")
    p_compare.add_argument("--fastapi-url", default="http://localhost:8000", help="URL base da FastAPI")
    p_compare.add_argument("--golden-dir", type=Path, default=GOLDEN_DIR / "latest", help="Diretório com golden files")
    p_compare.add_argument("--strict", action="store_true", help="Falha em qualquer divergência (padrão: tolerância 0.01%)")

    # shadow
    p_shadow = sub.add_parser("shadow", help="Compara continuamente NestJS vs FastAPI")
    p_shadow.add_argument("--nestjs-url", default="http://localhost:3000")
    p_shadow.add_argument("--fastapi-url", default="http://localhost:8000")
    p_shadow.add_argument("--interval", type=int, default=15, help="Intervalo em minutos (padrão: 15)")

    args = parser.parse_args()

    if args.command == "record":
        cmd_record(args.nestjs_url, args.output_dir)
    elif args.command == "compare":
        sys.exit(cmd_compare(args.fastapi_url, args.golden_dir, strict=args.strict))
    elif args.command == "shadow":
        cmd_shadow(args.nestjs_url, args.fastapi_url, args.interval)


if __name__ == "__main__":
    main()
