"""The review gate (SPEC §6.8) and its report (SPEC §6.9)."""

from crr.review.report import render_review
from crr.review.rules import (
    EXPLANATIONS,
    REVIEW_CODES,
    ReviewVerdict,
    confidence_reasons,
    decide,
    page_count_drift,
)

__all__ = [
    "EXPLANATIONS",
    "REVIEW_CODES",
    "ReviewVerdict",
    "confidence_reasons",
    "decide",
    "page_count_drift",
    "render_review",
]
