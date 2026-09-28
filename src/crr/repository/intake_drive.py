"""The intake layout on Google Drive (SPEC §18.3, §18.4).

Navigation, caching and the publish preflight are the v1 repository's; this adds what
continuous intake needs: component folders, upload times that a rename cannot move, renames
to and from `SUPERSEDED - `, and the system's own files replaced in place rather than
multiplied (`update_content`), so a folder never holds two status files.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
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
from crr.repository.drive_client import PDF_MIME, DriveApi, DriveFile
from crr.repository.google_drive import GoogleDriveRepository, _unique_name
from crr.repository.protocol import RepositoryError

log = get_logger(__name__)


def parse_time(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class DriveIntakeStore(GoogleDriveRepository):
    def __init__(self, api: DriveApi, root_folder_id: str, registry: PropertyRegistry) -> None:
        super().__init__(api, root_folder_id, registry)

    # -- navigation --------------------------------------------------------------------
    def _month(
        self, prop: Property, period: PeriodId, *more: str, create: bool = False
    ) -> DriveFile | None:
        manager_folder, property_folder = self._property_path(prop)
        return self._path(
            manager_folder,
            property_folder,
            self._registry.period_folder(period),
            *more,
            create=create,
        )

    def _forget(self, folder_id: str) -> None:
        self._children.pop(folder_id, None)

    # -- IntakeStore -------------------------------------------------------------------
    def list_months(self, prop: Property) -> list[PeriodId]:
        return self.list_periods(prop)

    def ensure_month(self, prop: Property, period: PeriodId, folders: Sequence[str]) -> None:
        for name in [*folders, OUTPUT]:
            self._month(prop, period, name, create=True)

    def list_component(self, prop: Property, period: PeriodId, folder: str) -> list[IntakeFile]:
        directory = self._month(prop, period, folder)
        if directory is None:
            return []
        self._forget(directory.id)  # always a fresh listing: this is what the run decides on
        return [self._intake_file(f) for f in self._list(directory.id) if not f.is_folder]

    def _intake_file(self, f: DriveFile) -> IntakeFile:
        is_pdf = f.mime_type == PDF_MIME
        return IntakeFile(
            id=f.id,
            name=f.name,
            uploaded_at=self._uploaded_at(f) if is_pdf else _time_or_epoch(f.modified_time),
            md5=f.md5,
            size=f.size,
            is_pdf=is_pdf,
        )

    def _uploaded_at(self, f: DriveFile) -> datetime:
        """The head revision's time. A file never renamed or re-versioned has
        `modifiedTime == createdTime`, and then either is the upload time — no extra call."""
        if f.created_time and f.modified_time == f.created_time:
            return parse_time(f.created_time)
        revised = self._api.head_revision_time(f.id)
        if revised:
            return parse_time(revised)
        return _time_or_epoch(f.created_time or f.modified_time)

    def rename(
        self, prop: Property, period: PeriodId, folder: str, file: IntakeFile, name: str
    ) -> None:
        self._api.rename(file.id, name)
        directory = self._month(prop, period, folder)
        if directory is not None:
            self._forget(directory.id)
        log.info("intake.renamed", property=prop.id, period=period, folder=folder)

    def download(self, file: IntakeFile, dest: Path) -> Path:
        return self._api.download(file.id, dest)

    def read_state(self, prop: Property, period: PeriodId) -> MonthState | None:
        text = self._read_text(self._month(prop, period, OUTPUT, MANIFESTS), STATE_FILE)
        return MonthState.model_validate_json(text) if text is not None else None

    def write_state(self, prop: Property, period: PeriodId, state: MonthState) -> None:
        folder = self._month(prop, period, OUTPUT, MANIFESTS, create=True)
        assert folder is not None
        self._write_text(folder, STATE_FILE, state.model_dump_json(indent=2) + "\n")

    def read_manifest(
        self, prop: Property, period: PeriodId, version: int
    ) -> dict[str, Any] | None:
        text = self._read_text(self._month(prop, period, OUTPUT, MANIFESTS), f"v{version}.json")
        if text is None:
            return None
        data: dict[str, Any] = json.loads(text)
        return data

    def output_names(self, prop: Property, period: PeriodId) -> list[str]:
        output = self._month(prop, period, OUTPUT)
        if output is None:
            return []
        self._forget(output.id)
        return sorted(f.name for f in self._list(output.id))

    def publish(  # type: ignore[override]
        self, prop: Property, period: PeriodId, path: Path, name: str, *, manifests: bool = False
    ) -> str:
        where = (OUTPUT, MANIFESTS) if manifests else (OUTPUT,)
        folder = self._month(prop, period, *where, create=True)
        if folder is None:  # pragma: no cover - create=True always returns a folder
            raise RepositoryError(f"{prop.id}: could not create {'/'.join(where)} in Drive")
        self._forget(folder.id)
        final = _unique_name({f.name for f in self._list(folder.id)}, name)
        self._api.upload(folder.id, path, name=final)
        self._forget(folder.id)
        return final

    def read_status(self, prop: Property, period: PeriodId) -> tuple[str, str] | None:
        output = self._month(prop, period, OUTPUT)
        if output is None:
            return None
        self._forget(output.id)
        for f in sorted(self._list(output.id), key=lambda f: f.name):
            if not f.is_folder and is_status_filename(f.name):
                return f.name, self._download_text(f.id)
        return None

    def status_name(self, prop: Property, period: PeriodId) -> str | None:
        output = self._month(prop, period, OUTPUT)
        if output is None:
            return None
        self._forget(output.id)
        names = sorted(
            f.name for f in self._list(output.id) if not f.is_folder and is_status_filename(f.name)
        )
        return names[0] if names else None

    def write_status(self, prop: Property, period: PeriodId, filename: str, body: str) -> bool:
        output = self._month(prop, period, OUTPUT, create=True)
        assert output is not None
        self._forget(output.id)
        existing = [
            f for f in self._list(output.id) if not f.is_folder and is_status_filename(f.name)
        ]
        if (
            len(existing) == 1
            and existing[0].name == filename
            and self._download_text(existing[0].id) == body
        ):
            return False
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.txt"
            path.write_text(body)
            if existing:
                # Rewrite our own file in place — renamed to the new headline — so the folder
                # never shows two statuses. Any extra (a crashed run's) is ours to trash.
                self._api.update_content(existing[0].id, path, name=filename)
                for extra in existing[1:]:
                    self._api.trash(extra.id)
            else:
                self._api.upload(output.id, path, name=filename)
        self._forget(output.id)
        return True

    def write_summary(self, body: str) -> bool:
        root = DriveFile(id=self._root, name="", mime_type="")
        if self._read_text(root, ROOT_SUMMARY) == body:
            return False
        self._write_text(root, ROOT_SUMMARY, body)
        return True

    # -- helpers -------------------------------------------------------------------------
    def _read_text(self, folder: DriveFile | None, name: str) -> str | None:
        if folder is None:
            return None
        self._forget(folder.id)
        match = next((f for f in self._list(folder.id) if f.name == name), None)
        return self._download_text(match.id) if match else None

    def _write_text(self, folder: DriveFile, name: str, text: str) -> None:
        self._forget(folder.id)
        match = next((f for f in self._list(folder.id) if f.name == name), None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text)
            if match is not None:
                self._api.update_content(match.id, path)
            else:
                self._api.upload(folder.id, path, name=name)
        self._forget(folder.id)

    def _download_text(self, file_id: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            return self._api.download(file_id, Path(tmp) / "f").read_text()


def _time_or_epoch(value: str | None) -> datetime:
    return parse_time(value) if value else datetime(1970, 1, 1, tzinfo=UTC)
