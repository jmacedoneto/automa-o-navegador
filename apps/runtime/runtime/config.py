from pydantic_settings import BaseSettings


class RuntimeSettings(BaseSettings):
    api_base_url: str = "http://localhost:8000"
    max_fallback_attempts: int = 2
    fallback_pause_when_failure: bool = True
    fallback_timeout_seconds: int = 20
    chrome_profile_dir: str = ".runtime-profile"
    chrome_headless: bool = False
    chrome_viewport_width: int = 1280
    chrome_viewport_height: int = 720
    poll_interval_seconds: float = 3.0
