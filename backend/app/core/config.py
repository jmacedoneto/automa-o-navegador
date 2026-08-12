from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    REDIS_URL: str = "redis://autopilot_redis:6379"
    BROWSERLESS_URL: str = ""
    BROWSERLESS_TOKEN: str = ""
    OPENAI_API_KEY: str = ""
    EVOLUTION_API_URL: str = ""
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_INSTANCE: str = ""
    NODE_ENV: str = "production"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
