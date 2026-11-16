"""Parser interface and registry (Strategy + Registry).

Adding a format (GPX, TCX) means subclassing ActivityParser and registering it;
nothing else in the package changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from fit_render.domain import Activity
from fit_render.errors import ActivityParseError, UnsupportedFileError


class ActivityParser(ABC):
    """Translates one file format into an Activity."""

    extensions: ClassVar[tuple[str, ...]]

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def parse(self, path: Path) -> Activity:
        if not path.is_file():
            raise ActivityParseError(f"File not found: {path}")
        activity = self._parse(path)
        if not activity.records:
            raise ActivityParseError(f"{path.name} contains no timestamped records.")
        return activity

    @abstractmethod
    def _parse(self, path: Path) -> Activity:
        """Format-specific parsing. Must return records sorted by timestamp."""


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: list[ActivityParser] = []

    def register(self, parser: ActivityParser) -> None:
        self._parsers.append(parser)

    def for_path(self, path: Path) -> ActivityParser:
        for parser in self._parsers:
            if parser.supports(path):
                return parser
        known = sorted({ext for p in self._parsers for ext in p.extensions})
        raise UnsupportedFileError(
            f"Unsupported file type {path.suffix!r}; supported: {', '.join(known)}"
        )
