"""Open findings from the Phase 10 audit (2026-09-26), held as tests of the behaviour we want.

Each is `xfail(strict=True)`: it runs on every build, documents a known gap, and turns into a
failure the moment the gap is closed, so whoever closes it removes the marker and the test
becomes an ordinary regression test. The recommended fixes are in PROGRESS.md → Phase 10 →
"Audit follow-ups".
"""

from __future__ import annotations

import os
import shutil
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from crr.classify.golden_classifier import GoldenClassifier
from crr.config import load_config
from crr.golden import load_all_golden
from crr.intake.reconcile import Options, Reconciler
from crr.repository.drive_client import GoogleDriveApi
from crr.repository.intake_drive import DriveIntakeStore
from crr.repository.intake_local import LocalIntakeStore
from crr.settings import Settings
from tests.unit.fake_drive import FakeDrive

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
FORT = CONFIG.properties.property("fort-grounds").to_domain()
JUNE = Path("data/bundle/2026-06/Missoula Property Management/Fort Grounds/2026-06 June/inputs")


class _CountingApi:
    """Every DriveApi call the store makes, counted."""

    def __init__(self, inner: FakeDrive) -> None:
        self.inner = inner
        self.calls: Counter[str] = Counter()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)
        if not callable(attr) or name.startswith("add_"):
            return attr

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.calls[name] += 1
            return attr(*args, **kwargs)

        return counted


def _no_op_calls(closed_months: int, work: Path) -> int:
    """Drive calls in a steady-state run with nothing to build, after `closed_months` months
    of history per property, each closed and showing its final status."""
    drive = FakeDrive()
    for entry in CONFIG.properties.properties:
        manager = CONFIG.properties.manager(entry.property_manager).folder
        for i in range(closed_months):
            year, month = divmod(2026 * 12 + 6 - closed_months + i, 12)  # the last is 2026-07
            label = CONFIG.properties.period_folder(f"{year:04d}-{month + 1:02d}")
            output = drive.add_path(manager, entry.folder, label, "output")
            drive.add_file(output, "STATUS - Closed (v1 is final).txt", b"x", mime="text/plain")
    api = _CountingApi(drive)
    store = DriveIntakeStore(api, drive.root_id, CONFIG.properties)  # type: ignore[arg-type]
    settings = Settings(work_dir=work, _env_file=None)  # type: ignore[call-arg]
    for _ in range(2):  # the first run prepares this month's and next month's folders
        api.calls.clear()
        store._children.clear()
        Reconciler(
            config=CONFIG,
            settings=settings,
            store=store,
            classifier_for=lambda _pid: None,  # type: ignore[arg-type,return-value]
            clock=lambda: NOW,
            monotonic=lambda: 0.0,
        ).run(Options())
    return sum(api.calls.values())


def test_a_no_op_run_does_not_grow_with_closed_history(tmp_path: Path) -> None:
    """Finding 4: every closed month used to cost 3 Drive calls on every run, forever."""
    assert _no_op_calls(12, tmp_path / "b") == _no_op_calls(0, tmp_path / "a")


class _CallsByPeriod:
    """Which months a local store was asked about."""

    def __init__(self, inner: LocalIntakeStore) -> None:
        self.inner = inner
        self.periods: set[str] = set()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)

        def recorded(*args: Any, **kwargs: Any) -> Any:
            self.periods.update(a for a in args if isinstance(a, str) and a[:2] == "20")
            return attr(*args, **kwargs)

        return recorded if callable(attr) else attr


