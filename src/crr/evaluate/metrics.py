"""Scoring a classifier against the golden labels (SPEC §8).

Pure functions over label lists: no I/O, no model, no PDFs. The harness supplies the labels.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from crr.golden import GoldenDocument
from crr.models import Orientation, PageClassification, ResolvedSection


@dataclass
class Tally:
    """Correct out of scored. `scored` is not always the page count — orientation is only
    scored where the golden file carries the key (SPEC §8)."""

    correct: int = 0
    scored: int = 0

    def add(self, is_correct: bool) -> None:
        self.scored += 1
        self.correct += int(is_correct)

    def merge(self, other: Tally) -> None:
        self.correct += other.correct
        self.scored += other.scored

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.scored if self.scored else None


@dataclass
class BoundaryScore:
    """Segment-level agreement after segmentation."""

    true_positive: int = 0
    predicted: int = 0
    actual: int = 0

    def merge(self, other: BoundaryScore) -> None:
        self.true_positive += other.true_positive
        self.predicted += other.predicted
        self.actual += other.actual

    @property
    def precision(self) -> float | None:
        return self.true_positive / self.predicted if self.predicted else None

    @property
    def recall(self) -> float | None:
        return self.true_positive / self.actual if self.actual else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or p + r == 0:
            return 0.0 if self.predicted or self.actual else None
        return 2 * p * r / (p + r)


@dataclass
class Scores:
    """Every metric SPEC §8 asks for, at one level of aggregation."""

    page: Tally = field(default_factory=Tally)
    continuation: Tally = field(default_factory=Tally)
    record: Tally = field(default_factory=Tally)
    orientation: Tally = field(default_factory=Tally)
    boundary: BoundaryScore = field(default_factory=BoundaryScore)
    #: (golden section, predicted section) → count, for the pairs that disagree.
    confusion: Counter[tuple[str, str]] = field(default_factory=Counter)

    def merge(self, other: Scores) -> None:
        self.page.merge(other.page)
        self.continuation.merge(other.continuation)
        self.record.merge(other.record)
        self.orientation.merge(other.orientation)
        self.boundary.merge(other.boundary)
        self.confusion.update(other.confusion)


def score_document(
    golden_doc: GoldenDocument,
    predicted: list[PageClassification],
    *,
    score_record: bool,
    golden_record_names: dict[str | None, str | None],
    resolve_record: Callable[[str, str | None], str | None] | None = None,
    effective_qualifiers: dict[int, str | None] | None = None,
) -> Scores:
    """Page-level metrics for one document.

    `golden_record_names` maps a golden record id to the `pm_name` a classifier would print,
    so a predicted `record_qualifier` is compared against what the source actually says.

    `resolve_record` maps `(section_id, qualifier)` to the record the pipeline would file the
    page under — `map_qualifier`, bound to this property and schema. Both sides of the
    comparison go through it, so the metric scores the record a page *lands in* rather than
    the string the model happened to print. Without it the comparison falls back to the raw
    strings, which scores a correct package wrong: Rent Manager prints the `Property:` header
    on every section-head page, the model dutifully transcribes it, and the golden files carry
    `null` on a single-record property because `map_qualifier` maps null and the matching
    `pm_name` to the same record. Measured on Fort Grounds: 8/16 on strings, 16/16 on records,
    with zero pages where the transcription changes where the page lands (A-10).

    `effective_qualifiers` supplies the qualifier each page carries *after* the continuation
    inheritance of SPEC §6.4 — `segmenter.effective_qualifiers`. Scoring the raw field instead
    penalises the model for obeying the prompt: a continuation page carrying no `Property:`
    header must return null, and on a multi-record property a bare null resolves nowhere. Both
    of WayPointe's remaining misses were pages of exactly that kind (A-10).
    """
    scores = Scores()
    by_page = {p.page: p for p in predicted}
    for page in golden_doc.pages:
        prediction = by_page.get(page.page)
        predicted_section = prediction.section_id if prediction else "<missing>"
        scores.page.add(predicted_section == page.section)
        if predicted_section != page.section:
            scores.confusion[(page.section, predicted_section)] += 1
        if prediction is not None:
            scores.continuation.add(prediction.is_continuation == page.continuation)
            if score_record:
                expected_name = golden_record_names.get(page.record)
                qualifier = (
                    prediction.record_qualifier
                    if effective_qualifiers is None
                    else effective_qualifiers.get(page.page)
                )
                if resolve_record is None:
                    correct = _normalise(qualifier) == _normalise(expected_name)
                else:
                    correct = resolve_record(page.section, qualifier) == resolve_record(
                        page.section, expected_name
                    )
                scores.record.add(correct)
            if page.orientation is not None:
                scores.orientation.add(prediction.orientation is page.orientation)
        else:
            scores.continuation.add(False)
            if score_record:
                scores.record.add(False)
            if page.orientation is not None:
                scores.orientation.add(False)
    return scores


def _normalise(value: str | None) -> str | None:
    return " ".join(value.split()).casefold() if value else None


def score_boundaries(
    golden_sections: list[ResolvedSection], predicted_sections: list[ResolvedSection]
) -> BoundaryScore:
    """Exact-span agreement between the two segmentations.

    A segment counts as correct only when its section id, record and page span all match: a
    boundary drawn one page early produces two wrong segments, which is the right penalty for
    an error that would put a page under the wrong bookmark.
    """
    golden_spans = Counter(_span(s) for s in golden_sections)
    predicted_spans = Counter(_span(s) for s in predicted_sections)
    overlap = sum((golden_spans & predicted_spans).values())
    return BoundaryScore(
        true_positive=overlap,
        predicted=sum(predicted_spans.values()),
        actual=sum(golden_spans.values()),
    )


def _span(section: ResolvedSection) -> tuple[str, str, str | None, int, int]:
    return (
        section.doc_role,
        section.section_id,
        section.record_id,
        section.pages[0],
        section.pages[-1],
    )


def orientation_of(page_orientation: Orientation | None) -> str:
    return page_orientation.value if page_orientation else "—"
