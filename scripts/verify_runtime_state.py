#!/usr/bin/env python3
"""
Helper to verify execution_runs, execution_jobs and recording_sessions status while manual
runtime/Browserless/Celery processes are running.

Usage:
  export AUTOPILOT_API_URL="http://localhost:8000/api"
  export SUPABASE_URL="https://supabase.apvsiguatemi.net"
  export SUPABASE_SERVICE_ROLE_KEY="..."
  python scripts/verify_runtime_state.py --automation-id <id>

The script posts to `/executions/automations/{id}/execute`, prints the run_id and polls the
`execution_runs` row until it leaves `queued`. Optionally it lists recent recording_sessions for
the same automation to confirm runtime_id / status transitions.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"missing environment variable {name}", file=sys.stderr)
        sys.exit(1)
    return value.rstrip("/")


def post_execution(api_url: str, automation_id: str) -> dict:
    resp = requests.post(
        f"{api_url}/executions/automations/{automation_id}/execute",
        json={"variables": {}},
        headers={"content-type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def supabase_get(table: str, supabase_url: str, service_key: str, params: dict) -> list[dict]:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    resp = requests.get(
        f"{supabase_url}/rest/v1/{table}",
        headers=headers,
        params=params,
    )
    resp.raise_for_status()
    return resp.json()


def poll_run_status(run_id: str, supabase_url: str, service_key: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    print(f"Polling execution_runs/{run_id} ...")
    while time.time() < deadline:
        rows = supabase_get(
            "execution_runs",
            supabase_url,
            service_key,
            params={"id": f"eq.{run_id}", "select": "*"},
        )
        if not rows:
            print("run row missing", file=sys.stderr)
            break
        run = rows[0]
        print(f" status={run['status']} steps={run['steps_completed']}/{run['total_steps']}")
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(3)
    print("timeout waiting for run status transition", file=sys.stderr)
    return run


def list_recordings(automation_id: str, supabase_url: str, service_key: str) -> list[dict]:
    return supabase_get(
        "recording_sessions",
        supabase_url,
        service_key,
        params={
            "automation_id": f"eq.{automation_id}",
            "order": "created_at.desc",
            "limit": 5,
            "select": "*",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify runtime job/run/recording state.")
    parser.add_argument("--automation-id", required=True)
    parser.add_argument("--skip-recordings", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    api_url = require_env("AUTOPILOT_API_URL")
    supabase_url = require_env("SUPABASE_URL")
    service_key = require_env("SUPABASE_SERVICE_ROLE_KEY")

    result = post_execution(api_url, args.automation_id)
    run_id = result.get("run_id")
    print("queued job:", result)
    if not run_id:
        print("no run_id returned", file=sys.stderr)
        sys.exit(1)

    finished_run = poll_run_status(run_id, supabase_url, service_key, timeout=args.timeout)
    print("final run state:", finished_run)

    if not args.skip_recordings:
        recordings = list_recordings(args.automation_id, supabase_url, service_key)
        print("recent recording_sessions:")
        for rec in recordings:
            print(" ", rec)


if __name__ == "__main__":
    main()
