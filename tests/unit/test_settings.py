"""Settings defaults and overrides (SPEC §12)."""

import pytest
from pydantic import ValidationError

from crr.settings import DEFAULT_PRICE_TABLE, Settings


def test_defaults_match_spec() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.model == "claude-opus-5"
    assert s.min_confidence == 0.85
    assert s.render_dpi == 150
    assert s.repo == "local"
    assert str(s.bundle_root) == "data/bundle/2026-06"
    assert s.exemplar_policy == "exclude_same_property"
    assert s.eval_min_page_accuracy == 0.98
    assert s.eval_min_boundary_f1 == 0.98


def test_env_prefix_and_unprefixed_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRR_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("CRR_MIN_CONFIDENCE", "0.5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.model == "claude-sonnet-5"
    assert s.min_confidence == 0.5
    assert s.anthropic_api_key == "sk-test"


def test_confidence_must_be_a_probability() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, min_confidence=1.5)  # type: ignore[call-arg]


def test_price_table_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CRR_PRICE_TABLE_JSON",
        '{"claude-opus-5": {"input": 1, "cache_read": 2, "cache_write": 3, "output": 4}}',
    )
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.price_table["claude-opus-5"].input == 1.0
    # the built-in table is not mutated by an override
    assert DEFAULT_PRICE_TABLE["claude-opus-5"].input == 15.0
    assert "claude-sonnet-5" in s.price_table
