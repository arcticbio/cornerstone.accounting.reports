"""Running every 30 minutes, for years, beside other runs (SPEC §18.3, §18.9).

Audit findings 4 and 6, fixed 2026-09-28: a run with nothing to do no longer grows with the
months behind it, and a run lease keeps a second execution out while one works. Finding 5,
retries on every Drive request, is tests/unit/test_drive_client_retries.py.
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
from crr.intake.lease import LEASE_FILE, Lease
from crr.intake.reconcile import LeaseHeld, Options, Reconciler
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
            sleep=lambda _seconds: None,
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


def _seed(root: Path) -> Path:
    """Fort Grounds' June files uploaded into September two hours ago: ready to build."""
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
    return month


def _lease(owner: str, *, expires: datetime, released: datetime | None = None) -> str:
    return Lease(
        owner=owner,
        host="elsewhere",
        acquired_at=expires - timedelta(minutes=30),
        expires_at=expires,
        released_at=released,
    ).model_dump_json()


def test_a_second_run_is_kept_out_while_a_build_publishes(tmp_path: Path) -> None:
    """Finding 6: a run landing between a build's publish and its state.json write published
    the same files again, and the index kept only one of the two. Now the second run finds
    the first one's lease and does nothing."""
    root = tmp_path / "drive"
    month = _seed(root)
    other = _reconciler(LocalIntakeStore(root, CONFIG.properties), tmp_path / "w2", NOW)
    refused: list[str] = []

    class Interleaved(LocalIntakeStore):
        """The other execution starts right after this one's PDF lands."""

        def publish(self, prop, period, path, name, *, manifests=False):  # type: ignore[no-untyped-def]
            final = super().publish(prop, period, path, name, manifests=manifests)
            if not refused and name.endswith(".pdf"):
                with pytest.raises(LeaseHeld) as held:
                    other.run(Options(property_ids=("fort-grounds",)))
                refused.append(str(held.value))
            return final

    store = Interleaved(root, CONFIG.properties)
    _reconciler(store, tmp_path / "w1", NOW).run(Options(property_ids=("fort-grounds",)))
    assert refused and "holds the lease until" in refused[0]
    assert [p.name for p in (month / "output").iterdir() if p.suffix == ".pdf"] == [
        "Fort Grounds - Investor Report - September 2026 - v1.pdf"
    ]
    state = store.read_state(FORT, "2026-09")
    assert state is not None and [v.version for v in state.versions] == [1]


def test_a_run_releases_its_lease(tmp_path: Path) -> None:
    store = LocalIntakeStore(tmp_path / "drive", CONFIG.properties)
    _reconciler(store, tmp_path / "w", NOW).run(Options(property_ids=("fort-grounds",)))
    lease = Lease.model_validate_json(store.read_lease() or "")
    assert lease.released_at is not None and not lease.held_at(NOW)


@pytest.mark.parametrize(
    "found",
    [
        _lease("crashed", expires=NOW - timedelta(seconds=1)),
        _lease("finished", expires=NOW + timedelta(minutes=10), released=NOW),
        "not a lease at all",
    ],
    ids=["lapsed", "released", "damaged"],
)
def test_a_lease_that_is_not_live_does_not_stop_a_run(tmp_path: Path, found: str) -> None:
    """A crash leaves its lease to lapse; a damaged file must never stop every run for good."""
    root = tmp_path / "drive"
    _seed(root)
    store = LocalIntakeStore(root, CONFIG.properties)
    store.write_lease(found)
    _reconciler(store, tmp_path / "w", NOW).run(Options(property_ids=("fort-grounds",)))
    state = store.read_state(FORT, "2026-09")
    assert state is not None and state.latest is not None and state.latest.version == 1


def test_a_live_lease_stops_a_run_before_it_touches_anything(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    store = LocalIntakeStore(root, CONFIG.properties)
    store.write_lease(_lease("running", expires=NOW + timedelta(minutes=5)))
    with pytest.raises(LeaseHeld, match="elsewhere"):
        _reconciler(store, tmp_path / "w", NOW).run(Options())
    assert sorted(p.name for p in root.iterdir()) == [LEASE_FILE]  # no folders, no summary


def test_a_dry_run_takes_no_lease(tmp_path: Path) -> None:
    store = LocalIntakeStore(tmp_path / "drive", CONFIG.properties)
    held = _lease("running", expires=NOW + timedelta(minutes=5))
    store.write_lease(held)
    _reconciler(store, tmp_path / "w", NOW).run(Options(dry_run=True))
    assert store.read_lease() == held


def test_the_run_that_loses_a_race_for_the_lease_does_nothing(tmp_path: Path) -> None:
    """Both saw no lease and both wrote one; only the write that is read back counts."""
    root = tmp_path / "drive"

    class Raced(LocalIntakeStore):
        def write_lease(self, text: str) -> None:
            super().write_lease(text)
            if '"released_at":null' in text.replace(" ", "").replace("\n", ""):
                super().write_lease(_lease("faster", expires=NOW + timedelta(minutes=30)))

    with pytest.raises(LeaseHeld):
        _reconciler(Raced(root, CONFIG.properties), tmp_path / "w", NOW).run(Options())
    assert sorted(p.name for p in root.iterdir()) == [LEASE_FILE]


def test_a_run_whose_lease_is_taken_over_starts_no_more_builds(tmp_path: Path) -> None:
    """A run that outlives its lease finishes what it started and starts nothing more."""
    root = tmp_path / "drive"
    _seed(root)
    lolo = CONFIG.properties.property("lolo-peak-village")
    inputs = Path(
        "data/bundle/2026-06/Missoula Property Management/Lolo Peak Village/2026-06 June/inputs"
    )
    month = LocalIntakeStore(root, CONFIG.properties).month_dir(lolo.to_domain(), "2026-09")
    for folder, name in (
        ("1 - Property Manager Report", "05 PM Source - Missoula PM Baseline.pdf"),
        ("2 - Balance Sheet", "01 Cornerstone - Balance Sheet.pdf"),
        ("3 - Profit and Loss", "02 Cornerstone - Profit and Loss YTD Comparison.pdf"),
    ):
        (month / folder).mkdir(parents=True)
        shutil.copy(inputs / name, month / folder / name)
        os.utime(month / folder / name, ((NOW - timedelta(hours=2)).timestamp(),) * 2)
    store = LocalIntakeStore(root, CONFIG.properties)

    class TakenOver(_Golden):
        def classify(self, doc, schema, pages):  # type: ignore[no-untyped-def]
            store.write_lease(_lease("newer", expires=NOW + timedelta(minutes=30)))
            return super().classify(doc, schema, pages)

    outcomes = Reconciler(
        config=CONFIG,
        settings=Settings(work_dir=tmp_path / "w", orientation_check=False, _env_file=None),  # type: ignore[call-arg]
        store=store,
        classifier_for=lambda pid: TakenOver() if pid == "fort-grounds" else _Golden(),  # type: ignore[arg-type,return-value]
        clock=lambda: NOW,
        monotonic=lambda: 0.0,
    ).run(Options(property_ids=("fort-grounds", "lolo-peak-village")))
    by_property = {o.property_id: o for o in outcomes if o.period == "2026-09"}
    assert by_property["fort-grounds"].version == 1  # the build it had started
    assert by_property["lolo-peak-village"].note == "deferred: another run holds the lease"
    assert store.status_name(lolo.to_domain(), "2026-09") is None
    assert Lease.model_validate_json(store.read_lease() or "").owner == "newer"  # not released
