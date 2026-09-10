"""The Drive repository against an in-memory Drive (SPEC §6.1, §13, D-14)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.config import load_config
from crr.models import BuildStatus
from crr.repository.google_drive import GoogleDriveRepository
from crr.repository.protocol import RepositoryError
from tests.conftest import MakePdf
from tests.unit.fake_drive import FakeDrive

CONFIG = load_config(Path("config"))
REGISTRY = CONFIG.properties
FORT_GROUNDS = REGISTRY.property("fort-grounds").to_domain()
TIMBER_PLACE = REGISTRY.property("timber-place").to_domain()

MISSOULA = "Missoula Property Management"
MCCATHREN = "McCathren Management and Real Estate Services"
PERIOD = "2026-06"
PERIOD_FOLDER = "2026-06 June"


def _drive_with_inputs(make_pdf: MakePdf, *, complete: bool = True) -> FakeDrive:
    drive = FakeDrive()
    inputs = drive.add_path(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "inputs")
    pdf = make_pdf("any.pdf", ["Owner Statement " * 8]).read_bytes()
    drive.add_file(inputs, "05 PM Source - Missoula PM Baseline.pdf", pdf)
    drive.add_file(inputs, "01 Cornerstone - Balance Sheet.pdf", pdf)
    drive.add_file(inputs, "02 Cornerstone - Profit and Loss YTD Comparison.pdf", pdf)
    if complete:
        drive.add_file(inputs, "03 Cornerstone - Investor Distribution Schedule.pdf", pdf)
    return drive


def _repo(drive: FakeDrive) -> GoogleDriveRepository:
    return GoogleDriveRepository(drive, drive.root_id, REGISTRY)


def test_periods_are_listed_from_folder_names(make_pdf: MakePdf) -> None:
    drive = _drive_with_inputs(make_pdf)
    drive.add_path(MISSOULA, "Fort Grounds", "2026-09 September")
    drive.add_path(MISSOULA, "Fort Grounds", "notes")  # not a period
    assert _repo(drive).list_periods(FORT_GROUNDS) == ["2026-06", "2026-09"]


def test_an_unknown_property_lists_no_periods() -> None:
    drive = FakeDrive()
    assert _repo(drive).list_periods(FORT_GROUNDS) == []


def test_a_period_is_ready_when_the_pm_source_is_there(make_pdf: MakePdf) -> None:
    drive = _drive_with_inputs(make_pdf)
    repo = _repo(drive)
    assert repo.has_inputs(FORT_GROUNDS, PERIOD)
    assert not repo.has_inputs(FORT_GROUNDS, "2026-09")
    assert not repo.has_inputs(TIMBER_PLACE, PERIOD)


def test_fetch_downloads_every_present_input(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    documents = _repo(drive).fetch_inputs(FORT_GROUNDS, PERIOD, tmp_path)
    assert [d.role for d in documents] == [
        "pm_source",
        "cornerstone_balance_sheet",
        "cornerstone_profit_loss_ytd",
        "cornerstone_distribution_schedule",
    ]
    assert all(d.path.is_file() for d in documents)
    assert all(len(d.sha256) == 64 for d in documents)
    assert documents[0].schema_id == "rentmanager-missoula"
    assert documents[1].schema_id == "cornerstone-qbo"


def test_a_missing_optional_component_is_simply_absent(make_pdf: MakePdf, tmp_path: Path) -> None:
    """Timber Place's missing distribution schedule is the real case (D-06)."""
    drive = _drive_with_inputs(make_pdf, complete=False)
    documents = _repo(drive).fetch_inputs(FORT_GROUNDS, PERIOD, tmp_path)
    assert "cornerstone_distribution_schedule" not in {d.role for d in documents}
    assert len(documents) == 3


def test_a_missing_pm_source_is_a_hard_failure(tmp_path: Path) -> None:
    drive = FakeDrive()
    drive.add_path(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "inputs")
    with pytest.raises(RepositoryError, match="no PM source"):
        _repo(drive).fetch_inputs(FORT_GROUNDS, PERIOD, tmp_path)


