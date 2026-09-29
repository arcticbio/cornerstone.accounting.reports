"""`crr reconcile` proves the store writable only before a run's first build (SPEC §18.9 step 4).

The probe used to be written at the start of every run — 48 a day on the 30-minute schedule —
and each left a trashed file in the shared drive, though most runs build nothing. Now a run
with nothing to build writes none, and a run that builds still proves the store writable
before anything is spent: a failed probe stops the run with no model call.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from crr.intake.lease import parse
from crr.intake.reconcile import Options, Reconciler, RunAborted
from crr.repository.protocol import RepositoryError
from tests.eval.test_reconcile import CONFIG, FOLDER, FORT, SOURCE, Counting, World


class _Probing:
    """The local store, counting probes and noting the classifier calls made before the first."""

    def __init__(self, inner: Any, classifier: Counting, *, fail: bool = False) -> None:
        self.inner = inner
        self.classifier = classifier
        self.fail = fail
        self.probes = 0
        self.calls_before_first_probe: list[str] | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def preflight_publish(self) -> None:
        self.probes += 1
        if self.calls_before_first_probe is None:
            self.calls_before_first_probe = list(self.classifier.calls)
        if self.fail:
            raise RepositoryError("storageQuotaExceeded")
        self.inner.preflight_publish()


def _run(world: World, store: _Probing, **options: Any) -> None:
    Reconciler(
        config=CONFIG,
        settings=world.settings,
        store=store,  # type: ignore[arg-type]
        classifier_for=lambda _pid: world.classifier,  # type: ignore[arg-type,return-value]
        clock=lambda: world.now,
        monotonic=world._monotonic(),
    ).run(Options(property_ids=("fort-grounds",), **options))


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def _upload_october(world: World) -> None:
    for key in ("pm", "bs", "pl"):
        dest = world.store.month_dir(FORT, "2026-10") / FOLDER[key] / f"{key}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SOURCE[key], dest)


def test_a_run_with_nothing_to_build_writes_no_probe(world: World) -> None:
    store = _Probing(world.store, world.classifier)
    _run(world, store)  # empty months
    world.upload("pm", "pm.pdf")
    _run(world, store)  # waiting for the rest
    world.upload_all()
    _run(world, store)  # complete, still settling
    assert store.probes == 0


def test_a_building_run_probes_once_before_the_first_model_call(world: World) -> None:
    world.upload_all()
    _upload_october(world)
    world.later(minutes=61)
    store = _Probing(world.store, world.classifier)
    _run(world, store)  # September and October both build
    assert store.probes == 1
    assert store.calls_before_first_probe == []
    assert len(world.state().versions) == 1
    assert world.classifier.calls  # it did build

    store.probes = 0
    _run(world, store)  # the same files again: nothing to build, so no probe
    assert store.probes == 0


def test_a_failed_probe_stops_the_run_before_any_model_call(world: World) -> None:
    world.upload_all()
    world.later(minutes=61)
    store = _Probing(world.store, world.classifier, fail=True)
    with pytest.raises(RunAborted, match=r"cannot publish.*no model calls were made"):
        _run(world, store)
    assert world.classifier.calls == []
    assert not any(name.endswith(".pdf") for name in world.output())
    lease = parse(world.store.read_lease())
    assert lease is not None and lease.released_at is not None  # released on the way out


@pytest.mark.parametrize("case", ["dry run", "preflight off"])
def test_dry_runs_and_a_disabled_preflight_write_no_probe(tmp_path: Path, case: str) -> None:
    world = World(tmp_path, publish_preflight=case != "preflight off")
    world.upload_all()
    world.later(minutes=61)
    store = _Probing(world.store, world.classifier)
    _run(world, store, dry_run=case == "dry run")
    assert store.probes == 0
    if case == "preflight off":
        assert len(world.state().versions) == 1  # it still builds
