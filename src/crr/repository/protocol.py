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

    def preflight_publish(self) -> None:
        """Prove the repository can be written to, before anything is spent (SPEC §6.1).

        `publish` is the last stage of a build, after OCR, classification and composition —
        so a repository that cannot be written to is discovered at the most expensive possible
        moment. On Drive that is not hypothetical: a service account has no storage quota of
        its own, so every upload fails `403 storageQuotaExceeded` while folder creation and
        reads keep working, and a full eight-property run costs ~$4.72 in classification before
        the first byte is refused (B-09).

        Raises `RepositoryError` when a write would fail. The default is a no-op, so an
        implementation that cannot be probed cheaply simply does not.
        """
        return None
