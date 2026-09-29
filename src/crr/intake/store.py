"""What the reconciler needs from wherever the folders live (SPEC §18.3).

Local disk and Drive implement it (`crr.repository.intake_local`, `…intake_drive`). Every
method is scoped to one property-month, except the root summary. Nothing here deletes or
overwrites a file a person put there: the only changes to their files are renames to and from
`SUPERSEDED - ` (D-21). The system's own files — status, index, root summary — are replaced in
place.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from crr.intake.files import IntakeFile
from crr.intake.state import MonthState
from crr.models import PeriodId, Property

OUTPUT = "output"
MANIFESTS = "manifests"


class IntakeStore(Protocol):
    name: str
    #: Seconds to wait between writing the run lease and reading it back, so that a
    #: concurrent writer's write is visible (SPEC §18.9). Zero where writes are immediate.
    lease_settle_s: float

    def preflight_publish(self) -> None:
        """Prove a file can be written before anything is spent (SPEC §6.1)."""
        ...

    def list_months(self, prop: Property) -> list[PeriodId]:
        """Every month folder the property has, oldest first."""
        ...

    def ensure_month(self, prop: Property, period: PeriodId, folders: Sequence[str]) -> None:
        """Create the month folder, its component folders and `output/` where missing."""
        ...

    def list_component(self, prop: Property, period: PeriodId, folder: str) -> list[IntakeFile]:
        """The files directly inside one component folder. Empty if the folder is absent."""
        ...

    def rename(
        self, prop: Property, period: PeriodId, folder: str, file: IntakeFile, name: str
    ) -> None: ...

    def download(self, file: IntakeFile, dest: Path) -> Path: ...

    def read_state(self, prop: Property, period: PeriodId) -> MonthState | None: ...

    def write_state(self, prop: Property, period: PeriodId, state: MonthState) -> None: ...

    def read_manifest(
        self, prop: Property, period: PeriodId, version: int
    ) -> dict[str, Any] | None:
        """`output/manifests/v<version>.json`, parsed, or None."""
        ...

    def output_names(self, prop: Property, period: PeriodId) -> list[str]:
        """Names directly in `output/` (for choosing a version number that is free)."""
        ...

    def publish(
        self, prop: Property, period: PeriodId, path: Path, name: str, *, manifests: bool = False
    ) -> str:
        """Upload a build artefact into `output/` (or `output/manifests/`) under `name`.
        Never overwrites; returns the name it was actually written under."""
        ...

    def read_status(self, prop: Property, period: PeriodId) -> tuple[str, str] | None:
        """(filename, body) of the status file in `output/`, if there is one."""
        ...

    def status_name(self, prop: Property, period: PeriodId) -> str | None:
        """The status file's name in `output/`, from one listing; its body is not read."""
        ...

    def write_status(self, prop: Property, period: PeriodId, filename: str, body: str) -> bool:
        """Make `filename` the one status file, with `body`. Returns False if it already was."""
        ...

    def write_summary(self, body: str) -> bool:
        """Replace the root summary. Returns False if it already said exactly this."""
        ...

    def read_lease(self) -> str | None:
        """The run lease's text at the root, if there is one (`crr.intake.lease`)."""
        ...

    def write_lease(self, text: str) -> None:
        """Make `text` the one run lease at the root, replacing it in place."""
        ...
