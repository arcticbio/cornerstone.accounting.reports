"""One bad property-month must not stop the run (SPEC §18.9).

Before this was enforced, anything that raised while checking a month — an index someone
edited, a folder named like a month that is not one, a store error — ended the run there: every
property after it went unchecked on every run, and the root summary, the reviewer's sign that
the job is alive, was never written again. Real June files, golden labels, several properties.
"""

from __future__ import annotations

import io
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader, PdfWriter

from crr.classify.golden_classifier import GoldenClassifier
from crr.config import load_config
from crr.golden import load_all_golden
from crr.intake.decide import Kind
from crr.intake.reconcile import Options, Outcome, Reconciler, RunAborted
from crr.intake.state import MonthState, VersionEntry
from crr.models import BuildStatus
from crr.repository.intake_local import LocalIntakeStore
from crr.settings import Settings

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))
BUNDLE = Path("data/bundle/2026-06")
START = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
UNCHECKED = "STATUS - Could not be checked - will retry.txt"
BUILT_V1 = "STATUS - Built v1 (current).txt"
HEALTHY = ("fort-grounds", "lolo-peak-village")
CORNERSTONE = {
    "cornerstone_balance_sheet": "01 Cornerstone - Balance Sheet.pdf",
    "cornerstone_profit_loss_ytd": "02 Cornerstone - Profit and Loss YTD Comparison.pdf",
}


def _june(pid: str, role: str) -> Path:
    entry = CONFIG.properties.property(pid)
    pm = CONFIG.properties.manager(entry.property_manager)
    inputs = BUNDLE / pm.folder / entry.folder / "2026-06 June" / "inputs"
    return inputs / (pm.pm_source_filename if role == "pm_source" else CORNERSTONE[role])


class Golden:
    needs_page_images = False
    prompt_version: str | None = None
    name = "golden"

    def __init__(self, pid: str) -> None:
        self._inner = GoldenClassifier(GOLDEN[pid])

    def classify(self, doc, schema, pages):  # type: ignore[no-untyped-def]
        return self._inner.classify(doc, schema, pages)


class World:
    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "drive"
        self.now = START
        self.store: Any = LocalIntakeStore(self.root, CONFIG.properties)
        self.settings = Settings(
            work_dir=tmp / "work",
            orientation_check=False,
            _env_file=None,  # type: ignore[call-arg]
        )
        self.classifier_for: Any = Golden

    def prop(self, pid: str):  # type: ignore[no-untyped-def]
        return CONFIG.properties.property(pid).to_domain()

    def month(self, pid: str, period: str) -> Path:
        return self.store.month_dir(self.prop(pid), period)

    def put(self, pid: str, period: str, role: str, content: bytes | None = None) -> None:
        folder = self.month(pid, period) / CONFIG.properties.component_folders[role]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{role}.pdf"
        if content is None:
            shutil.copy(_june(pid, role), path)
        else:
            path.write_bytes(content)
        os.utime(path, (self.now.timestamp(),) * 2)

    def upload_all(self, pid: str, period: str = "2026-09") -> None:
        for role in ("pm_source", *CORNERSTONE):
            self.put(pid, period, role)

    def run(self, **options: Any) -> list[Outcome]:
        return Reconciler(
            config=CONFIG,
            settings=self.settings,
            store=self.store,
            classifier_for=self.classifier_for,
            clock=lambda: self.now,
            monotonic=lambda: 0.0,
        ).run(Options(**options))

    def status(self, pid: str, period: str = "2026-09") -> str | None:
        found = LocalIntakeStore(self.root, CONFIG.properties).read_status(self.prop(pid), period)
        return found[0] if found else None

    def summary(self) -> str:
        return (self.root / "_STATUS - All properties.txt").read_text()

    def poison_index(self, pid: str, period: str = "2026-09", *, with_status: bool) -> None:
        """An index the current code cannot read — what an older image meets after a rollback,
        or what a person's edit in Drive leaves behind."""
        output = self.month(pid, period) / "output"
        (output / "manifests").mkdir(parents=True, exist_ok=True)
        (output / "manifests" / "state.json").write_text('{"versions": [], "note": "edited"}')
        if with_status:
            (output / BUILT_V1).write_text("v1 was built from exactly the files listed below.")


@pytest.fixture
def world(tmp_path: Path) -> World:
    w = World(tmp_path)
    for pid in HEALTHY:
        w.upload_all(pid)
    w.now += timedelta(minutes=61)
    return w


def _errors(outcomes: list[Outcome]) -> list[tuple[str, str, str]]:
    return [(o.property_id, o.period, o.note) for o in outcomes if o.kind is Kind.ERROR]


