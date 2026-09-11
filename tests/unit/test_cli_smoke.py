"""Phase 0 scaffold checks: the CLI is importable and its commands exit 0."""

from pathlib import Path

from typer.testing import CliRunner

from crr import __version__
from crr.cli import app

runner = CliRunner()


def test_version_prints_a_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_validate_config_loads_the_shipped_yaml() -> None:
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 0


def test_eval_exits_zero_and_writes_its_report_and_predictions(tmp_path: Path) -> None:
    """`--report` into tmp_path, or the run litters the committed `eval/reports/` with a
    report and a 68 KB predictions file every time anyone runs the suite."""
    report = tmp_path / "run.md"
    result = runner.invoke(app, ["eval", "--classifier", "golden", "--report", str(report)])
    assert result.exit_code == 0
    assert report.is_file()
    assert (tmp_path / "run.predictions.json").is_file()


# A second `eval` invocation in the same process trips structlog's captured stderr against
# CliRunner's per-invoke streams ("I/O operation on closed file"), so there is exactly one
# here. Replay is covered properly in tests/integration/test_eval_replay.py.


def test_a_missing_predictions_file_is_a_clean_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["eval", "--from", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
