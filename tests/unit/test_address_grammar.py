"""The address grammar, every production and every error (SPEC §5)."""

from __future__ import annotations

import pytest

from crr.resolve.address import RECORD_PLACEHOLDER, Address, AddressError, parse_address


def test_source_alias_and_section_ref() -> None:
    a = parse_address("pm:owner_statement")
    assert a == Address("pm", "owner_statement")
    assert not a.is_wildcard
    assert not a.is_record_templated


def test_wildcard_section_ref() -> None:
    a = parse_address("pm:*")
    assert a.is_wildcard
    assert a.section_ref == "*"


def test_record_qualifier() -> None:
    a = parse_address("pm:unit_availability@waypointe-ah-lp")
    assert a.record == "waypointe-ah-lp"


def test_record_placeholder() -> None:
    a = parse_address("pm:profit_loss_comparison@{record}")
    assert a.record == RECORD_PLACEHOLDER
    assert a.is_record_templated
    assert a.with_record("128-s-5th-street-west").record == "128-s-5th-street-west"


def test_occurrence() -> None:
    a = parse_address("pm:balance_sheet#2")
    assert a.occurrence == 2


def test_record_and_occurrence_together() -> None:
    a = parse_address("pm:delinquency@waypointe-ah-lp#3")
    assert (a.source_alias, a.section_ref, a.record, a.occurrence) == (
        "pm",
        "delinquency",
        "waypointe-ah-lp",
        3,
    )


def test_identifiers_allow_digits_dashes_and_underscores() -> None:
    a = parse_address("cs_bs:rent_roll_12@128-s-5th-street-west")
    assert a.source_alias == "cs_bs"
    assert a.section_ref == "rent_roll_12"
    assert a.record == "128-s-5th-street-west"


@pytest.mark.parametrize(
    ("address", "message"),
    [
        ("", "address is empty"),
        ("   ", "address is empty"),
        ("pm", "expected 'source_alias:section_ref'"),
        (":owner_statement", "source_alias is empty"),
        ("pm:", "section_ref is empty"),
        ("pm:a:b", "more than one ':'"),
        ("p m:owner_statement", "source_alias"),
        ("pm:owner statement", "section_ref"),
        ("pm:owner_statement@", "record is empty"),
        ("pm:owner_statement@bad record", "record"),
        ("pm:owner_statement#", "occurrence is empty"),
        ("pm:owner_statement#x", "not an integer"),
        ("pm:owner_statement#0", "must be >= 1"),
        ("pm:*@record-1", "'*' cannot be qualified with a record"),
        ("pm:*#2", "'*' cannot be qualified with an occurrence"),
    ],
)
def test_errors_name_the_failing_production(address: str, message: str) -> None:
    with pytest.raises(AddressError, match=message.replace("*", r"\*")):
        parse_address(address)


@pytest.mark.parametrize(
    "address",
    ["pm:owner_statement", "pm:*", "pm:x@r", "pm:x#2", "pm:x@r#2", "pm:x@{record}"],
)
def test_render_round_trips(address: str) -> None:
    assert parse_address(address).render() == address
