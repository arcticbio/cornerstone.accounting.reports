"""The local-filesystem repository (SPEC §6.1).

Layout: `<root>/<pm folder>/<property folder>/<period folder>/inputs/`, publishing to
`output/` or, when the build needs review, `review/`. Never deletes; never overwrites — a
second publish of the same name lands as `<name> (build N).<ext>`, matching the Drive
repository's rule so the two behave alike (SPEC §6.1).
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path

from crr.config.properties import PropertyRegistry
from crr.log import get_logger
from crr.models import BuildStatus, PeriodId, Property, SourceDocument
from crr.preprocess.text import document_text_layer, page_count, sha256_file
from crr.repository.protocol import RepositoryError

log = get_logger(__name__)

_PERIOD_DIR = re.compile(r"^(\d{4})-(\d{2})\b")


PM_SOURCE_ROLE = "pm_source"
CORNERSTONE_SCHEMA = "cornerstone-qbo"

#: property, role -> schema id. The pipeline supplies one built from the output definition;
#: the default covers the shape every manager in the registry uses today.
SchemaResolver = Callable[[Property, str], str]


def pm_pages_from_manifest(path: Path | None) -> int | None:
    """PM source page count recorded in a manifest file, or None if unreadable."""
    if path is None:
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    for source in data.get("inputs", []):
        if source.get("role") == PM_SOURCE_ROLE:
            pages = source.get("pages")
            return int(pages) if isinstance(pages, int) else None
    return None


class LocalFsRepository:
    """Reads the golden bundle — or any tree with the same shape — off local disk."""

    name = "local"

    def __init__(
        self,
        root: Path,
        registry: PropertyRegistry,
        schema_for_role: SchemaResolver | None = None,
        publish_root: Path | None = None,
    ) -> None:
        self.root = root
        #: Outputs mirror the repository layout under this root. It defaults to `root` — the
        #: layout SPEC §6.1 describes — but the CLI points it away from `bundle_root` so a
        #: local run never writes into the read-only June fixture (D-08).
        self.publish_root = publish_root if publish_root is not None else root
        self._registry = registry
        self._schema_for_role = schema_for_role or self._default_schema_for_role

    def _default_schema_for_role(self, prop: Property, role: str) -> str:
        if role == PM_SOURCE_ROLE:
            return self._registry.manager(prop.property_manager).schema_id
        return CORNERSTONE_SCHEMA

    # -- layout ------------------------------------------------------------------------
    def property_dir(self, prop: Property) -> Path:
        manager = self._registry.manager(prop.property_manager)
        return self.root / manager.folder / prop.folder

    def period_dir(self, prop: Property, period: PeriodId) -> Path:
        return self.property_dir(prop) / self._registry.period_folder(period)

    def publish_dir(self, prop: Property, period: PeriodId, folder: str) -> Path:
        manager = self._registry.manager(prop.property_manager)
        return (
            self.publish_root
            / manager.folder
            / prop.folder
            / self._registry.period_folder(period)
            / folder
        )

    def list_periods(self, prop: Property) -> list[PeriodId]:
        """Period ids present for a property, oldest first."""
        base = self.property_dir(prop)
        if not base.is_dir():
            return []
        found: set[str] = set()
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            match = _PERIOD_DIR.match(entry.name)
            if match:
                found.add(f"{match.group(1)}-{match.group(2)}")
        return sorted(found)

    def has_inputs(self, prop: Property, period: PeriodId) -> bool:
        """True when the PM source file is there — the definition of a period being ready
        to build (SPEC §13)."""
        filenames = self._registry.input_filenames(prop.id)
        return (self.period_dir(prop, period) / "inputs" / filenames[PM_SOURCE_ROLE]).is_file()

    # -- fetch -------------------------------------------------------------------------
    def fetch_inputs(self, prop: Property, period: PeriodId, dest: Path) -> list[SourceDocument]:
        """Copy the period's inputs into `dest` and describe each one.

        A missing PM source is a hard failure for this property; a missing Cornerstone
        component is simply absent from the returned list, and the resolver decides whether
        that matters (SPEC §6.1).
        """
        inputs_dir = self.period_dir(prop, period) / "inputs"
        if not inputs_dir.is_dir():
            raise RepositoryError(
                f"{prop.id}: no inputs directory for period {period} under {self.name}"
            )
        filenames = self._registry.input_filenames(prop.id)
        dest.mkdir(parents=True, exist_ok=True)

        documents: list[SourceDocument] = []
        for role, filename in filenames.items():
            source = inputs_dir / filename
            if not source.is_file():
                if role == PM_SOURCE_ROLE:
                    raise RepositoryError(
                        f"{prop.id}: PM source {filename!r} is missing for period {period}"
                    )
                log.info("repository.optional_input_absent", property=prop.id, role=role)
                continue
            local = dest / filename
            if not local.exists() or local.stat().st_size != source.stat().st_size:
                shutil.copy2(source, local)
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

    # -- publish -----------------------------------------------------------------------
    def previous_pm_pages(self, prop: Property, period: PeriodId, work_dir: Path) -> int | None:
        """PM source page count from this property's last build, for the drift check."""
        path = previous_manifest_path(work_dir, prop.id, period)
        return pm_pages_from_manifest(path)

    def publish(
        self, prop: Property, period: PeriodId, files: list[Path], status: BuildStatus
    ) -> None:
        """Copy the finished artefacts beside the inputs. `FAILED` publishes nothing."""
        if status is BuildStatus.FAILED:
            log.info("repository.publish_skipped", property=prop.id, status=status.value)
            return
        folder = "review" if status is BuildStatus.NEEDS_REVIEW else "output"
        target_dir = self.publish_dir(prop, period, folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        for path in files:
            destination = _unique_name(target_dir, path.name)
            shutil.copy2(path, destination)
            # The output filename carries the property's public name; log the shape of the
            # artefact, not the name (SPEC §11, §16). The manifest records the filename.
            log.info(
                "repository.published",
                property=prop.id,
                folder=folder,
                kind=destination.suffix.lstrip(".") or "file",
                renamed=destination.name != path.name,
            )


def previous_manifest_path(work_dir: Path, property_id: str, period: PeriodId) -> Path | None:
    """The newest manifest for this property from a period *before* `period`.

    Local builds leave their manifests in `work/<period>/<property>/`, so the work directory
    is the archive the drift check reads (PLAN Phase 9).
    """
    if not work_dir.is_dir():
        return None
    candidates: list[tuple[str, Path]] = []
    for period_dir in work_dir.iterdir():
        if not period_dir.is_dir() or period_dir.name >= period:
            continue
        manifest = period_dir / property_id / "build-manifest.json"
        if manifest.is_file():
            candidates.append((period_dir.name, manifest))
    if not candidates:
        return None
    return max(candidates)[1]


def _unique_name(directory: Path, name: str) -> Path:
    """`report.pdf` → `report (build 2).pdf` when the name is taken. Never overwrites."""
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    build = 2
    while True:
        candidate = directory / f"{stem} (build {build}){suffix}"
        if not candidate.exists():
            return candidate
        build += 1
