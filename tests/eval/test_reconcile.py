"""`crr reconcile` end to end over a local store, real June files and golden labels
(SPEC §18, PLAN Phase 10's rehearsal scenarios in miniature).

The clock is the test's: settling, closing and upload order are all driven by it.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from crr.classify.golden_classifier import GoldenClassifier
from crr.classify.protocol import ClassificationResult, PageInput
from crr.config import load_config
from crr.config.models import SourceSchema
from crr.golden import load_all_golden
from crr.intake.decide import Kind
from crr.intake.reconcile import Options, Reconciler
from crr.intake.state import MonthState
from crr.models import SourceDocument
from crr.repository.intake_local import LocalIntakeStore
from crr.settings import Settings

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))
FORT = CONFIG.properties.property("fort-grounds").to_domain()
JUNE = Path("data/bundle/2026-06/Missoula Property Management/Fort Grounds/2026-06 June/inputs")
SOURCE = {
    "pm": JUNE / "05 PM Source - Missoula PM Baseline.pdf",
    "bs": JUNE / "01 Cornerstone - Balance Sheet.pdf",
    "pl": JUNE / "02 Cornerstone - Profit and Loss YTD Comparison.pdf",
    "dist": JUNE / "03 Cornerstone - Investor Distribution Schedule.pdf",
}
FOLDER = {
    "pm": "1 - Property Manager Report",
    "bs": "2 - Balance Sheet",
    "pl": "3 - Profit and Loss",
    "dist": "4 - Distribution Schedule",
}
PERIOD = "2026-09"
START = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


class Counting:
    """The golden classifier, counting which roles it was actually asked about."""

    needs_page_images = False
    prompt_version: str | None = None

    def __init__(self, name: str = "golden", fail: bool = False) -> None:
        self.name = name
        self._inner = GoldenClassifier(GOLDEN["fort-grounds"])
        self.calls: list[str] = []
        self.fail = fail

    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult:
        self.calls.append(doc.role)
        if self.fail:
            raise RuntimeError("the model is down")
        result = self._inner.classify(doc, schema, pages)
        result.pages = [
            label.model_copy(update={"classifier": self.name}) for label in result.pages
        ]
        return result


class World:
    def __init__(self, tmp_path: Path, **settings: Any) -> None:
        self.root = tmp_path / "drive"
        self.now = START
        self.store = LocalIntakeStore(self.root, CONFIG.properties)
        self.classifier = Counting(settings.pop("classifier_name", "golden"))
        self.settings = Settings(
            work_dir=tmp_path / "work",
            orientation_check=False,
            _env_file=None,  # type: ignore[call-arg]
            **settings,
        )
        self.soft_deadline_passed = False

    def month(self) -> Path:
        return self.store.month_dir(FORT, PERIOD)

    def upload(
        self, key: str, name: str, *, source: Path | None = None, content: bytes | None = None
    ) -> Path:
        path = self.month() / FOLDER[key] / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is not None:
            path.write_bytes(content)
        else:
            shutil.copy(source or SOURCE[key], path)
        os.utime(path, (self.now.timestamp(), self.now.timestamp()))
        return path

    def later(self, **delta: float) -> None:
        self.now += timedelta(**delta)

    def run(self, **options: Any) -> dict[str, Any]:
        reconciler = Reconciler(
            config=CONFIG,
            settings=self.settings,
            store=self.store,
            classifier_for=lambda _pid: self.classifier,  # type: ignore[arg-type,return-value]
            clock=lambda: self.now,
            monotonic=self._monotonic(),
        )
        outcomes = reconciler.run(Options(property_ids=("fort-grounds",), **options))
        return {o.period: o for o in outcomes}

    def _monotonic(self):  # type: ignore[no-untyped-def]
        """The run's start reads 0; every later reading is past the deadline, if asked."""
        readings = iter([0.0])
        late = 1e9 if self.soft_deadline_passed else 0.0
        return lambda: next(readings, late)

    def output(self) -> list[str]:
        out = self.month() / "output"
        return sorted(p.name for p in out.iterdir()) if out.is_dir() else []

    def status(self) -> str:
        found = self.store.read_status(FORT, PERIOD)
        assert found is not None
        return found[0]

    def body(self) -> str:
        found = self.store.read_status(FORT, PERIOD)
        assert found is not None
        return found[1]

    def state(self) -> MonthState:
        state = self.store.read_state(FORT, PERIOD)
        assert state is not None
        return state

    def upload_all(self) -> None:
        for key in ("pm", "bs", "pl"):
            self.upload(key, f"{key}.pdf")


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def test_folders_are_prepared_and_an_empty_month_is_silent(world: World) -> None:
    outcome = world.run()
    for period in ("2026-10", "2026-11"):  # the current month and the next
        month = world.store.month_dir(FORT, period)
        assert sorted(p.name for p in month.iterdir()) == [*FOLDER.values(), "output"]
    assert outcome["2026-10"].kind is Kind.NONE
    assert world.store.read_status(FORT, "2026-10") is None


