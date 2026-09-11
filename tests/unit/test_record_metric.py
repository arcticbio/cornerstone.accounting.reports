"""The `record_qualifier` metric scores the record a page lands in (SPEC §8, A-10).

The real-model eval reported Missoula record accuracy 59.38 % (38/64) on a run where every
Missoula property resolved to its exact golden page count with no `unresolved_record`. The gap
was the metric, not the classifier: Rent Manager prints the `Property:` header on every
section-head page, the model transcribes it, and the golden files carry `null` for a
single-record property because `map_qualifier` maps null and the matching `pm_name` to the
same record. Comparing the strings scored a correct package wrong.

The labels here are real `claude-opus-5` runs over the Fort Grounds (single-record) and
WayPointe (two records) PM sources, with the evidence strings dropped — the pages themselves
never enter the repository.
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

from crr.config import load_config
from crr.evaluate.harness import _effective_by_page, _resolve_record
from crr.evaluate.metrics import score_document
from crr.golden import load_all_golden
from crr.models import PageClassification
from crr.segment.records import map_qualifier

DATA = Path(__file__).parent.parent / "data"
CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))


def _case(property_id: str = "fort-grounds"):  # type: ignore[no-untyped-def]
    golden = GOLDEN[property_id]
    doc = next(d for d in golden.documents if d.role == "pm_source")
    labels = DATA / f"{property_id}-real-model-labels.json"
    predictions = [PageClassification(**row) for row in json.loads(labels.read_text())]
    names = {r.id: r.pm_name for r in golden.records} | {None: None}
    schema = CONFIG.schemas[doc.schema_id]
    prop = CONFIG.properties.property(property_id).to_domain()
    return doc, predictions, names, schema, prop


def _score(property_id: str):  # type: ignore[no-untyped-def]
    """Score exactly as the harness does."""
    doc, predictions, names, schema, prop = _case(property_id)
    return score_document(
        doc,
        predictions,
        score_record=True,
        golden_record_names=names,
        resolve_record=partial(_resolve_record, prop, schema),
        effective_qualifiers=_effective_by_page(predictions),
    )


def test_the_transcribed_header_never_changes_where_a_page_lands() -> None:
    """The premise of the metric change: on a single-record property the qualifier the model
    prints and `null` resolve to the same record, on every page."""
    doc, predictions, _, schema, prop = _case()
    by_page = {p.page: p for p in predictions}
    for page in doc.pages:
        section = schema.section(page.section)
        predicted = map_qualifier(prop, section, by_page[page.page].record_qualifier)
        assert predicted == map_qualifier(prop, section, None), page.page


def test_scoring_the_resolved_record_is_perfect_here() -> None:
    doc, predictions, names, schema, prop = _case()
    scores = score_document(
        doc,
        predictions,
        score_record=True,
        golden_record_names=names,
        resolve_record=lambda section_id, qualifier: map_qualifier(
            prop, schema.section(section_id), qualifier
        ),
    )
    assert (scores.record.correct, scores.record.scored) == (16, 16)
    assert (scores.page.correct, scores.page.scored) == (16, 16)


def test_scoring_the_raw_string_is_what_reported_the_false_gap() -> None:
    """Kept so the regression is legible: the old comparison marks half these pages wrong."""
    doc, predictions, names, _, _ = _case()
    scores = score_document(
        doc, predictions, score_record=True, golden_record_names=names, resolve_record=None
    )
    assert scores.record.correct < scores.record.scored
    assert (scores.record.correct, scores.record.scored) == (8, 16)


def test_a_qualifier_matching_no_record_is_still_wrong() -> None:
    """The metric must not become vacuous: a name that resolves nowhere still scores wrong."""
    doc, predictions, names, schema, prop = _case()
    broken = [p.model_copy(update={"record_qualifier": "Nowhere Apartments"}) for p in predictions]
    scores = score_document(
        doc,
        broken,
        score_record=True,
        golden_record_names=names,
        resolve_record=lambda section_id, qualifier: map_qualifier(
            prop, schema.section(section_id), qualifier
        ),
    )
    # `cardinality: one` sections discard the qualifier, so only the per_record pages move.
    per_record = sum(
        1 for page in doc.pages if schema.section(page.section).cardinality == "per_record"
    )
    assert scores.record.scored - scores.record.correct == per_record
    assert per_record > 0


class TestContinuationInheritance:
    """WayPointe is the only multi-record property, and the only place a bare null on a
    continuation page can resolve nowhere."""

    def test_both_missoula_properties_score_perfectly_as_the_harness_scores_them(self) -> None:
        for property_id in ("fort-grounds", "waypointe"):
            scores = _score(property_id)
            assert (scores.record.correct, scores.record.scored) == (16, 16), property_id
            assert (scores.page.correct, scores.page.scored) == (16, 16), property_id

    def test_without_inheritance_the_continuation_pages_score_wrong(self) -> None:
        """The 2/64 that survived the first metric fix: pages 4 and 7 are `unit_availability`
        continuations where the model correctly returned null, as the prompt requires."""
        doc, predictions, names, schema, prop = _case("waypointe")
        scores = score_document(
            doc,
            predictions,
            score_record=True,
            golden_record_names=names,
            resolve_record=partial(_resolve_record, prop, schema),
            effective_qualifiers=None,
        )
        assert (scores.record.correct, scores.record.scored) == (14, 16)
        # Pages 9 and 13 are continuations too, but on `cardinality: one` sections, where the
        # qualifier is discarded outright — only a per_record continuation can resolve nowhere.
        at_risk = [
            p.page
            for p in predictions
            if p.is_continuation
            and schema.section(p.section_id).cardinality == "per_record"
            and p.record_qualifier is None
        ]
        assert at_risk == [4, 7]

    def test_inheritance_does_not_invent_a_record_across_a_section_break(self) -> None:
        """A non-continuation page with no qualifier must not inherit the previous section's:
        that would silently file a page under the wrong record."""
        doc, predictions, names, schema, prop = _case("waypointe")
        broken = [
            p.model_copy(update={"record_qualifier": None, "is_continuation": False})
            if p.page == 5
            else p
            for p in predictions
        ]
        effective = _effective_by_page(broken)
        assert effective[5] is None
        scores = score_document(
            doc,
            broken,
            score_record=True,
            golden_record_names=names,
            resolve_record=partial(_resolve_record, prop, schema),
            effective_qualifiers=effective,
        )
        assert scores.record.correct < scores.record.scored
