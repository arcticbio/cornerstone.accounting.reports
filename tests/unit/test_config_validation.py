"""Config loading and the six rejections SPEC §9.6 requires."""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.config import ConfigError, load_config

CONFIG = Path("config")
BAD = Path("tests/unit/fixtures/bad-config")


def test_the_shipped_config_is_valid() -> None:
    bundle = load_config(CONFIG)
    assert set(bundle.schemas) == {"cobalt", "cornerstone-qbo", "mccathren", "rentmanager-missoula"}
    assert set(bundle.outputs) == {
        "cobalt-investor-report",
        "mccathren-investor-report",
        "missoula-investor-report",
    }
    assert len(bundle.properties.properties) == 8
    assert bundle.sha256["properties.yaml"]


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("unknown-semantic", "unknown semantic tag"),
        ("duplicate-section-id", "duplicate section id"),
        ("invalid-cardinality", "cardinality"),
        ("duplicate-footer-label", "duplicate footer_label"),
        ("undeclared-source-alias", "undeclared source alias"),
        ("drop-unknown-section", "does not declare"),
    ],
)
def test_each_bad_config_is_rejected(fixture: str, expected: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_config(BAD / fixture)
    assert any(expected in problem for problem in excinfo.value.problems), excinfo.value.problems


def test_every_problem_is_reported_not_just_the_first(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "schemas" / "broken.yaml").write_text(
        "schema_id: broken\nversion: 1\nproducer: p\nsystem: s\ntext_layer: always\n"
        "fingerprint: {description: d}\n"
        "sections:\n"
        "  - {id: a, semantic: nope, cardinality: many, text_cues: [x]}\n"
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(tmp_path)
    problems = excinfo.value.problems
    assert len(problems) >= 3  # bad semantic, bad cardinality, missing properties.yaml
    assert any("properties.yaml is missing" in p for p in problems)


def test_section_display_title_humanises_the_id() -> None:
    bundle = load_config(CONFIG)
    cobalt = bundle.schemas["cobalt"]
    assert cobalt.section("cash_flow_12_month").display_title == "Cash Flow 12 Month"


def test_period_helpers() -> None:
    registry = load_config(CONFIG).properties
    assert registry.period_folder("2026-06") == "2026-06 June"
    assert registry.period_label("2026-06") == "June 2026"
    assert registry.period_folder("2026-09") == "2026-09 September"
    with pytest.raises(ValueError, match="not YYYY-MM"):
        registry.period_folder("June 2026")
    with pytest.raises(ValueError, match="no month"):
        registry.period_folder("2026-13")


def test_input_filenames_are_per_manager() -> None:
    registry = load_config(CONFIG).properties
    names = registry.input_filenames("fort-grounds")
    assert names["pm_source"] == "05 PM Source - Missoula PM Baseline.pdf"
    assert names["cornerstone_balance_sheet"] == "01 Cornerstone - Balance Sheet.pdf"
    assert registry.input_filenames("timber-place")["pm_source"] == (
        "05 PM Source - McCathren Baseline.pdf"
    )
