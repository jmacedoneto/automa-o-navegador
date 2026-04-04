import httpx


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def runs_url(self, run_id: str) -> str:
        return f"{self.base_url}/api/runs/{run_id}"

    async def poll_next_job(self) -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(f"{self.base_url}/api/jobs/next")
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            return resp.json()

    async def report_run_status(
        self,
        run_id: str,
        status: str,
        steps_completed: int = 0,
        total_steps: int = 0,
        error: str = "",
        extracted_data: dict | None = None,
    ) -> None:
        payload: dict = {
            "status": status,
            "steps_completed": steps_completed,
            "total_steps": total_steps,
        }
        if error:
            payload["error_message"] = error
        if extracted_data:
            payload["extracted_data"] = extracted_data
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.patch(self.runs_url(run_id), json=payload)
            resp.raise_for_status()

    async def ack_job(self, job_id: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(f"{self.base_url}/api/jobs/{job_id}/ack")
            resp.raise_for_status()
