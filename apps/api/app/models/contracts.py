from pydantic import BaseModel


class FallbackPolicy(BaseModel):
    max_tentativas_ia: int = 2
    timeout_total_segundos: int = 20
    pausa_quando_falhar: bool = True
