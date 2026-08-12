import pytest
from pydantic import BaseModel

from app.automation.schemas import (
    SchemaRegistrar,
    SchemaNotFoundError,
    get_schema,
    list_schemas,
)
from app.automation.schemas.cotacao_pvs import ResultadoCotacao


def test_schema_registrar_register_and_get():
    class MySchema(BaseModel):
        x: int

    reg = SchemaRegistrar()
    reg.register("my_schema", MySchema)
    assert reg.get("my_schema") is MySchema


def test_get_schema_falls_back_to_module_registry():
    cls = get_schema("ResultadoCotacao")
    assert cls is ResultadoCotacao


def test_get_schema_raises_on_unknown():
    with pytest.raises(SchemaNotFoundError, match="does_not_exist"):
        get_schema("does_not_exist")


def test_list_schemas_includes_builtins():
    names = list_schemas()
    assert "ResultadoCotacao" in names


def test_resultado_cotacao_schema_fields():
    fields = ResultadoCotacao.model_fields.keys()
    assert set(fields) >= {"valor_total", "prazo_meses", "status"}


def test_resultado_cotacao_validates_payload():
    payload = {"valor_total": 100.0, "prazo_meses": 12, "status": "ok"}
    obj = ResultadoCotacao(**payload)
    assert obj.valor_total == 100.0
    assert obj.status == "ok"


def test_resultado_cotacao_rejects_unknown_status():
    with pytest.raises(ValueError):
        ResultadoCotacao(valor_total=100.0, prazo_meses=12, status="nope")
