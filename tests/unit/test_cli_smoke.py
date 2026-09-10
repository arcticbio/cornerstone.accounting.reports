"""Phase 0 scaffold checks: the CLI is importable and its stub commands exit 0."""

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


def test_eval_stub_exits_zero() -> None:
    result = runner.invoke(app, ["eval", "--classifier", "golden"])
    assert result.exit_code == 0