def test_the_whole_life_of_a_month(world: World) -> None:
    # A partial upload waits, naming what is missing.
    world.upload("pm", "PM report.pdf")
    world.run()
    assert world.status() == "STATUS - Waiting for Balance Sheet, Profit and Loss.txt"

    # Everything required arrives; the month settles for an hour before building.
    world.later(minutes=10)
    world.upload("bs", "BS.pdf")
    world.upload("pl", "P&L.pdf")
    world.later(minutes=30)
    world.run()
    assert world.status() == "STATUS - Waiting for uploads to settle.txt"
    assert world.classifier.calls == []

    world.later(minutes=31)
    result = world.run()
    assert result[PERIOD].version == 1
    assert world.status() == "STATUS - Built v1 (current).txt"
    assert "Fort Grounds - Investor Report - September 2026 - v1.pdf" in world.output()
    assert (world.month() / "output" / "manifests" / "v1.json").is_file()
    manifest = json.loads((world.month() / "output" / "manifests" / "v1.json").read_text())
    assert manifest["version"] == 1 and manifest["manifest_version"] == 2
    assert manifest["omitted_optional"] == ["Distribution Schedule"]
    assert {i["upload_name"] for i in manifest["inputs"]} == {"PM report.pdf", "BS.pdf", "P&L.pdf"}
    assert "Distribution Schedule: none - optional" in world.body()

    # Nothing changed: nothing is rebuilt, however many runs.
    calls = len(world.classifier.calls)
    world.later(hours=5)
    world.run()
    world.run()
    assert len(world.classifier.calls) == calls
    assert world.state().latest.version == 1  # type: ignore[union-attr]

    # A corrected Balance Sheet: the old one is set aside at once, v2 follows once settled,
    # and only the Balance Sheet is classified again.
    world.upload("bs", "BS corrected.pdf", source=SOURCE["bs"])
    (world.month() / FOLDER["bs"] / "BS corrected.pdf").write_bytes(
        SOURCE["bs"].read_bytes() + b"\n% corrected\n"
    )
    os.utime(world.month() / FOLDER["bs"] / "BS corrected.pdf", (world.now.timestamp(),) * 2)
    world.run()
    assert sorted(p.name for p in (world.month() / FOLDER["bs"]).iterdir()) == [
        "BS corrected.pdf",
        "SUPERSEDED - BS.pdf",
    ]
    assert world.status() == "STATUS - Built v1 - newer files waiting.txt"
    world.later(minutes=61)
    world.classifier.calls.clear()
    world.run()
    assert world.status() == "STATUS - Built v2 (current).txt"
    assert world.classifier.calls == ["cornerstone_balance_sheet"]
    v2 = json.loads((world.month() / "output" / "manifests" / "v2.json").read_text())
    reused = {i["role"]: i["reused_classification"] for i in v2["inputs"]}
    assert reused == {
        "pm_source": True,
        "cornerstone_balance_sheet": False,
        "cornerstone_profit_loss_ytd": True,
    }
    assert "v2 - " in world.body() and "Balance Sheet replaced" in world.body()
    assert "Fort Grounds - Investor Report - September 2026 - v1.pdf" in world.output()

    # Going back: delete the newer file. The older one wins again and loses its mark.
    (world.month() / FOLDER["bs"] / "BS corrected.pdf").unlink()
    world.later(minutes=61)
    world.run()
    assert sorted(p.name for p in (world.month() / FOLDER["bs"]).iterdir()) == ["BS.pdf"]
    assert world.status() == "STATUS - Built v3 (current).txt"

    # An optional component arriving later is one more version.
    world.upload("dist", "distributions.pdf")
    world.later(minutes=61)
    world.run()
    assert world.status() == "STATUS - Built v4 (current).txt"
    assert "Distribution Schedule added" in world.body()

    # After the lookback window the month closes, once, and later changes are ignored.
    world.now = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)
    world.upload("pl", "late.pdf")
    result = world.run()
    assert world.status() == "STATUS - Closed 2026-11-11 (v4 is final).txt"
    assert result[PERIOD].kind is Kind.CLOSED
    world.later(hours=1)
    assert PERIOD not in world.run()  # closed months are not even looked at again
    assert world.state().latest.version == 4  # type: ignore[union-attr]


