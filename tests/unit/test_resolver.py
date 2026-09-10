"""Flow resolution: for_each_record, wildcards, drop, optional handling, bookmarks
(SPEC §5, §6.5)."""

from __future__ import annotations

import pytest

from crr.config.models import (
    Fingerprint,
    FlowGroup,
    FlowLeaf,
    OutputDefinition,
    SectionDef,
    SourceAlias,
    SourceSchema,
    Transforms,
)
from crr.models import Orientation, PageClassification, Property, PropertyRecord
from crr.resolve.resolver import ResolveError, resolve
from crr.segment.segmenter import segment

SCHEMA = SourceSchema(
    schema_id="pmschema",
    version=1,
    producer="p",
    system="s",
    text_layer="always",
    fingerprint=Fingerprint(description="d"),
    sections=(
        SectionDef(
            id="owner_statement", semantic="owner_statement", cardinality="one", text_cues=("x",)
        ),
        SectionDef(
            id="profit_loss",
            semantic="income_statement",
            cardinality="per_record",
            text_cues=("x",),
        ),
        SectionDef(id="ledger", semantic="general_ledger", cardinality="one", text_cues=("x",)),
        SectionDef(
            id="extra", semantic="narrative", cardinality="one", text_cues=("x",), optional=True
        ),
    ),
)
SCHEMAS = {"pmschema": SCHEMA}


def _prop(*records: tuple[str, str]) -> Property:
    return Property(
        id="p",
        name="Property",
        folder="P",
        property_manager="pm",
        owning_entity="E",
        records=tuple(PropertyRecord(id=i, pm_name=n) for i, n in records),
    )


SINGLE = _prop(("default", "The Property"))
MULTI = _prop(("a", "Alpha LP"), ("b", "Beta LP"))


def _page(
    page: int,
    section: str,
    cont: bool = False,
    qualifier: str | None = None,
    orientation: Orientation = Orientation.UPRIGHT,
) -> PageClassification:
    return PageClassification(
        doc_role="pm_source",
        page=page,
        section_id=section,
        is_continuation=cont,
        record_qualifier=qualifier,
        orientation=orientation,
        confidence=1.0,
        evidence="e",
        classifier="golden",
    )


def _segments(pages: list[PageClassification], prop: Property) -> dict:
    return {"pm_source": segment(pages, SCHEMA, prop, "pm_source")}