@pytest.mark.parametrize(
    ("today", "closed", "read"),
    [
        (datetime(2026, 11, 12, 6, 0, tzinfo=UTC), True, True),  # 1 day past: closed now
        (datetime(2026, 11, 25, 6, 0, tzinfo=UTC), True, True),  # 14 days past: still in grace
        (datetime(2026, 11, 26, 6, 0, tzinfo=UTC), False, False),  # 15 days: never read again
    ],
    ids=["just-closed", "last-day-of-grace", "past-grace"],
)
def test_a_closed_month_is_read_only_within_the_grace_period(
    tmp_path: Path, today: datetime, closed: bool, read: bool
) -> None:
    """September closes 2026-11-11; its final status is written by a run within 14 days of
    that, and after that nobody reads the month again (SPEC §18.3)."""
    store = LocalIntakeStore(tmp_path / "drive", CONFIG.properties)
    store.ensure_month(FORT, "2026-09", [])
    store.write_status(FORT, "2026-09", "STATUS - Built v1 (current).txt", "v1")
    spy = _CallsByPeriod(store)
    Reconciler(
        config=CONFIG,
        settings=Settings(work_dir=tmp_path / "w", _env_file=None),  # type: ignore[call-arg]
        store=spy,  # type: ignore[arg-type]
        classifier_for=lambda _pid: None,  # type: ignore[arg-type,return-value]
        clock=lambda: today,
        monotonic=lambda: 0.0,
    ).run(Options(property_ids=("fort-grounds",)))
    status = store.status_name(FORT, "2026-09")
    assert (status == "STATUS - Closed 2026-11-11 (nothing built).txt") is closed
    assert ("2026-09" in spy.periods) is read


class _Request:
    def __init__(self, log: list[dict[str, Any]]) -> None:
        self._log = log

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._log.append(kwargs)
        return {"files": []}


class _Service:
    """Just enough of googleapiclient's service to see how requests are executed."""

    def __init__(self) -> None:
        self.log: list[dict[str, Any]] = []

    def files(self) -> _Service:
        return self

    def list(self, **_kwargs: Any) -> _Request:
        return _Request(self.log)


@pytest.mark.xfail(
    strict=True,
    reason="audit finding 5: Drive requests are executed without retries, so one 5xx or 429 "
    "makes a month unchecked for the run",
)
def test_drive_requests_are_retried() -> None:
    api = GoogleDriveApi.__new__(GoogleDriveApi)
    service = _Service()
    api._service = service
    api.list_children("folder-id")
    assert service.log and all(call.get("num_retries", 0) >= 3 for call in service.log)


class _Golden:
    needs_page_images = False
    prompt_version: str | None = None
    name = "golden"

    def __init__(self) -> None:
        self._inner = GoldenClassifier(GOLDEN["fort-grounds"])

    def classify(self, doc, schema, pages):  # type: ignore[no-untyped-def]
        return self._inner.classify(doc, schema, pages)


def _reconciler(store: Any, work: Path, now: datetime) -> Reconciler:
    return Reconciler(
        config=CONFIG,
        settings=Settings(work_dir=work, orientation_check=False, _env_file=None),  # type: ignore[call-arg]
        store=store,
        classifier_for=lambda _pid: _Golden(),  # type: ignore[arg-type,return-value]
        clock=lambda: now,
        monotonic=lambda: 0.0,
    )


@pytest.mark.xfail(
    strict=True,
    reason="audit finding 6: a second run landing between a build's publish and its state.json "
    "write publishes the same files again, and the index keeps only one of the two",
)
def test_a_run_landing_between_publish_and_commit_publishes_no_duplicate(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    month = LocalIntakeStore(root, CONFIG.properties).month_dir(FORT, "2026-09")
    uploaded = NOW - timedelta(hours=2)
    for folder, name in (
        ("1 - Property Manager Report", "05 PM Source - Missoula PM Baseline.pdf"),
        ("2 - Balance Sheet", "01 Cornerstone - Balance Sheet.pdf"),
        ("3 - Profit and Loss", "02 Cornerstone - Profit and Loss YTD Comparison.pdf"),
    ):
        (month / folder).mkdir(parents=True)
        shutil.copy(JUNE / name, month / folder / name)
        os.utime(month / folder / name, (uploaded.timestamp(),) * 2)
    other = _reconciler(LocalIntakeStore(root, CONFIG.properties), tmp_path / "w2", NOW)
    fired: list[bool] = []

    class Interleaved(LocalIntakeStore):
        """The other execution runs start to finish right after this one's PDF lands."""

        def publish(self, prop, period, path, name, *, manifests=False):  # type: ignore[no-untyped-def]
            final = super().publish(prop, period, path, name, manifests=manifests)
            if not fired and name.endswith(".pdf"):
                fired.append(True)
                other.run(Options(property_ids=("fort-grounds",)))
            return final

    store = Interleaved(root, CONFIG.properties)
    _reconciler(store, tmp_path / "w1", NOW).run(Options(property_ids=("fort-grounds",)))
    pdfs = [p.name for p in (month / "output").iterdir() if p.suffix == ".pdf"]
    assert len(pdfs) == 1, pdfs
