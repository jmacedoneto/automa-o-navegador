"""Pydantic schemas referenced by name in run_ai steps.

The DSL serializes a schema name (string) in run_ai.params.schema. The
runtime resolves the name to a Pydantic class via SchemaRegistrar, which
defaults to importing from domain modules in this package.

Schema registration happens at import time via side-effect imports below.
Add a new domain module by:
1. Drop `app/automation/schemas/<domain>.py` defining a Pydantic class.
2. Call `register("Name", Class)` at module bottom.
3. Add `from app.automation.schemas import <domain>  # noqa: F401` below.
"""
from app.automation.schemas._base import SchemaRegistrar, SchemaNotFoundError, get_schema, list_schemas

# Side-effect imports — populate the registry.
from app.automation.schemas import cotacao_pvs  # noqa: F401

__all__ = ["SchemaRegistrar", "SchemaNotFoundError", "get_schema", "list_schemas"]
