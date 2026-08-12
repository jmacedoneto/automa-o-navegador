import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from cotacao_pvs.automacao import (
    load_veiculos_referencia,
    build_combos,
    filter_combos,
    executar_cotacao_pvs,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_load_veiculos_referencia_parses_json(tmp_path):
    p = tmp_path / "veiculos.json"
    p.write_text(json.dumps([
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "pesado", "codigo_fipe": None,
         "nota": "Nenhum veículo encontrado"},
    ]))
    out = load_veiculos_referencia(p)
    assert len(out) == 2
    assert out[0]["codigo_fipe"] == "001"


def test_load_veiculos_referencia_returns_empty_when_missing(tmp_path):
    out = load_veiculos_referencia(tmp_path / "does_not_exist.json")
    assert out == []


def test_build_combos_expands_tipos():
    veiculos = [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
        {"faixa_min": 11001, "faixa_max": 21000, "tipo": "pesado", "codigo_fipe": "002"},
    ]
    regioes = {"capital": "Salvador", "interior": "Santo Antônio de Jesus"}
    combos = build_combos(veiculos, regioes)
    assert len(combos) == 4
    for c in combos:
        assert "fipe_code" in c
        assert "cidade" in c
        assert "faixa_min" in c
        assert "faixa_max" in c
        assert "tipo" in c
        assert "regiao" in c
        assert "dashboard_url" in c


def test_filter_combos_skips_missing_fipe():
    veiculos = [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
        {"faixa_min": 11001, "faixa_max": 21000, "tipo": "pesado", "codigo_fipe": None},
    ]
    combos = build_combos(veiculos, {"capital": "Salvador"})
    filtered = filter_combos(combos)
    assert len(filtered) == 1
    assert filtered[0]["fipe_code"] == "001"


def test_executar_cotacao_pvs_dispatches_run_automation_v2(monkeypatch, tmp_path):
    """The driver calls run_automation_v2 with the loaded combos."""
    fake_delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr("cotacao_pvs.automacao.run_automation_v2", MagicMock(delay=fake_delay))

    fake_veiculos = [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
    ]
    monkeypatch.setattr("cotacao_pvs.automacao.load_veiculos_referencia", lambda p: fake_veiculos)

    result = _run(executar_cotacao_pvs(
        veiculos_path=tmp_path / "veiculos.json",
        credentials={"apvs_login": {"user": "x", "pass": "y"}},
        supabase_key="sb-key",
        estado="BA",
        regioes={"capital": "Salvador"},
        automation_name="cotacao_pvs_smoke",
    ))
    assert result["total_combos"] == 1
    assert result["dispatched"] == 1
    fake_delay.assert_called_once()
    kwargs = fake_delay.call_args.kwargs
    assert kwargs["automation_name"] == "cotacao_pvs_smoke"
    assert isinstance(kwargs["steps_payload"], list)
    assert kwargs["inputs"]["cnpj"] == "x"
    assert kwargs["inputs"]["combos"]  # list of combos


def test_executar_cotacao_pvs_wraps_auth_block_for_dispatcher(monkeypatch, tmp_path):
    """The driver wraps the top-level `auth` block so the dispatcher can detect it.

    This is the bridge between steps.json shape (auth next to steps) and the
    dispatcher's expected shape (auth as steps_payload[0]).
    """
    fake_delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr("cotacao_pvs.automacao.run_automation_v2", MagicMock(delay=fake_delay))
    monkeypatch.setattr("cotacao_pvs.automacao.load_veiculos_referencia", lambda p: [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
    ])

    # Monkey-patch STEPS_PATH to read a custom steps.json with a top-level auth block.
    auth_block = {"type": "form_login", "url": "x", "credentials_ref": "apvs_login", "selectors": {"user": "input", "pass": "input", "submit": "button"}, "success_assert": {"selector": ".ok", "timeout_ms": 5000}}
    body_step = {"id": "click_x", "click": {"selector": "button"}}
    fake_steps_json = {"auth": auth_block, "steps": [body_step]}
    import cotacao_pvs.automacao as auto_mod
    auto_mod.STEPS_PATH = tmp_path / "steps.json"
    auto_mod.STEPS_PATH.write_text(json.dumps(fake_steps_json), encoding="utf-8")

    _run(executar_cotacao_pvs(
        veiculos_path=tmp_path / "veiculos.json",
        credentials={"apvs_login": {"user": "x", "pass": "y"}},
        supabase_key="sb-key",
        estado="BA",
        regioes={"capital": "Salvador"},
        automation_name="cotacao_pvs_smoke",
    ))

    kwargs = fake_delay.call_args.kwargs
    payload = kwargs["steps_payload"]
    # First element is the auth envelope.
    assert payload[0] == {"auth": auth_block}, f"expected auth envelope as first element, got {payload[0]}"
    # Body steps follow.
    assert payload[1] == body_step
