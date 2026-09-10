"""The source repository interface (SPEC §6.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from crr.models import BuildStatus, PeriodId, Property, SourceDocument


class RepositoryError(Exception):
    """The repository could not serve a property/period. A missing PM source is one of these
    (SPEC §6.1: a hard failure for that property)."""


class SourceRepository(Protocol):
    """Where inputs come from and where outputs go. Local disk and Drive are the two."""

    name: str

    def list_periods(self, prop: Property) -> list[PeriodId]: ...

    def fetch_inputs(
        self, prop: Property, period: PeriodId, dest: Path
    ) -> list[SourceDocument]: ...

    def publish(
        self, prop: Property, period: PeriodId, files: list[Path], status: BuildStatus
    ) -> None: ...
