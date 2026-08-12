"""NavRunner — declarative browser automation framework."""
from app.automation.models import Step, RetryPolicy, RunContext
from app.automation.bindings import interpolate
from app.automation.retry import with_retry
from app.automation.interpreter import execute_step
from app.automation.runner import NavRunner, NavRunnerConfig, set_step_log_writer
from app.automation.auth import parse_auth, run_auth
from app.automation.credentials import resolve_credentials
from app.automation.control import run_for_each, run_if
from app.automation.run_python import run_python
from app.automation.extraction import extract_text, extract_table, screenshot
from app.automation.storage import upload_to_minio, _minio_configured
from app.automation.tracing import langfuse_span

__all__ = [
    # Core data types
    "Step", "RetryPolicy", "RunContext",
    # Bindings + retry
    "interpolate", "with_retry",
    # Interpreter + runner
    "execute_step", "NavRunner", "NavRunnerConfig", "set_step_log_writer",
    # Auth block
    "parse_auth", "run_auth",
    # Credentials resolver
    "resolve_credentials",
    # Control flow
    "run_for_each", "run_if",
    # Code escape hatch
    "run_python",
    # Extraction steps
    "extract_text", "extract_table", "screenshot",
    # Storage (MinIO upload + local fallback)
    "upload_to_minio", "_minio_configured",
    # Tracing (no-op until LANGFUSE_* env set)
    "langfuse_span",
]
