"""Schemas for the cotação PVS flow."""
from typing import Literal

from pydantic import BaseModel, Field

from app.automation.schemas._base import register


class ResultadoCotacao(BaseModel):
    """The cheapest plan + meta extracted from the APVS cotação plans screen."""

    valor_total: float = Field(..., description="Valor da menor parcela em R$")
    prazo_meses: int = Field(..., description="Prazo em meses")
    status: Literal["ok", "rejeitado", "revisao"] = Field(..., description="Status da cotação")
    motivo_rejeicao: str | None = Field(None, description="Preenchido quando status != 'ok'")


register("ResultadoCotacao", ResultadoCotacao)
