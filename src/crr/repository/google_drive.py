"""The Google Drive repository (SPEC §6.1, §13, D-14).

The Drive tree mirrors the repo bundle without `target/` and `reference/`:

    <root>/<PM folder>/<Property folder>/<YYYY-MM Month>/inputs/…
                                                        /output/    ← written here
                                                        /review/    ← written here instead

Navigation is by folder *name*, because the names are contractual (SPEC §4.3) and folder ids
are not. Every lookup is cached for the life of the object: a build touches the same handful
of folders repeatedly, and Drive's list calls are the slow part.

This repository never deletes and never overwrites. A second publish of the same name lands
as `<name> (build N).<ext>`, exactly as the local repository does.
"""

from __future__ import annotations

import tempfile
import uuid
from contextlib import suppress
from pathlib import Path

from crr.config.properties import PropertyRegistry
from crr.log import get_logger
from crr.models import BuildStatus, PeriodId, Property, SourceDocument
from crr.preprocess.text import document_text_layer, page_count, sha256_file
from crr.repository.drive_client import DriveApi, DriveFile
from crr.repository.local_fs import (
    CORNERSTONE_SCHEMA,
    PM_SOURCE_ROLE,
    SchemaResolver,
    pm_pages_from_manifest,
)
from crr.repository.protocol import RepositoryError

log = get_logger(__name__)

INPUTS = "inputs"
OUTPUT = "output"
REVIEW = "review"


