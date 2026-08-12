"""Outer-loop driver for the cotação PVS flow.

Reads `veiculos_referencia.json`, builds the cartesian product of
(vehicle × region) combos, and dispatches one Celery task per combo via
the NavRunner v2 dispatcher. Each combo is one full DSL run with the
`input.combos` list narrowed to a single element.

Why one DSL run per combo (not one DSL run with all combos):
- A combo can fail independently (FIPE rejected, model not loaded, etc.).
  Per-combo runs give us per-combo retry + per-combo step logs.
- Each combo writes to a unique row in `cotacoes_fipe` (filter by faixa+tipo+regiao).
"""
import json
from pathlib import Path
from typing import Any

from app.workers.tasks import run_automation_v2


STEPS_PATH = Path(__file__).parent / "steps.json"
DASHBOARD_URL = "https://app.apvs.vc/dashboard"


def load_veiculos_referencia(path: Path | None = None) -> list[dict]:
    """Load the FIPE vehicle reference list.

    Default path is `cotacao_pvs/veiculos_referencia.json` (the legacy output).
    """
    p = path or (Path(__file__).parent / "veiculos_referencia.json")
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def build_combos(veiculos: list[dict], regioes: dict[str, str]) -> list[dict]:
    """Cartesian product of (vehicle × region). Each combo has all fields
    the DSL needs to drive one quotation."""
    combos = []
    for v in veiculos:
        for regiao_slug, cidade in regioes.items():
            combos.append({
                "fipe_code": v.get("codigo_fipe"),
                "faixa_min": v["faixa_min"],
                "faixa_max": v["faixa_max"],
                "tipo": v["tipo"],
                "regiao": regiao_slug,
                "cidade": cidade,
                "dashboard_url": DASHBOARD_URL,
            })
    return combos


def filter_combos(combos: list[dict]) -> list[dict]:
    """Drop combos without a FIPE code (the legacy output marks them with
    `codigo_fipe: null` and a `nota` field)."""
    return [c for c in combos if c.get("fipe_code")]


async def executar_cotacao_pvs(
    veiculos_path: Path | None = None,
    credentials: dict[str, Any] | None = None,
    supabase_key: str = "",
    estado: str = "BA",
    regioes: dict[str, str] | None = None,
    automation_name: str = "cotacao_pvs",
) -> dict[str, Any]:
    """Dispatch one Celery task per combo.

    Returns a summary dict with `total_combos` and `dispatched` counts.
    """
    credentials = credentials or {}
    regioes = regioes or {"capital": "Salvador"}

    veiculos = load_veiculos_referencia(veiculos_path)
    combos = filter_combos(build_combos(veiculos, regioes))

    steps_payload = json.loads((STEPS_PATH).read_text(encoding="utf-8"))

    dispatched = 0
    for combo in combos:
        inputs = {
            "cnpj": credentials.get("apvs_login", {}).get("user", ""),
            "password": credentials.get("apvs_login", {}).get("pass", ""),
            "supabase_key": supabase_key,
            "estado": estado,
            "combos": [combo],  # one combo per run
        }
        run_automation_v2.delay(
            automation_name=automation_name,
            steps_payload=steps_payload["steps"],
            inputs=inputs,
        )
        dispatched += 1

    return {"total_combos": len(combos), "dispatched": dispatched}