def test_a_bad_index_in_one_month_does_not_stop_the_others(world: World) -> None:
    # bridgewater/2026-09 sorts before every healthy month, so it used to stop them all.
    world.poison_index("bridgewater", with_status=True)
    outcomes = world.run()
    assert _errors(outcomes) == [("bridgewater", "2026-09", "ValidationError")]
    assert [world.status(pid) for pid in HEALTHY] == [BUILT_V1, BUILT_V1]
    # Its output/ stops claiming a state nobody has checked.
    assert world.status("bridgewater") == UNCHECKED
    summary = world.summary()
    assert "Fort Grounds - September 2026 - Built v1 (current)" in summary
    assert "Lolo Peak Village - September 2026 - Built v1 (current)" in summary
    assert (
        "Bridgewater - September 2026 - Could not be checked - will retry (ValidationError)"
        in summary
    )
    assert summary.index("Could not be checked on this run") > summary.index("Fort Grounds")

    # Once the index is readable again, the month's status is decided as usual.
    (world.month("bridgewater", "2026-09") / "output" / "manifests" / "state.json").unlink()
    world.now += timedelta(minutes=30)
    assert _errors(world.run()) == []
    assert world.status("bridgewater") != UNCHECKED
    assert "Could not be checked" not in world.summary()


def test_a_month_that_never_showed_a_status_is_not_given_one(world: World) -> None:
    world.poison_index("bridgewater", with_status=False)
    outcomes = world.run()
    assert _errors(outcomes) == [("bridgewater", "2026-09", "ValidationError")]
    assert world.status("bridgewater") is None  # the summary and the log carry it instead
    assert "Bridgewater - September 2026 - Could not be checked" in world.summary()


def test_a_folder_that_only_looks_like_a_month_is_ignored(world: World) -> None:
    stray = world.month("fort-grounds", "2026-09").parent / "2026-13 misc"
    stray.mkdir()
    outcomes = world.run()
    assert _errors(outcomes) == []
    assert [world.status(pid) for pid in HEALTHY] == [BUILT_V1, BUILT_V1]
    assert sorted(p.name for p in stray.iterdir()) == []  # never prepared, never written


def test_a_store_error_for_one_property_does_not_stop_the_others(world: World) -> None:
    real = world.store

    class Flaky:
        """Drive answering 503 for one property's folders; the drive client does not retry."""

        def __getattr__(self, name: str) -> Any:
            return getattr(real, name)

        def list_component(self, prop, period, folder):  # type: ignore[no-untyped-def]
            if prop.id == "bridgewater":
                raise OSError("503 Service Unavailable")
            return real.list_component(prop, period, folder)

    world.store = Flaky()
    outcomes = world.run()
    assert _errors(outcomes) == [
        ("bridgewater", "2026-10", "OSError"),
        ("bridgewater", "2026-11", "OSError"),
    ]
    assert [world.status(pid) for pid in HEALTHY] == [BUILT_V1, BUILT_V1]
    assert world.summary().count("Could not be checked - will retry (OSError)") == 2


def test_a_classifier_that_cannot_be_built_stops_the_run(world: World) -> None:
    """A missing API key is the run's problem: it must not be written into every month."""

    def unavailable(_pid: str) -> Any:
        raise RunAborted("the anthropic classifier cannot be built")

    world.classifier_for = unavailable
    with pytest.raises(RunAborted):
        world.run()
    assert [world.status(pid) for pid in HEALTHY] == [None, None]


def _first_pages(src: Path, count: int) -> bytes:
    writer = PdfWriter()
    for page in PdfReader(str(src)).pages[:count]:
        writer.add_page(page)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_the_drift_check_passes_over_an_unreadable_earlier_month(world: World) -> None:
    """History is read newest first; one bad index must not blind the check to older ones."""
    july = world.prop("fort-grounds"), "2026-07"
    world.store.ensure_month(*july, [])
    world.store.write_state(
        *july,
        MonthState(
            versions=[
                VersionEntry(
                    version=1,
                    built_at=START,
                    status=BuildStatus.BUILT,
                    fingerprint="july",
                    output_file="x - v1.pdf",
                )
            ]
        ),
    )
    manifests = world.month("fort-grounds", "2026-07") / "output" / "manifests"
    (manifests / "v1.json").write_text('{"inputs": [{"role": "pm_source", "pages": 16}]}')
    world.poison_index("fort-grounds", "2026-08", with_status=False)
    # September: the PM report arrives with 3 pages instead of 16.
    shutil.rmtree(world.month("fort-grounds", "2026-09"))
    world.upload_all("fort-grounds")
    world.put(
        "fort-grounds", "2026-09", "pm_source", _first_pages(_june("fort-grounds", "pm_source"), 3)
    )
    world.now += timedelta(minutes=61)
    outcomes = world.run(property_ids=("fort-grounds",))
    assert _errors(outcomes) == [("fort-grounds", "2026-08", "ValidationError")]
    state = world.store.read_state(world.prop("fort-grounds"), "2026-09")
    assert state is not None and state.latest is not None
    assert "page_count_drift" in state.latest.review_codes
