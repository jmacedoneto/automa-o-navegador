"""Schema registry — resolved by string name into Pydantic classes."""
from typing import Any

from pydantic import BaseModel


class SchemaNotFoundError(KeyError):
    """Raised when a schema name doesn't match any registered class."""


class SchemaRegistrar:
    """In-memory registry of {name: Pydantic class}."""

    def __init__(self) -> None:
        self._by_name: dict[str, type[BaseModel]] = {}

    def register(self, name: str, cls: type[BaseModel]) -> None:
        if not issubclass(cls, BaseModel):
            raise TypeError(f"{cls} is not a Pydantic BaseModel subclass")
        self._by_name[name] = cls

    def get(self, name: str) -> type[BaseModel]:
        if name not in self._by_name:
            raise SchemaNotFoundError(f"Schema {name!r} not registered")
        return self._by_name[name]

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())


# Module-level registry — populated by side-effect imports below.
_REGISTRY = SchemaRegistrar()


def register(name: str, cls: type[BaseModel]) -> None:
    _REGISTRY.register(name, cls)


def get_schema(name: str) -> type[BaseModel]:
    return _REGISTRY.get(name)


def list_schemas() -> list[str]:
    return _REGISTRY.names()
