"""Ingest unit: turn activity files into domain Activity objects."""

from pathlib import Path

from fit_render.domain import Activity
from fit_render.ingest.base import ActivityParser, ParserRegistry
from fit_render.ingest.fit import FitParser

default_registry = ParserRegistry()
default_registry.register(FitParser())


def load_activity(path: Path, registry: ParserRegistry = default_registry) -> Activity:
    return registry.for_path(path).parse(path)


__all__ = ["ActivityParser", "FitParser", "ParserRegistry", "default_registry", "load_activity"]
