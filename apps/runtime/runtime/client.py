class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def runs_url(self, run_id: str) -> str:
        return f"{self.base_url}/api/runs/{run_id}"
