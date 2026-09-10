"""Mapping a classifier's `record_qualifier` onto a property record id (SPEC §5 rule 3)."""

from __future__ import annotations

import re

from crr.config.models import SectionDef
from crr.models import Property

_WS = re.compile(r"\s+")

#: Returned instead of a record id when a qualifier maps to no record. The review gate turns
#: this into `unresolved_record`.
UNRESOLVED = "\x00unresolved"


def normalise_qualifier(qualifier: str | None) -> str | None:
    """Whitespace-normalised, case-folded form used for matching."""
    if qualifier is None:
        return None
    collapsed = _WS.sub(" ", qualifier).strip()
    return collapsed.casefold() or None


def map_qualifier(prop: Property, section: SectionDef, qualifier: str | None) -> str | None:
    """Resolve a page's record qualifier to a record id.

    - A `cardinality: one` section belongs to no single record: always `None`. WayPointe's
      combined Owner Statement is the case this exists for.
    - A `per_record` section maps by exact match on `pm_name` after whitespace normalisation,
      case-insensitively.
    - On a single-record property a null qualifier means that record (single-record sources
      often print no `Property:` header).
    - Anything else is `UNRESOLVED`.
    """
    if section.cardinality == "one":
        return None
    wanted = normalise_qualifier(qualifier)
    if wanted is None:
        return prop.records[0].id if prop.is_single_record else UNRESOLVED
    for record in prop.records:
        if normalise_qualifier(record.pm_name) == wanted:
            return record.id
    return UNRESOLVED