def test_a_file_that_does_not_open_holds_the_build(world: World) -> None:
    world.upload_all()
    world.upload("bs", "scan.pdf", content=b"this is not a pdf")
    world.later(minutes=61)
    world.run()
    assert world.status() == "STATUS - Held - Balance Sheet cannot be opened.txt"
    assert '"scan.pdf" in Balance Sheet cannot be opened as a PDF' in world.body()
    assert world.classifier.calls == []


def test_non_pdfs_are_ignored_and_named(world: World) -> None:
    world.upload_all()
    world.upload("bs", "photo.jpg", content=b"jpeg")
    world.later(minutes=61)
    world.run()
    assert world.status() == "STATUS - Built v1 (current).txt"
    assert 'ignored: "photo.jpg" - not a PDF' in world.body()
    assert (world.month() / FOLDER["bs"] / "photo.jpg").is_file()  # never renamed or moved


def test_failures_retry_then_stop_until_the_files_change(world: World) -> None:
    world.classifier.fail = True
    world.upload_all()
    world.later(minutes=61)
    world.run()
    assert world.status() == "STATUS - Failed (attempt 1 of 3), will retry.txt"
    assert not any(name.endswith(".pdf") for name in world.output())
    world.run()
    world.run()
    assert world.status() == "STATUS - Failed 3 times, stopped retrying.txt"
    calls = len(world.classifier.calls)
    world.run()
    assert len(world.classifier.calls) == calls  # no fourth attempt on the same files

    world.classifier.fail = False
    world.upload("pl", "P&L v2.pdf")
    (world.month() / FOLDER["pl"] / "P&L v2.pdf").write_bytes(SOURCE["pl"].read_bytes() + b"\n%x\n")
    os.utime(world.month() / FOLDER["pl"] / "P&L v2.pdf", (world.now.timestamp(),) * 2)
    world.later(minutes=61)
    world.run()
    assert world.status() == "STATUS - Built v1 (current).txt"


def test_the_cost_ceiling_holds_and_reuse_lowers_the_estimate(tmp_path: Path) -> None:
    # 18 pages x $0.03 = $0.54 against a $0.50 ceiling. The fake is named like the real
    # classifier so the estimate applies.
    world = World(tmp_path, classifier_name="anthropic", max_build_usd=0.50)
    world.upload_all()
    world.later(minutes=61)
    world.run()
    assert world.status() == "STATUS - Held - would cost about $0.54, over the $0.50 limit.txt"
    assert world.classifier.calls == []


