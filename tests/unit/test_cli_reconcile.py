"""`crr reconcile` from the command line (SPEC §11, §18.9): exit codes and what it prints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from crr.cli import app
from crr.config import load_config
from crr.intake.calendar import period_of
from crr.intake.lease import LEASE_FILE, Lease
from crr.repository.intake_local import LocalIntakeStore

CONFIG = load_config(Path("config"))
runner = CliRunner()


def test_a_month_that_cannot_be_checked_fails_the_run_after_the_rest(tmp_path: Path) -> None:
    """Every other month is still checked and the summary still written; then exit 1, so the
    execution shows as failed and someone reads the log."""
    root = tmp_path / "intake"
    store = LocalIntakeStore(root, CONFIG.properties)
    period = period_of(datetime.now(UTC).date())  # the run's own clock: always an open month
    prop = CONFIG.properties.property("bridgewater").to_domain()
    manifests = store.month_dir(prop, period) / "output" / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "state.json").write_text('{"versions": [], "note": "edited"}')

    result = runner.invoke(
        app,
        ["reconcile", "--repo", "local", "--classifier", "golden", "--work-dir", str(tmp_path)],
        env={"CRR_INTAKE_ROOT": str(root)},
    )
    assert result.exit_code == 1, result.output
    assert f"bridgewater          {period}  Could not be checked - will retry" in result.stdout
    assert "[ValidationError]" in result.stdout
    assert "1 month(s) could not be checked" in result.output
    summary = (root / "_STATUS - All properties.txt").read_text()
    assert "Bridgewater - " in summary and "Could not be checked - will retry" in summary
    # The other seven properties had this month and the next prepared as usual.
    other = store.month_dir(CONFIG.properties.property("waypointe").to_domain(), period)
    assert (other / "output").is_dir()


def test_a_run_that_finds_another_holding_the_lease_does_nothing(tmp_path: Path) -> None:
    """Azure's scheduled run and an Actions run at once: the second says so and exits 0."""
    root = tmp_path / "intake"
    now = datetime.now(UTC)
    LocalIntakeStore(root, CONFIG.properties).write_lease(
        Lease(
            owner="azure",
            host="crr-quarterly-abc12",
            acquired_at=now,
            expires_at=now + timedelta(minutes=30),
        ).model_dump_json()
    )
    result = runner.invoke(
        app,
        ["reconcile", "--repo", "local", "--classifier", "golden", "--work-dir", str(tmp_path)],
        env={"CRR_INTAKE_ROOT": str(root)},
    )
    assert result.exit_code == 0, result.output
    assert "nothing done: another run (crr-quarterly-abc12) holds the lease until" in result.stdout
    assert sorted(p.name for p in root.iterdir()) == [LEASE_FILE]


def test_a_run_with_nothing_to_build_writes_no_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The write check runs once, just before a run's first build (SPEC §18.9) — not at the
    start of every run, where it left a trashed probe in the shared drive 48 times a day."""
    probes: list[str] = []
    monkeypatch.setattr(LocalIntakeStore, "preflight_publish", lambda self: probes.append("p"))
    result = runner.invoke(
        app,
        ["reconcile", "--repo", "local", "--classifier", "golden", "--work-dir", str(tmp_path)],
        env={"CRR_INTAKE_ROOT": str(tmp_path / "intake")},
    )
    assert result.exit_code == 0, result.output
    assert probes == []
