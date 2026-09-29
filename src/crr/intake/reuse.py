"""Carry page labels over from the previous version for inputs that did not change (SPEC §18.7).

Correcting a one-page Balance Sheet should not re-classify a 26-page PM source. A document's
labels are reused only when everything that produced them is the same: the uploaded bytes
(`source_sha256`, taken before OCR), the schema it was classified against, and the classifier —
name, model and prompt version. Anything else is classified afresh.
"""

from __future__ import annotations

from crr.classify.protocol import ClassificationResult, Classifier, PageInput, Usage
from crr.config.models import SourceSchema
from crr.log import get_logger
from crr.manifest.model import BuildManifest, InputRef
from crr.models import SourceDocument

log = get_logger(__name__)


def classifier_matches(
    previous: BuildManifest, name: str, model: str | None, prompt: str | None
) -> bool:
    block = previous.classifier
    return block.name == name and block.model == model and block.prompt_version == prompt


def reusable_input(
    previous: BuildManifest | None,
    *,
    role: str,
    source_sha256: str,
    schema_sha256: str | None,
    classifier: tuple[str, str | None, str | None],
) -> InputRef | None:
    """The previous build's record of this input, if its labels can stand for this build."""
    if previous is None or not schema_sha256 or not classifier_matches(previous, *classifier):
        return None
    for ref in previous.inputs:
        if (
            ref.role == role
            and (ref.source_sha256 or ref.sha256) == source_sha256
            and ref.schema_sha256 == schema_sha256
        ):
            labelled = {c.page for c in previous.classifications if c.doc_role == role}
            if labelled == set(range(1, ref.pages + 1)):
                return ref
    return None


class ReusingClassifier:
    """Wraps the real classifier; answers from the previous manifest where it safely can."""

    def __init__(
        self,
        inner: Classifier,
        previous: BuildManifest | None,
        *,
        model: str | None,
        schema_sha256: dict[str, str],
    ) -> None:
        self._inner = inner
        self._previous = previous
        self._model = model
        self._schema_sha256 = schema_sha256
        self.name = inner.name
        self.needs_page_images = getattr(inner, "needs_page_images", True)
        self.prompt_version: str | None = getattr(inner, "prompt_version", None)
        #: Roles whose labels were carried over in this build.
        self.reused: list[str] = []

    def identity(self) -> tuple[str, str | None, str | None]:
        return self.name, self._model, self.prompt_version

    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult:
        ref = reusable_input(
            self._previous,
            role=doc.role,
            source_sha256=doc.source_sha256 or doc.sha256,
            schema_sha256=self._schema_sha256.get(doc.schema_id),
            classifier=self.identity(),
        )
        if ref is not None and self._previous is not None:
            wanted = {p.page for p in pages}
            labels = [
                c.model_copy()
                for c in self._previous.classifications
                if c.doc_role == doc.role and c.page in wanted
            ]
            if {c.page for c in labels} == wanted:
                self.reused.append(doc.role)
                log.info("classify.reused", role=doc.role, pages=len(labels))
                return ClassificationResult(
                    pages=sorted(labels, key=lambda c: c.page), usage=Usage()
                )
        return self._inner.classify(doc, schema, pages)
