"""The intake store contract, run against local disk and an in-memory Drive (SPEC §18.3, §18.4).

The two must behave identically: every rehearsal and most tests run locally, and production
runs on Drive.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from crr.config import load_config
from crr.intake.state import MonthState, VersionEntry
from crr.models import BuildStatus
from crr.repository.intake_drive import DriveIntakeStore
from crr.repository.intake_local import LocalIntakeStore
from tests.unit.fake_drive import FakeDrive

CONFIG = load_config(Path("config"))
FORT = CONFIG.properties.property("fort-grounds").to_domain()
PERIOD = "2026-09"
FOLDERS = [c.folder for c in CONFIG.components_for("fort-grounds")]
BS = "2 - Balance Sheet"
T0 = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


@dataclass
class Harness:
    store: Any
    #: put(folder, name, content, at) — a person uploading a file
    put: Callable[[str, str, bytes, datetime], None]
    #: set the clock that system writes (renames) are stamped with
    set_now: Callable[[datetime], None]


def _local(tmp_path: Path) -> Harness:
    store = LocalIntakeStore(tmp_path / "root", CONFIG.properties)

    def put(folder: str, name: str, content: bytes, at: datetime) -> None:
        path = store.month_dir(FORT, PERIOD) / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        os.utime(path, (at.timestamp(), at.timestamp()))

    return Harness(store, put, lambda _: None)


def _drive(tmp_path: Path) -> Harness:
    drive = FakeDrive()
    store = DriveIntakeStore(drive, drive.root_id, CONFIG.properties)

    def put(folder: str, name: str, content: bytes, at: datetime) -> None:
        parent = drive.add_path(
            "Missoula Property Management", "Fort Grounds", "2026-09 September", folder
        )
        mime = "application/pdf" if name.endswith(".pdf") else "image/jpeg"
        drive.add_file(parent, name, content, at=at, mime=mime)

    def set_now(moment: datetime) -> None:
        drive.now = moment

    harness = Harness(store, put, set_now)
    harness.drive = drive  # type: ignore[attr-defined]
    return harness


@pytest.fixture(params=["local", "gdrive"])
def h(request: pytest.FixtureRequest, tmp_path: Path) -> Harness:
    return _local(tmp_path) if request.param == "local" else _drive(tmp_path)


def test_ensure_month_creates_every_folder_once(h: Harness) -> None:
    h.store.ensure_month(FORT, PERIOD, FOLDERS)
    h.store.ensure_month(FORT, PERIOD, FOLDERS)  # idempotent
    h.store.ensure_month(FORT, "2026-10", FOLDERS)
    assert h.store.list_months(FORT) == ["2026-09", "2026-10"]
    assert h.store.list_component(FORT, PERIOD, BS) == []
    assert h.store.output_names(FORT, PERIOD) == []


def test_a_missing_folder_lists_nothing(h: Harness) -> None:
    assert h.store.list_component(FORT, PERIOD, BS) == []
    assert h.store.read_state(FORT, PERIOD) is None
    assert h.store.read_status(FORT, PERIOD) is None


def test_files_carry_upload_time_content_hash_and_type(h: Harness) -> None:
    h.put(BS, "bs.pdf", b"%PDF one", T0)
    h.put(BS, "photo.jpg", b"jpeg", T0)
    files = {f.name: f for f in h.store.list_component(FORT, PERIOD, BS)}
    assert set(files) == {"bs.pdf", "photo.jpg"}
    assert files["bs.pdf"].is_pdf and not files["photo.jpg"].is_pdf
    assert files["bs.pdf"].uploaded_at == T0
    import hashlib

    assert files["bs.pdf"].md5 == hashlib.md5(b"%PDF one").hexdigest()
    same = h.store.list_component(FORT, PERIOD, BS)
    assert {f.md5 for f in same} == {f.md5 for f in files.values()}


def test_a_rename_does_not_move_the_upload_time(h: Harness) -> None:
    """The property §18.4 rests on: marking a file SUPERSEDED must not make it the newest."""
    h.put(BS, "old.pdf", b"%PDF old", T0)
    (old,) = h.store.list_component(FORT, PERIOD, BS)
    h.set_now(T0 + timedelta(days=3))
    h.store.rename(FORT, PERIOD, BS, old, "SUPERSEDED - old.pdf")
    (renamed,) = h.store.list_component(FORT, PERIOD, BS)
    assert renamed.name == "SUPERSEDED - old.pdf"
    assert renamed.uploaded_at == T0
    assert renamed.md5 == old.md5


def test_download_copies_the_bytes(h: Harness, tmp_path: Path) -> None:
    h.put(BS, "bs.pdf", b"%PDF content", T0)
    (f,) = h.store.list_component(FORT, PERIOD, BS)
    assert h.store.download(f, tmp_path / "dl" / "x.pdf").read_bytes() == b"%PDF content"


def test_state_round_trips(h: Harness) -> None:
    state = MonthState(
        versions=[
            VersionEntry(
                version=1,
                built_at=T0,
                status=BuildStatus.BUILT,
                fingerprint="fp",
                output_file="r - v1.pdf",
            )
        ]
    )
    h.store.write_state(FORT, PERIOD, state)
    assert h.store.read_state(FORT, PERIOD) == state
    state.versions[0].status = BuildStatus.NEEDS_REVIEW
    h.store.write_state(FORT, PERIOD, state)  # replaced in place, not duplicated
    assert h.store.read_state(FORT, PERIOD) == state


def test_publish_never_overwrites(h: Harness, tmp_path: Path) -> None:
    artefact = tmp_path / "a.pdf"
    artefact.write_bytes(b"one")
    assert h.store.publish(FORT, PERIOD, artefact, "Report - v1.pdf") == "Report - v1.pdf"
    second = h.store.publish(FORT, PERIOD, artefact, "Report - v1.pdf")
    assert second != "Report - v1.pdf"
    manifest = tmp_path / "m.json"
    manifest.write_text('{"version": 1}')
    h.store.publish(FORT, PERIOD, manifest, "v1.json", manifests=True)
    assert h.store.read_manifest(FORT, PERIOD, 1) == {"version": 1}
    assert h.store.read_manifest(FORT, PERIOD, 2) is None
    assert {"Report - v1.pdf", second} <= set(h.store.output_names(FORT, PERIOD))


def test_there_is_only_ever_one_status_file(h: Harness) -> None:
    assert h.store.write_status(FORT, PERIOD, "STATUS - Waiting for Balance Sheet.txt", "a")
    assert not h.store.write_status(FORT, PERIOD, "STATUS - Waiting for Balance Sheet.txt", "a")
    assert h.store.write_status(FORT, PERIOD, "STATUS - Built v1 (current).txt", "b")
    names = [n for n in h.store.output_names(FORT, PERIOD) if n.startswith("STATUS - ")]
    assert names == ["STATUS - Built v1 (current).txt"]
    assert h.store.read_status(FORT, PERIOD) == ("STATUS - Built v1 (current).txt", "b")


def test_the_summary_is_replaced_only_when_it_changes(h: Harness) -> None:
    assert h.store.write_summary("one")
    assert not h.store.write_summary("one")
    assert h.store.write_summary("two")


def test_preflight_passes_on_a_writable_store(h: Harness) -> None:
    h.store.preflight_publish()


def test_drive_asks_for_revision_time_only_when_a_file_was_touched(tmp_path: Path) -> None:
    h = _drive(tmp_path)
    drive: FakeDrive = h.drive  # type: ignore[attr-defined]
    h.put(BS, "a.pdf", b"%PDF", T0)
    h.store.list_component(FORT, PERIOD, BS)
    assert drive.revision_calls == 0  # created == modified: the upload time is free
    (f,) = h.store.list_component(FORT, PERIOD, BS)
    drive.now = T0 + timedelta(hours=5)
    h.store.rename(FORT, PERIOD, BS, f, "SUPERSEDED - a.pdf")
    (after,) = h.store.list_component(FORT, PERIOD, BS)
    assert drive.revision_calls == 1 and after.uploaded_at == T0


def test_drive_never_trashes_a_persons_file(tmp_path: Path) -> None:
    h = _drive(tmp_path)
    drive: FakeDrive = h.drive  # type: ignore[attr-defined]
    h.put(BS, "a.pdf", b"%PDF", T0)
    h.put(BS, "b.pdf", b"%PDF 2", T0 + timedelta(hours=1))
    for f in h.store.list_component(FORT, PERIOD, BS):
        h.store.rename(FORT, PERIOD, BS, f, "SUPERSEDED - " + f.name)
    h.store.write_status(FORT, PERIOD, "STATUS - x.txt", "x")
    h.store.write_status(FORT, PERIOD, "STATUS - y.txt", "y")
    assert drive.deleted == []