def test_a_second_fetch_reuses_the_local_copy(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    repo = _repo(drive)
    repo.fetch_inputs(FORT_GROUNDS, PERIOD, tmp_path)
    downloaded = {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()}
    repo.fetch_inputs(FORT_GROUNDS, PERIOD, tmp_path)
    assert {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()} == downloaded


def test_publish_creates_output_and_never_deletes(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-1.4\n")
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text("{}")

    _repo(drive).publish(FORT_GROUNDS, PERIOD, [report, manifest], BuildStatus.BUILT)

    output = drive.find(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "output")
    assert output is not None
    assert sorted(drive.names_in(output)) == ["build-manifest.json", "report.pdf"]
    inputs = drive.find(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "inputs")
    assert inputs is not None
    assert len(drive.names_in(inputs)) == 4  # nothing touched


def test_needs_review_publishes_to_review(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF")
    _repo(drive).publish(FORT_GROUNDS, PERIOD, [report], BuildStatus.NEEDS_REVIEW)
    assert drive.find(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "review") is not None
    assert drive.find(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "output") is None


def test_a_failed_build_publishes_nothing(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF")
    _repo(drive).publish(FORT_GROUNDS, PERIOD, [report], BuildStatus.FAILED)
    assert drive.uploads == []
    assert drive.created_folders == []


def test_a_second_publish_never_overwrites(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    repo = _repo(drive)
    report = tmp_path / "Fort Grounds - Investor Report - June 2026.pdf"
    report.write_bytes(b"%PDF")
    repo.publish(FORT_GROUNDS, PERIOD, [report], BuildStatus.BUILT)
    repo.publish(FORT_GROUNDS, PERIOD, [report], BuildStatus.BUILT)
    repo.publish(FORT_GROUNDS, PERIOD, [report], BuildStatus.BUILT)
    output = drive.find(MISSOULA, "Fort Grounds", PERIOD_FOLDER, "output")
    assert output is not None
    assert sorted(drive.names_in(output)) == [
        "Fort Grounds - Investor Report - June 2026 (build 2).pdf",
        "Fort Grounds - Investor Report - June 2026 (build 3).pdf",
        "Fort Grounds - Investor Report - June 2026.pdf",
    ]


def test_folder_listings_are_cached(make_pdf: MakePdf, tmp_path: Path) -> None:
    drive = _drive_with_inputs(make_pdf)
    repo = _repo(drive)
    repo.has_inputs(FORT_GROUNDS, PERIOD)
    calls = drive.list_calls
    repo.has_inputs(FORT_GROUNDS, PERIOD)
    repo.present_inputs(FORT_GROUNDS, PERIOD)
    assert drive.list_calls == calls


def test_a_case_differing_folder_name_is_found_with_a_warning(make_pdf: MakePdf) -> None:
    drive = FakeDrive()
    drive.add_path(MISSOULA, "fort grounds", PERIOD_FOLDER, "inputs")
    assert _repo(drive).list_periods(FORT_GROUNDS) == ["2026-06"]


def test_the_period_skeleton_is_folders_only(make_pdf: MakePdf) -> None:
    drive = FakeDrive()
    ids = _repo(drive).ensure_period_skeleton(FORT_GROUNDS, "2026-09")
    assert list(ids) == [
        MISSOULA,
        f"{MISSOULA}/Fort Grounds",
        f"{MISSOULA}/Fort Grounds/2026-09 September",
        f"{MISSOULA}/Fort Grounds/2026-09 September/inputs",
    ]
    assert drive.created_folders == [MISSOULA, "Fort Grounds", "2026-09 September", "inputs"]
    assert drive.uploads == []
    inputs = drive.find(MISSOULA, "Fort Grounds", "2026-09 September", "inputs")
    assert inputs is not None
    assert drive.names_in(inputs) == []


def test_the_skeleton_is_idempotent() -> None:
    drive = FakeDrive()
    repo = _repo(drive)
    first = repo.ensure_period_skeleton(FORT_GROUNDS, "2026-09")
    created = list(drive.created_folders)
    second = repo.ensure_period_skeleton(FORT_GROUNDS, "2026-09")
    assert first == second
    assert drive.created_folders == created  # nothing created the second time


def test_two_properties_share_the_manager_folder() -> None:
    drive = FakeDrive()
    repo = _repo(drive)
    repo.ensure_period_skeleton(FORT_GROUNDS, "2026-09")
    repo.ensure_period_skeleton(REGISTRY.property("waypointe").to_domain(), "2026-09")
    assert drive.created_folders.count(MISSOULA) == 1


def test_a_property_of_another_manager_gets_its_own_tree() -> None:
    drive = FakeDrive()
    _repo(drive).ensure_period_skeleton(TIMBER_PLACE, "2026-09")
    assert drive.find(MCCATHREN, "Timber Place", "2026-09 September", "inputs") is not None
