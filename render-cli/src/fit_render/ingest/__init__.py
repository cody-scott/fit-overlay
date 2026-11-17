"""Ingest unit: turn activity files into domain Activity objects."""

from collections.abc import Sequence
from pathlib import Path

from fit_render.domain import Activity
from fit_render.ingest.base import ActivityParser, ParserRegistry
from fit_render.ingest.corrections import (
    DEFAULT_CORRECTIONS,
    ActivityCorrection,
    SpeedFromDistance,
    apply_corrections,
)
from fit_render.ingest.fit import FitParser

default_registry = ParserRegistry()
default_registry.register(FitParser())


def load_activity(
    path: Path,
    registry: ParserRegistry = default_registry,
    corrections: Sequence[ActivityCorrection] = DEFAULT_CORRECTIONS,
) -> Activity:
    """Parse a file, then repair known data defects (see Activity.notes)."""
    return apply_corrections(registry.for_path(path).parse(path), corrections)


__all__ = [
    "DEFAULT_CORRECTIONS",
    "ActivityCorrection",
    "ActivityParser",
    "FitParser",
    "ParserRegistry",
    "SpeedFromDistance",
    "apply_corrections",
    "default_registry",
    "load_activity",
]
