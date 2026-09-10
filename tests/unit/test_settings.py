"""Settings load from the environment as SPEC §12 documents."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from crr.settings import DEFAULT_PRICE_TABLE, Settings

CLASSIFIER_KEY_VARS = ("CRR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
ALL_VARS = (
    *CLASSIFIER_KEY_VARS,
    "CRR_MODEL",
    "CRR_MIN_CONFIDENCE",
    "CRR_RENDER_DPI",
    "CRR_BUNDLE_ROOT",
    "CRR_REPO",
    "CRR_WORK_DIR",
    "CRR_GDRIVE_ROOT_FOLDER_ID",
    "CRR_GOOGLE_SERVICE_ACCOUNT_B64",
    "GOOGLE_SERVICE_ACCOUNT_B64",
    "CRR_PRICE_TABLE_JSON",
    "CRR_EXEMPLAR_POLICY",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate every test from the ambient environment and from a repo-root .env."""
    for var in ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)


def test_defaults_match_the_spec_table() -> None:
    settings = Settings()
    assert settings.model == "claude-opus-5"
    assert settings.min_confidence == 0.85
    assert settings.render_dpi == 150
    assert settings.max_parallel_docs == 2
    assert settings.bundle_root == Path("data/bundle/2026-06")
    assert settings.repo == "local"
    assert settings.work_dir == Path("work")
    assert settings.exemplar_policy == "exclude_same_property"
    assert settings.eval_min_page_accuracy == 0.98
    assert settings.eval_min_boundary_f1 == 0.98
    assert settings.anthropic_api_key is None
    assert settings.has_classifier_key is False


@pytest.mark.parametrize("var", CLASSIFIER_KEY_VARS)
def test_classifier_key_is_read_from_either_name(var: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """CRR_ANTHROPIC_API_KEY is the documented name; ANTHROPIC_API_KEY stays a fallback.

    Claude Code on the web strips the unprefixed name, which is why the prefixed one exists.
    """
    monkeypatch.setenv(var, "sk-ant-test")
    settings = Settings()
    assert settings.has_classifier_key is True
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-test"


def test_prefixed_classifier_key_wins_over_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fallback")
    monkeypatch.setenv("CRR_ANTHROPIC_API_KEY", "preferred")
    assert Settings().anthropic_api_key is not None
    assert Settings().anthropic_api_key.get_secret_value() == "preferred"  # type: ignore[union-attr]


def test_secrets_do_not_appear_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """SecretStr keeps keys out of logs and tracebacks (SPEC §16)."""
    monkeypatch.setenv("CRR_ANTHROPIC_API_KEY", "sk-ant-do-not-leak")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_B64", "Z29vZ2xlLXNlY3JldA==")
    settings = Settings()
    dumped = repr(settings) + str(settings.model_dump())
    assert "sk-ant-do-not-leak" not in dumped
    assert "Z29vZ2xlLXNlY3JldA==" not in dumped


def test_gdrive_credentials_need_both_halves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_B64", "Z29vZ2xl")
    assert Settings().has_gdrive_credentials is False
    monkeypatch.setenv("CRR_GDRIVE_ROOT_FOLDER_ID", "folder-id")
    assert Settings().has_gdrive_credentials is True


def test_price_table_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().price_table == DEFAULT_PRICE_TABLE
    override = {
        "claude-opus-5": {"input": 1.0, "cache_read": 0.1, "cache_write": 1.25, "output": 5.0}
    }
    monkeypatch.setenv("CRR_PRICE_TABLE_JSON", json.dumps(override))
    assert Settings().price_table == override


def test_bad_price_table_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRR_PRICE_TABLE_JSON", "{not json")
    with pytest.raises(ValidationError, match="not valid JSON"):
        Settings()


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("CRR_REPO", "dropbox"),
        ("CRR_MIN_CONFIDENCE", "1.5"),
        ("CRR_RENDER_DPI", "0"),
        ("CRR_EXEMPLAR_POLICY", "whatever"),
    ],
)
def test_out_of_range_values_are_rejected(
    var: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(var, value)
    with pytest.raises(ValidationError):
        Settings()
