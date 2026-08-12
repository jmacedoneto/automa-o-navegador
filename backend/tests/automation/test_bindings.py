from app.automation.bindings import interpolate
from app.automation.models import RunContext


def test_interpolate_simple_binding():
    ctx = RunContext(inputs={"nome": "Ana"}, bindings={"valor": 100})
    assert interpolate("Olá {{input.nome}}", ctx) == "Olá Ana"
    assert interpolate("R$ {{valor}}", ctx) == "R$ 100"


def test_interpolate_nested_binding():
    ctx = RunContext(inputs={"cliente": {"doc": "123"}}, bindings={})
    assert interpolate("{{input.cliente.doc}}", ctx) == "123"


def test_interpolate_in_dict_and_list():
    ctx = RunContext(inputs={"a": 1}, bindings={"b": 2})
    assert interpolate({"k": "{{a}}", "n": ["{{b}}", 3]}, ctx) == {"k": "1", "n": ["2", 3]}


def test_interpolate_missing_key_returns_default_marker():
    ctx = RunContext(inputs={}, bindings={})
    out = interpolate("valor={{missing}}", ctx, missing_marker="???")
    assert out == "valor=???"


def test_interpolate_keeps_non_strings():
    assert interpolate(42, RunContext()) == 42
    assert interpolate(None, RunContext()) is None
    assert interpolate(True, RunContext()) is True
