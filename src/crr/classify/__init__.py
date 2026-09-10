"""Page classification (SPEC §7)."""

from crr.classify.footer_check import FooterVerdict, apply_footer_check, check_footer
from crr.classify.golden_classifier import GoldenClassifier, GoldenLabelMissing
from crr.classify.protocol import ClassificationResult, Classifier, PageInput, Usage

__all__ = [
    "ClassificationResult",
    "Classifier",
    "FooterVerdict",
    "GoldenClassifier",
    "GoldenLabelMissing",
    "PageInput",
    "Usage",
    "apply_footer_check",
    "check_footer",
]
