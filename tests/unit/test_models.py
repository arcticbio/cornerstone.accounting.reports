"""Domain model invariants (SPEC §3)."""

import pytest
from pydantic import ValidationError

from crr.models import Orientation, PlanItem, Property, PropertyRecord, ResolvedSection


def test_orientation_correcting_rotation_matches_spec_table() -> None:
    # SPEC §6.5: pypdf's rotate(n) turns the page clockwise.
    assert Orientation.UPRIGHT.correcting_rotation == 0
    assert Orientation.ROT_90_CW.correcting_rotation == 270
    assert Orientation.ROT_90_CCW.correcting_rotation == 90
    assert Orientation.ROT_180.correcting_rotation == 180


def test_models_are_frozen_and_forbid_extras() -> None:
    item = PlanItem(
        output_page=1,
        doc_role="pm_source",
        source_page=3,
        section_id="owner_statement",
        record_id=None,
    )
    with pytest.raises(ValidationError):
        item.output_page = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        PlanItem(
            output_page=1,
            doc_role="pm_source",
            source_page=1,
            section_id="x",
            record_id=None,
            nonsense=True,  # type: ignore[call-arg]
        )


def test_resolved_section_requires_contiguous_pages() -> None:
    ok = ResolvedSection(
        doc_role="pm_source", section_id="rent_roll", record_id=None, pages=(4, 5, 6)
    )
    assert ok.first_page == 4
    with pytest.raises(ValidationError, match="contiguous"):
        ResolvedSection(doc_role="pm_source", section_id="rent_roll", record_id=None, pages=(4, 6))
    with pytest.raises(ValidationError, match="at least one page"):
        ResolvedSection(doc_role="pm_source", section_id="rent_roll", record_id=None, pages=())


def test_resolved_section_rejects_orientation_fixes_outside_its_pages() -> None:
    with pytest.raises(ValidationError, match="outside the section"):
        ResolvedSection(
            doc_role="pm_source",
            section_id="rent_roll",
            record_id=None,
            pages=(4, 5),
            orientation_fixes={7: Orientation.ROT_90_CW},
        )


def test_property_rejects_duplicate_record_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate record ids"):
        Property(
            id="p",
            name="P",
            folder="P",
            property_manager="pm",
            owning_entity="E",
            records=(PropertyRecord(id="a"), PropertyRecord(id="a")),
        )


def test_property_record_lookup() -> None:
    prop = Property(
        id="waypointe",
        name="WayPointe",
        folder="WayPointe",
        property_manager="missoula",
        owning_entity="WayPointe Apartment Homes LP",
        records=(PropertyRecord(id="a", pm_name="A"), PropertyRecord(id="b", pm_name="B")),
    )
    assert prop.record("b").pm_name == "B"
    assert not prop.is_single_record
    with pytest.raises(KeyError):
        prop.record("missing")
