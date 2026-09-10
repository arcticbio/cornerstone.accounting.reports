"""The CLI surface exists and the Phase 0 stubs behave as the plan requires."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from crr import __version__
from crr.cli import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_version_prints_the_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help_without_erroring_out() -> None:
    result = runner.invoke(app, [])
    assert "validate-config" in result.stdout
    assert "eval" in result.stdout


def test_validate_config_loads_the_shipped_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 0, result.stdout
    assert "properties: 1 file(s) loaded" in result.stdout


def test_validate_config_exits_1_when_config_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 1


def test_validate_config_exits_1_on_malformed_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "config" / "schemas").mkdir(parents=True)
    (tmp_path / "config" / "outputs").mkdir(parents=True)
    (tmp_path / "config" / "properties.yaml").write_text("a: [1, 2\n")
    (tmp_path / "config" / "schemas" / "s.yaml").write_text("id: s\n")
    (tmp_path / "config" / "outputs" / "o.yaml").write_text("id: o\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 1


def test_eval_stub_exits_zero() -> None:
    result = runner.invoke(app, ["eval", "--classifier", "golden", "--gate"])
    assert result.exit_code == 0
    assert "eval not implemented" in result.stdout
