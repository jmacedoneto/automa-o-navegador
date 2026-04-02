from pydantic_settings import BaseSettings


class RuntimeSettings(BaseSettings):
    api_base_url: str = "http://localhost:8000"
    max_fallback_attempts: int = 2