class GoogleDriveRepository:
    """Reads a period's inputs from Drive and publishes the finished package back."""

    name = "gdrive"

    def __init__(
        self,
        api: DriveApi,
        root_folder_id: str,
        registry: PropertyRegistry,
        schema_for_role: SchemaResolver | None = None,
    ) -> None:
        self._api = api
        self._root = root_folder_id
        self._registry = registry
        self._schema_for_role = schema_for_role or self._default_schema_for_role
        self._children: dict[str, list[DriveFile]] = {}

    def _default_schema_for_role(self, prop: Property, role: str) -> str:
        if role == PM_SOURCE_ROLE:
            return self._registry.manager(prop.property_manager).schema_id
        return CORNERSTONE_SCHEMA

    # -- navigation --------------------------------------------------------------------
    def _list(self, folder_id: str) -> list[DriveFile]:
        if folder_id not in self._children:
            self._children[folder_id] = self._api.list_children(folder_id)
        return self._children[folder_id]

    def _child(self, folder_id: str, name: str) -> DriveFile | None:
        """Exact name match, then a case-insensitive one — Drive names are contractual, but a
        manager renaming `Fort Grounds` to `fort grounds` should not read as 'no data'."""
        children = self._list(folder_id)
        for child in children:
            if child.name == name:
                return child
        folded = name.casefold()
        for child in children:
            if child.name.casefold() == folded:
                log.warning("gdrive.name_case_mismatch", expected=name, found=child.name)
                return child
        return None

    def _folder(self, folder_id: str, name: str) -> DriveFile | None:
        child = self._child(folder_id, name)
        return child if child and child.is_folder else None

    def _path(self, *names: str, create: bool = False) -> DriveFile | None:
        current_id = self._root
        found: DriveFile | None = None
        for name in names:
            found = self._folder(current_id, name)
            if found is None:
                if not create:
                    return None
                found = self._api.create_folder(current_id, name)
                self._children.pop(current_id, None)
                log.info("gdrive.folder_created", name=name)
            current_id = found.id
        return found

    def _property_path(self, prop: Property) -> tuple[str, str]:
        manager = self._registry.manager(prop.property_manager)
        return manager.folder, prop.folder

    # -- SourceRepository --------------------------------------------------------------
    def list_periods(self, prop: Property) -> list[PeriodId]:
        manager_folder, property_folder = self._property_path(prop)
        base = self._path(manager_folder, property_folder)
        if base is None:
            return []
        periods: set[str] = set()
        for child in self._list(base.id):
            if child.is_folder and len(child.name) >= 7 and child.name[4] == "-":
                candidate = child.name[:7]
                year, _, month = candidate.partition("-")
                if year.isdigit() and month.isdigit():
                    periods.add(candidate)
        return sorted(periods)

    def has_inputs(self, prop: Property, period: PeriodId) -> bool:
        """A period is ready to build when `inputs/` holds the PM source (SPEC §13)."""
        return self.present_inputs(prop, period).get(PM_SOURCE_ROLE) is not None

    def present_inputs(self, prop: Property, period: PeriodId) -> dict[str, DriveFile | None]:
        """role → the Drive file, or None when it is not there yet."""
        manager_folder, property_folder = self._property_path(prop)
        inputs = self._path(
            manager_folder, property_folder, self._registry.period_folder(period), INPUTS
        )
        filenames = self._registry.input_filenames(prop.id)
        if inputs is None:
            return dict.fromkeys(filenames)
        return {role: self._child(inputs.id, name) for role, name in filenames.items()}

    def fetch_inputs(self, prop: Property, period: PeriodId, dest: Path) -> list[SourceDocument]:
        present = self.present_inputs(prop, period)
        if present.get(PM_SOURCE_ROLE) is None:
            raise RepositoryError(
                f"{prop.id}: no PM source in Drive for period {period} "
                f"({self._registry.input_filenames(prop.id)[PM_SOURCE_ROLE]!r})"
            )
        dest.mkdir(parents=True, exist_ok=True)
        documents: list[SourceDocument] = []
        for role, drive_file in present.items():
            if drive_file is None:
                log.info("repository.optional_input_absent", property=prop.id, role=role)
                continue
            local = dest / drive_file.name
            if not (
                local.is_file() and drive_file.size and local.stat().st_size == drive_file.size
            ):
                self._api.download(drive_file.id, local)
            sha = sha256_file(local)
            _, has_text = document_text_layer(local)
            documents.append(
                SourceDocument(
                    role=role,
                    schema_id=self._schema_for_role(prop, role),
                    path=local,
                    sha256=sha,
                    page_count=page_count(local),
                    has_text_layer=has_text,
                )
            )
            log.info("repository.fetched", property=prop.id, role=role, sha256=sha)
        return documents

    def publish(
        self, prop: Property, period: PeriodId, files: list[Path], status: BuildStatus
    ) -> None:
        if status is BuildStatus.FAILED:
            log.info("repository.publish_skipped", property=prop.id, status=status.value)
            return
        manager_folder, property_folder = self._property_path(prop)
        folder_name = REVIEW if status is BuildStatus.NEEDS_REVIEW else OUTPUT
        target = self._path(
            manager_folder,
            property_folder,
            self._registry.period_folder(period),
            folder_name,
            create=True,
        )
        if target is None:  # pragma: no cover - create=True always returns a folder
            raise RepositoryError(f"{prop.id}: could not create {folder_name}/ in Drive")
        existing = {child.name for child in self._list(target.id)}
        for path in files:
            name = _unique_name(existing, path.name)
            self._api.upload(target.id, path, name=name)
            existing.add(name)
            self._children.pop(target.id, None)
            # As in the local repository: the shape of the artefact, never its name.
            log.info(
                "repository.published",
                property=prop.id,
                folder=folder_name,
                kind=path.suffix.lstrip(".") or "file",
                renamed=name != path.name,
            )

    def preflight_publish(self) -> None:
        """Upload one byte to the Drive root and delete it again (SPEC §6.1, B-09).

        Nothing cheaper is trustworthy. `capabilities.canAddChildren` reports `true` on the
        folder even when every upload into it fails, because creating a *folder* really is
        allowed — folders consume no quota. Only writing a file proves a file can be written,
        which is why this does exactly that and nothing clever.
        """
        probe = Path(tempfile.gettempdir()) / f".crr-preflight-{uuid.uuid4().hex}"
        probe.write_bytes(b"crr")
        try:
            created = self._api.upload(self._root, probe, name=probe.name)
        # Broad on purpose: the client raises googleapiclient's HttpError, which this module
        # does not import, and any failure to write here means the same thing to the caller.
        except Exception as exc:
            raise RepositoryError(
                f"Drive rejected a test upload to the root folder: {exc}\n"
                "The runner cannot publish. If this is `storageQuotaExceeded`, the root is a "
                "My Drive folder and a service account has no storage of its own — move it to "
                "a shared drive. See docs/SETUP-GOOGLE-DRIVE.md."
            ) from exc
        finally:
            with suppress(OSError):
                probe.unlink()
        self._children.pop(self._root, None)
        try:
            self._api.delete(created.id)
        except Exception as exc:
            # Cleanup only: the probe is what mattered and it passed. A leftover byte is not
            # worth failing a run over, but it is worth saying so — someone will find the file.
            log.warning("repository.preflight_probe_left", error=type(exc).__name__)
        else:
            self._children.pop(self._root, None)
        log.info("repository.preflight_ok", repo="gdrive")

    def previous_pm_pages(self, prop: Property, period: PeriodId, work_dir: Path) -> int | None:
        """PM source page count from the last period this property published (SPEC §6.8).

        Drive is the archive here: the manifest sits beside the package it describes, so the
        check reads the newest `output/build-manifest.json` from an earlier period.
        """
        earlier = [p for p in self.list_periods(prop) if p < period]
        manager_folder, property_folder = self._property_path(prop)
        for candidate in sorted(earlier, reverse=True):
            output = self._path(
                manager_folder,
                property_folder,
                self._registry.period_folder(candidate),
                OUTPUT,
            )
            if output is None:
                continue
            manifest = self._child(output.id, "build-manifest.json")
            if manifest is None:
                continue
            local = work_dir / "previous" / f"{prop.id}-{candidate}.json"
            self._api.download(manifest.id, local)
            pages = pm_pages_from_manifest(local)
            if pages is not None:
                log.info("gdrive.previous_manifest", property=prop.id, period=candidate)
                return pages
        return None

    # -- period preparation ------------------------------------------------------------
    def ensure_period_skeleton(self, prop: Property, period: PeriodId) -> dict[str, str]:
        """Create `<property>/<period>/inputs/` (folders only) and return the folder ids.

        This is what "preparing a period" means for a human: the folders exist, so the files
        have somewhere obvious to go (SPEC §13).
        """
        manager_folder, property_folder = self._property_path(prop)
        period_folder = self._registry.period_folder(period)
        manager = self._path(manager_folder, create=True)
        property_dir = self._path(manager_folder, property_folder, create=True)
        period_dir = self._path(manager_folder, property_folder, period_folder, create=True)
        inputs = self._path(manager_folder, property_folder, period_folder, INPUTS, create=True)
        if not (manager and property_dir and period_dir and inputs):  # pragma: no cover
            raise RepositoryError(f"{prop.id}: could not create the period skeleton in Drive")
        return {
            manager_folder: manager.id,
            f"{manager_folder}/{property_folder}": property_dir.id,
            f"{manager_folder}/{property_folder}/{period_folder}": period_dir.id,
            f"{manager_folder}/{property_folder}/{period_folder}/{INPUTS}": inputs.id,
        }


def _unique_name(existing: set[str], name: str) -> str:
    """`report.pdf` → `report (build 2).pdf`. Drive happily keeps two files with the same
    name in one folder, which is worse than a collision: nobody can tell which is current."""
    if name not in existing:
        return name
    stem, dot, suffix = name.rpartition(".")
    stem, suffix = (stem, f".{suffix}") if dot else (name, "")
    build = 2
    while f"{stem} (build {build}){suffix}" in existing:
        build += 1
    return f"{stem} (build {build}){suffix}"
