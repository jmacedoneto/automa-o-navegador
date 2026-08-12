"""Pydantic schemas referenced by name in run_ai steps.

The DSL serializes a schema name (string) in run_ai.params.schema. The
runtime resolves the name to a Pydantic class via SchemaRegistrar, which
defaults to importing from domain modules in this package.
"""
from app.automation.schemas._base import SchemaRegistrar, SchemaNotFoundError, get_schema, list_schemas

__all__ = ["SchemaRegistrar", "SchemaNotFoundError", "get_schema", "list_schemas"]
