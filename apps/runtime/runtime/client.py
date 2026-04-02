class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