def test_the_soft_deadline_defers_a_build_to_the_next_run(world: World) -> None:
    world.upload_all()
    world.later(minutes=61)
    world.soft_deadline_passed = True
    result = world.run()
    assert result[PERIOD].note == "deferred to the next run"
    assert world.classifier.calls == []
    world.soft_deadline_passed = False
    world.run()
    assert world.status() == "STATUS - Built v1 (current).txt"


def test_force_rebuilds_unchanged_files(world: World) -> None:
    world.upload_all()
    world.later(minutes=61)
    world.run()
    world.run(force=True)
    assert world.status() == "STATUS - Built v2 (current).txt"
    assert "same files, rebuilt on request" in world.body()


def test_dry_run_writes_nothing(world: World) -> None:
    world.upload_all()
    world.upload("bs", "BS2.pdf")
    world.later(minutes=61)
    before = sorted(str(p) for p in world.root.rglob("*"))
    result = world.run(dry_run=True)
    assert result[PERIOD].note == "would build"
    assert sorted(str(p) for p in world.root.rglob("*")) == before
    assert world.classifier.calls == []


def test_a_month_emptied_again_does_not_keep_a_stale_status(world: World) -> None:
    path = world.upload("pm", "pm.pdf")
    world.run()
    path.unlink()
    world.run()
    assert world.status() == (
        "STATUS - Waiting for Property Manager Report, Balance Sheet, Profit and Loss.txt"
    )


def test_the_root_summary_has_a_line_per_active_property(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.upload_all()
    world.later(minutes=61)
    reconciler = Reconciler(
        config=CONFIG,
        settings=world.settings,
        store=world.store,
        classifier_for=lambda _pid: world.classifier,  # type: ignore[arg-type,return-value]
        clock=lambda: world.now,
        monotonic=lambda: 0.0,
    )
    reconciler.run()
    summary = (world.root / "_STATUS - All properties.txt").read_text()
    assert "Fort Grounds - September 2026 - Built v1 (current)" in summary
    assert "Timber Place" not in summary  # nothing uploaded there


def test_an_overlapping_run_that_published_the_same_files_wins(tmp_path: Path) -> None:
    """Two runs building the same month at once publish one version, not two (§18.9)."""
    world = World(tmp_path)
    world.upload_all()
    world.later(minutes=61)
    other = World(tmp_path)  # a second run over the same folders, started meanwhile
    other.now = world.now
    inner = world.classifier
    ran_other = []

    class Overlapping(Counting):
        def classify(self, doc, schema, pages):  # type: ignore[no-untyped-def]
            if not ran_other:
                ran_other.append(True)
                other.run()  # finishes and publishes while this build is mid-classification
            return inner.classify(doc, schema, pages)

    world.classifier = Overlapping()
    result = world.run()
    assert result[PERIOD].note == "duplicate"
    assert world.state().latest.version == 1  # type: ignore[union-attr]
    assert [n for n in world.output() if n.endswith(".pdf")] == [
        "Fort Grounds - Investor Report - September 2026 - v1.pdf"
    ]
    assert world.status() == "STATUS - Built v1 (current).txt"


def test_status_and_summary_never_carry_page_text(tmp_path: Path) -> None:
    """Only filenames, times and version numbers reach the status files (SPEC §16)."""
    from crr.preprocess.text import page_texts

    world = World(tmp_path)
    world.upload_all()
    world.upload("dist", "d.pdf")
    world.later(minutes=61)
    world.run()
    world.run(force=True)
    written = world.body() + "\n".join(p.read_text() for p in world.root.glob("_STATUS*.txt"))
    fragments = {
        line.strip()
        for source in SOURCE.values()
        for text in page_texts(source)
        for line in text.splitlines()
        if len(line.strip()) >= 12
    }
    assert fragments, "the fixture should have text to look for"
    # The system's own vocabulary may coincide with a page heading; that is not a leak.
    allowed = {c.label for c in CONFIG.components_for("fort-grounds")} | {FORT.name}
    leaked = sorted(f for f in fragments - allowed if f in written)
    assert leaked == []