def _output(flow: tuple, drop: tuple[str, ...] = (), **kwargs: object) -> OutputDefinition:
    return OutputDefinition(
        output_id="test-output",
        version=1,
        property_manager="pm",
        title_template="{property} - {period_label}",
        sources={"pm": SourceAlias(schema="pmschema", role="pm_source")},
        flow=flow,
        drop=drop,
        transforms=Transforms(autorotate=True, add_bookmarks=True),
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_simple_flow_places_pages_in_flow_order_not_source_order() -> None:
    pages = [_page(1, "owner_statement"), _page(2, "profit_loss")]
    output = _output(
        (
            FlowLeaf(address="pm:profit_loss", bookmark="P&L"),
            FlowLeaf(address="pm:owner_statement", bookmark="Owner Statement"),
        )
    )
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert [(i.output_page, i.source_page) for i in result.plan] == [(1, 2), (2, 1)]
    assert not result.reasons


def test_for_each_record_repeats_in_properties_yaml_order() -> None:
    pages = [
        _page(1, "profit_loss", qualifier="Beta LP"),  # source order is Beta first ...
        _page(2, "profit_loss", qualifier="Alpha LP"),
    ]
    output = _output(
        (
            FlowGroup(
                for_each_record=(
                    FlowLeaf(address="pm:profit_loss@{record}", bookmark="P&L - {record_name}"),
                )
            ),
        )
    )
    result = resolve(output, MULTI, _segments(pages, MULTI), SCHEMAS, "June 2026")
    # ... but the output follows properties.yaml record order (D-07).
    assert [(i.source_page, i.record_id) for i in result.plan] == [(2, "a"), (1, "b")]
    assert [i.bookmark for i in result.plan] == ["P&L - Alpha LP", "P&L - Beta LP"]


def test_per_record_without_a_record_qualifier_emits_every_record_in_order() -> None:
    pages = [
        _page(1, "profit_loss", qualifier="Beta LP"),
        _page(2, "profit_loss", qualifier="Alpha LP"),
    ]
    output = _output((FlowLeaf(address="pm:profit_loss", bookmark="P&L"),))
    result = resolve(output, MULTI, _segments(pages, MULTI), SCHEMAS, "June 2026")
    assert [i.record_id for i in result.plan] == ["a", "b"]


def test_single_record_property_drops_the_record_name_suffix() -> None:
    pages = [_page(1, "profit_loss")]
    output = _output(
        (
            FlowGroup(
                for_each_record=(
                    FlowLeaf(address="pm:profit_loss@{record}", bookmark="P&L - {record_name}"),
                )
            ),
        )
    )
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert result.plan[0].bookmark == "P&L"


def test_bookmark_only_on_the_first_page_of_a_section() -> None:
    pages = [_page(1, "owner_statement"), _page(2, "owner_statement", cont=True)]
    output = _output((FlowLeaf(address="pm:owner_statement", bookmark="Owner Statement"),))
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert [i.bookmark for i in result.plan] == ["Owner Statement", None]


def test_wildcard_expands_in_source_order_minus_drops() -> None:
    pages = [_page(1, "owner_statement"), _page(2, "ledger"), _page(3, "profit_loss")]
    output = _output((FlowLeaf(address="pm:*", bookmark="{section_title}"),), drop=("pm:ledger",))
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert [i.source_page for i in result.plan] == [1, 3]
    assert [d.section_id for d in result.dropped] == ["ledger"]
    assert [i.bookmark for i in result.plan] == ["Owner Statement", "Profit Loss"]


def test_a_section_in_neither_flow_nor_drop_is_unmapped() -> None:
    pages = [_page(1, "owner_statement"), _page(2, "ledger")]
    output = _output((FlowLeaf(address="pm:owner_statement", bookmark="Owner"),))
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert [r.code for r in result.reasons] == ["unmapped_section"]
    assert result.reasons[0].page == 2


def test_a_missing_required_section_is_a_review_reason() -> None:
    pages = [_page(1, "owner_statement")]
    output = _output(
        (
            FlowLeaf(address="pm:owner_statement", bookmark="Owner"),
            FlowLeaf(address="pm:profit_loss", bookmark="P&L"),
        )
    )
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert [r.code for r in result.reasons] == ["missing_required"]


def test_an_optional_flow_item_may_resolve_to_nothing() -> None:
    pages = [_page(1, "owner_statement")]
    output = _output(
        (
            FlowLeaf(address="pm:owner_statement", bookmark="Owner"),
            FlowLeaf(address="pm:extra", bookmark="Extra", required=False),
        )
    )
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert not result.reasons
    assert result.page_count == 1


def test_a_missing_source_file_is_missing_required_only_when_required() -> None:
    output = _output((FlowLeaf(address="pm:owner_statement", bookmark="Owner"),))
    result = resolve(output, SINGLE, {}, SCHEMAS, "June 2026", present_roles=set())
    assert [r.code for r in result.reasons] == ["missing_required"]

    optional = _output((FlowLeaf(address="pm:owner_statement", bookmark="Owner", required=False),))
    result = resolve(optional, SINGLE, {}, SCHEMAS, "June 2026", present_roles=set())
    assert not result.reasons


def test_occurrence_selects_the_nth_instance_and_clears_the_cardinality_reason() -> None:
    pages = [_page(1, "ledger"), _page(2, "ledger")]  # two instances of a 'one' section
    output = _output((FlowLeaf(address="pm:ledger#2", bookmark="Ledger"),), drop=("pm:ledger",))
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert [i.source_page for i in result.plan] == [2]


def test_a_one_section_found_twice_without_disambiguation_is_a_cardinality_violation() -> None:
    pages = [_page(1, "ledger"), _page(2, "ledger")]
    output = _output((FlowLeaf(address="pm:ledger", bookmark="Ledger"),))
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert "cardinality_violation" in {r.code for r in result.reasons}


def test_autorotate_adds_the_correcting_rotation_to_the_transform_list() -> None:
    pages = [_page(1, "owner_statement", orientation=Orientation.ROT_90_CCW)]
    output = _output((FlowLeaf(address="pm:owner_statement", bookmark="Owner"),))
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert result.plan[0].transforms == ("copy", "rotate:90")


def test_autorotate_off_leaves_the_page_alone() -> None:
    pages = [_page(1, "owner_statement", orientation=Orientation.ROT_180)]
    output = _output((FlowLeaf(address="pm:owner_statement", bookmark="Owner"),))
    output = output.model_copy(update={"transforms": Transforms(autorotate=False)})
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert result.plan[0].transforms == ("copy",)


def test_every_page_is_placed_dropped_or_a_review_reason() -> None:
    pages = [_page(1, "owner_statement"), _page(2, "ledger"), _page(3, "unknown")]
    output = _output(
        (FlowLeaf(address="pm:owner_statement", bookmark="Owner"),), drop=("pm:ledger",)
    )
    result = resolve(output, SINGLE, _segments(pages, SINGLE), SCHEMAS, "June 2026")
    assert result.unaccounted_pages == {}


def test_record_placeholder_outside_for_each_record_is_a_bug_not_a_review_reason() -> None:
    output = _output((FlowLeaf(address="pm:profit_loss@{record}", bookmark="P&L"),))
    with pytest.raises(ResolveError, match="outside for_each_record"):
        resolve(output, SINGLE, _segments([_page(1, "profit_loss")], SINGLE), SCHEMAS, "June 2026")
