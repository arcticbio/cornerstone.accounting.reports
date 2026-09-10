"""The address grammar (SPEC §5).

    address     := source_alias ":" section_ref [ "@" record ] [ "#" occurrence ]
    source_alias:= identifier
    section_ref := section_id | "*"
    record      := record_id | "{record}"
    occurrence  := integer >= 1
    identifier  := [A-Za-z0-9_-]+

Hand-written, per the spec: a regex would parse the happy path but could not say *which*
production failed, and every error here becomes a config-validation message a human reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+")

#: The placeholder a `for_each_record` item uses in place of a concrete record id.
RECORD_PLACEHOLDER = "{record}"

#: `section_ref` wildcard: every section found in the source, in source order.
WILDCARD = "*"


class AddressError(ValueError):
    """A malformed address. The message names the production that failed."""


@dataclass(frozen=True, slots=True)
class Address:
    source_alias: str
    section_ref: str
    record: str | None = None
    occurrence: int | None = None

    @property
    def is_wildcard(self) -> bool:
        return self.section_ref == WILDCARD

    @property
    def is_record_templated(self) -> bool:
        return self.record == RECORD_PLACEHOLDER

    def with_record(self, record_id: str) -> Address:
        """Bind `{record}` to a concrete record id (what `for_each_record` does)."""
        return Address(self.source_alias, self.section_ref, record_id, self.occurrence)

    def render(self) -> str:
        text = f"{self.source_alias}:{self.section_ref}"
        if self.record is not None:
            text += f"@{self.record}"
        if self.occurrence is not None:
            text += f"#{self.occurrence}"
        return text


def _identifier(text: str, production: str, address: str) -> str:
    if not text:
        raise AddressError(f"{address!r}: {production} is empty")
    if not _IDENTIFIER.fullmatch(text):
        raise AddressError(
            f"{address!r}: {production} {text!r} is not an identifier ([A-Za-z0-9_-]+)"
        )
    return text


def parse_address(address: str) -> Address:
    """Parse an address, or raise `AddressError` naming the production that failed."""
    if not isinstance(address, str) or not address.strip():
        raise AddressError("address is empty")
    text = address.strip()

    # occurrence: trailing "#n"
    occurrence: int | None = None
    if "#" in text:
        text, _, raw_occurrence = text.partition("#")
        if not raw_occurrence:
            raise AddressError(f"{address!r}: occurrence is empty after '#'")
        if not raw_occurrence.isdigit():
            raise AddressError(f"{address!r}: occurrence {raw_occurrence!r} is not an integer")
        occurrence = int(raw_occurrence)
        if occurrence < 1:
            raise AddressError(f"{address!r}: occurrence must be >= 1, got {occurrence}")

    # record: "@record" or "@{record}"
    record: str | None = None
    if "@" in text:
        text, _, raw_record = text.partition("@")
        if raw_record == RECORD_PLACEHOLDER:
            record = RECORD_PLACEHOLDER
        else:
            record = _identifier(raw_record, "record", address)

    if ":" not in text:
        raise AddressError(f"{address!r}: expected 'source_alias:section_ref'")
    raw_alias, _, raw_section = text.partition(":")
    if ":" in raw_section:
        raise AddressError(f"{address!r}: more than one ':' separator")
    source_alias = _identifier(raw_alias, "source_alias", address)
    section_ref = (
        WILDCARD if raw_section == WILDCARD else _identifier(raw_section, "section_ref", address)
    )

    if section_ref == WILDCARD and record is not None:
        raise AddressError(f"{address!r}: '*' cannot be qualified with a record")
    if section_ref == WILDCARD and occurrence is not None:
        raise AddressError(f"{address!r}: '*' cannot be qualified with an occurrence")

    return Address(source_alias, section_ref, record, occurrence)
