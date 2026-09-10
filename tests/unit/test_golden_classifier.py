"""The golden classifier and exemplar selection (SPEC §7.1, §7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.classify.golden_classifier import GoldenClassifier, GoldenLabelMissing
from crr.classify.prompts import prompt_versions, render_system_prompt, select_exemplars
from crr.config import load_config
from crr.golden import load_all_golden
from crr.models import Orientation, SourceDocument

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))


def _doc(role: str = "pm_source", pages: int = 16, schema_id: str = "rentmanager-missoula"):  # type: ignore[no-untyped-def]
    return SourceDocument(
        role=role,
        schema_id=schema_id,
        path=Path("x.pdf"),
        sha256="a" * 64,
        page_count=pages,
        has_text_layer=True,
    )


def test_it_replays_every_golden_label() -> None:
    classifier = GoldenClassifier(GOLDEN["fort-grounds"])
    result = classifier.classify(_doc(), CONFIG.schemas["rentmanager-missoula"], [])
    assert [p.section_id for p in result.pages[:3]] == [
        "owner_statement",
        "owner_statement",
        "profit_loss_comparison",
    ]
    assert all(p.confidence == 1.0 for p in result.pages)
    assert all(p.classifier == "golden" for p in result.pages)
    assert result.usage.api_calls == 0


def test_record_ids_are_rendered_back_to_the_pm_name() -> None:
    """The golden file stores the mapped record id; the classifier contract is the raw
    qualifier, so the segmenter's mapping stays under test."""
    result = GoldenClassifier(GOLDEN["waypointe"]).classify(
        _doc(), CONFIG.schemas["rentmanager-missoula"], []
    )
    assert result.pages[1].record_qualifier == "WayPointe Apartment Homes LP"
    assert result.pages[4].record_qualifier == "128 S. 5th Street West"
    assert result.pages[0].record_qualifier is None  # combined owner statement


def test_orientation_defaults_to_upright_and_is_read_when_present() -> None:
    result = GoldenClassifier(GOLDEN["timber-place"]).classify(
        _doc(schema_id="mccathren", pages=23), CONFIG.schemas["mccathren"], []
    )
    assert result.pages[2].orientation is Orientation.ROT_90_CCW
    assert result.pages[0].orientation is Orientation.UPRIGHT


def test_an_unknown_role_is_an_error_not_an_empty_result() -> None:
    with pytest.raises(GoldenLabelMissing, match="no golden labels"):
        GoldenClassifier(GOLDEN["timber-place"]).classify(
            _doc(role="cornerstone_distribution_schedule"), CONFIG.schemas["cornerstone-qbo"], []
        )


def test_labels_naming_a_section_the_schema_lacks_are_rejected() -> None:
    """A golden file that drifts from its schema must fail loudly, not produce a build."""
    golden = GOLDEN["fort-grounds"]
    with pytest.raises(GoldenLabelMissing, match="does not declare"):
        GoldenClassifier(golden).classify(_doc(), CONFIG.schemas["cobalt"], [])


class TestPrompts:
    def test_every_schema_ships_a_v1_prompt(self) -> None:
        for schema_id in CONFIG.schemas:
            assert prompt_versions(schema_id) == ["v1"], schema_id

    def test_the_catalogue_is_rendered_verbatim_from_the_yaml(self) -> None:
        schema = CONFIG.schemas["cobalt"]
        text = render_system_prompt(schema)
        for section in schema.sections:
            assert f"### {section.id}" in text
            for cue in section.text_cues:
                assert cue in text
        assert schema.fingerprint.description.strip().split("\n")[0].strip() in text

    def test_an_unknown_prompt_version_is_an_error(self) -> None:
        with pytest.raises(FileNotFoundError, match="no prompt 'v9'"):
            render_system_prompt(CONFIG.schemas["cobalt"], "v9")


class TestExemplars:
    def _images(self) -> dict[tuple[str, str, int], Path]:
        return {
            (g.property_id, doc.role, page.page): Path(f"{g.property_id}-{page.page}.png")
            for g in GOLDEN.values()
            for doc in g.documents
            for page in doc.pages
        }

    def test_exclude_same_property_keeps_the_answer_key_out(self) -> None:
        exemplars = select_exemplars(
            CONFIG.schemas["rentmanager-missoula"],
            GOLDEN,
            self._images(),
            for_property="fort-grounds",
            exemplar_policy="exclude_same_property",
        )
        assert exemplars
        assert all(e.property_id != "fort-grounds" for e in exemplars)

    def test_at_most_two_per_section(self) -> None:
        exemplars = select_exemplars(
            CONFIG.schemas["rentmanager-missoula"],
            GOLDEN,
            self._images(),
            for_property="fort-grounds",
        )
        counts: dict[str, int] = {}
        for e in exemplars:
            counts[e.section_id] = counts.get(e.section_id, 0) + 1
        assert max(counts.values()) <= 2

    def test_policy_any_may_use_the_property_under_test(self) -> None:
        """McCathren has two properties; with `any`, River Falls can still draw on itself for
        a section only it has."""
        exemplars = select_exemplars(
            CONFIG.schemas["mccathren"],
            GOLDEN,
            self._images(),
            for_property="river-falls",
            exemplar_policy="any",
        )
        sections = {e.section_id for e in exemplars}
        assert "aged_receivable" in sections  # only Timber Place has one
        assert "cover_letter" in sections

    def test_a_section_with_no_rendered_page_yields_no_exemplar(self) -> None:
        exemplars = select_exemplars(
            CONFIG.schemas["cobalt"], GOLDEN, {}, for_property="bridgewater"
        )
        assert exemplars == []
