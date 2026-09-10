"""The eval harness (SPEC §8)."""

from crr.evaluate.harness import DocumentResult, EvalResult, evaluate, gate_failures
from crr.evaluate.metrics import BoundaryScore, Scores, Tally, score_boundaries, score_document
from crr.evaluate.report import render_report, report_filename

__all__ = [
    "BoundaryScore",
    "DocumentResult",
    "EvalResult",
    "Scores",
    "Tally",
    "evaluate",
    "gate_failures",
    "render_report",
    "report_filename",
    "score_boundaries",
    "score_document",
]
