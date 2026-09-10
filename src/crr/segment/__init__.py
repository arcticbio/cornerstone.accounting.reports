"""Run-length segmentation and record mapping (SPEC §6.4)."""

from crr.segment.records import UNRESOLVED, map_qualifier, normalise_qualifier
from crr.segment.segmenter import UNKNOWN, Segmentation, segment

__all__ = [
    "UNKNOWN",
    "UNRESOLVED",
    "Segmentation",
    "map_qualifier",
    "normalise_qualifier",
    "segment",
]
