"""The intake layout on local disk (SPEC §18.3) — for tests, rehearsals and `--repo local`.

Reads and writes the same tree: `<root>/<PM>/<Property>/<YYYY-MM Month>/<component>/…` and
`…/output/`. A file's modification time stands in for Drive's head-revision time; a rename does
not change it, which is the property §18.4 depends on.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crr.config.properties import PropertyRegistry
from crr.intake.files import IntakeFile
from crr.intake.state import STATE_FILE, MonthState
from crr.intake.status import ROOT_SUMMARY, is_status_filename
from crr.intake.store import MANIFESTS, OUTPUT
from crr.log import get_logger
from crr.models import PeriodId, Property
from crr.repository.protocol import RepositoryError

log = get_logger(__name__)

_PERIOD_DIR = re.compile(r"^(\d{4})-(\d{2})\b")


class LocalIntakeStore:
    name = "local"

    def __init__(self, root: Path, registry: PropertyRegistry) -> None:
        self.root = root
        self._registry = registry

    # -- layout ------------------------------------------------------------------------
    def property_dir(self, prop: Property) -> Path:
        return self.root / self._registry.manager(prop.property_manager).folder / prop.folder

    def month_dir(self, prop: Property, period: PeriodId) -> Path:
        return self.property_dir(prop) / self._registry.period_folder(period)

    def _output(self, prop: Property, period: PeriodId) -> Path:
        return self.month_dir(prop, period) / OUTPUT

    # -- IntakeStore -------------------------------------------------------------------
    def preflight_publish(self) -> None:
        probe = self.root / f".crr-preflight-{uuid.uuid4().hex}"
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe.write_bytes(b"crr")
        except OSError as exc:
            raise RepositoryError(f"cannot write to {self.root}: {exc}") from exc
        finally:
            with suppress(OSError):
                probe.unlink()

    def list_months(self, prop: Property) -> list[PeriodId]:
        base = self.property_dir(prop)
        if not base.is_dir():
            return []
        found = {
            f"{m.group(1)}-{m.group(2)}"
            for entry in base.iterdir()
            if entry.is_dir() and (m := _PERIOD_DIR.match(entry.name))
        }
        return sorted(found)

    def ensure_month(self, prop: Property, period: PeriodId, folders: Sequence[str]) -> None:
        month = self.month_dir(prop, period)
        for name in [*folders, OUTPUT]:
            (month / name).mkdir(parents=True, exist_ok=True)

    def list_component(self, prop: Property, period: PeriodId, folder: str) -> list[IntakeFile]:
        directory = self.month_dir(prop, period) / folder
        if not directory.is_dir():
            return []
        out: list[IntakeFile] = []
        for entry in sorted(directory.iterdir()):
            if not entry.is_file() or entry.name.startswith("."):
                continue
            stat = entry.stat()
            out.append(
                IntakeFile(
                    id=str(entry.relative_to(self.root)),
                    name=entry.name,
                    uploaded_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                    md5=hashlib.md5(entry.read_bytes()).hexdigest(),
                    size=stat.st_size,
                    is_pdf=entry.suffix.lower() == ".pdf",
                )
            )
        return out

    def rename(
        self, prop: Property, period: PeriodId, folder: str, file: IntakeFile, name: str
    ) -> None:
        source = self.root / file.id
        target = _free(source.parent, name)
        source.rename(target)  # rename keeps the mtime: the upload time does not move
        log.info("intake.renamed", property=prop.id, period=period, folder=folder)

    def download(self, file: IntakeFile, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.root / file.id, dest)
        return dest

    def read_state(self, prop: Property, period: PeriodId) -> MonthState | None:
        path = self._output(prop, period) / MANIFESTS / STATE_FILE
        if not path.is_file():
            return None
        return MonthState.model_validate_json(path.read_text())

    def write_state(self, prop: Property, period: PeriodId, state: MonthState) -> None:
        path = self._output(prop, period) / MANIFESTS / STATE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(state.model_dump_json(indent=2) + "\n")

    def read_manifest(
        self, prop: Property, period: PeriodId, version: int
    ) -> dict[str, Any] | None:
        path = self._output(prop, period) / MANIFESTS / f"v{version}.json"
        if not path.is_file():
            return None
        data: dict[str, Any] = json.loads(path.read_text())
        return data

    def output_names(self, prop: Property, period: PeriodId) -> list[str]:
        output = self._output(prop, period)
        return sorted(p.name for p in output.iterdir()) if output.is_dir() else []

    def publish(
        self, prop: Property, period: PeriodId, path: Path, name: str, *, manifests: bool = False
    ) -> str:
        folder = self._output(prop, period) / (MANIFESTS if manifests else "")
        folder.mkdir(parents=True, exist_ok=True)
        target = _free(folder, name)
        shutil.copy2(path, target)
        return target.name

    def read_status(self, prop: Property, period: PeriodId) -> tuple[str, str] | None:
        output = self._output(prop, period)
        if not output.is_dir():
            return None
        for entry in sorted(output.iterdir()):
            if entry.is_file() and is_status_filename(entry.name):
                return entry.name, entry.read_text()
        return None

    def status_name(self, prop: Property, period: PeriodId) -> str | None:
        output = self._output(prop, period)
        if not output.is_dir():
            return None
        names = sorted(
            e.name for e in output.iterdir() if e.is_file() and is_status_filename(e.name)
        )
        return names[0] if names else None

    def write_status(self, prop: Property, period: PeriodId, filename: str, body: str) -> bool:
        output = self._output(prop, period)
        output.mkdir(parents=True, exist_ok=True)
        existing = [e for e in output.iterdir() if e.is_file() and is_status_filename(e.name)]
        if [e.name for e in existing] == [filename] and existing[0].read_text() == body:
            return False
        for entry in existing:  # the system's own file: replaced, never kept beside the new one
            entry.unlink()
        (output / filename).write_text(body)
        return True

    def write_summary(self, body: str) -> bool:
        path = self.root / ROOT_SUMMARY
        if path.is_file() and path.read_text() == body:
            return False
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return True


def _free(folder: Path, name: str) -> Path:
    """`name`, or `name (2)` … when a file already has it. Never overwrites."""
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    n = 2
    while (folder / f"{stem} ({n}){suffix}").exists():
        n += 1
    return folder / f"{stem} ({n}){suffix}"
