"""The orientation arbiter (SPEC §7.6).

Asked only when the classifier and Tesseract OSD disagree about one page, which on the golden
corpus is one page in 172. It shows the page in all four rotations, in a shuffled order, and
asks which one reads normally — a discrimination the model is good at, unlike naming the
rotation it is looking at.

The shuffle matters: the answer must not be inferable from the position of the option, or a
model that always says "B" would score well on a fixed order and tell us nothing.
"""

from __future__ import annotations

import base64
import io
import random
from pathlib import Path

import pypdfium2 as pdfium
from anthropic import Anthropic, AnthropicError
from anthropic.types import ImageBlockParam, MessageParam, TextBlockParam

from crr.log import get_logger
from crr.models import Orientation
from crr.preprocess.render import DEFAULT_DPI, DEFAULT_MAX_EDGE_PX, scale_for
from crr.settings import Settings

log = get_logger(__name__)

#: Enough room for the model to think before it answers. A budget too small to finish thinking
#: in returns an empty text block, which reads as a refusal and sends the page to review for
#: no reason; 16 tokens did exactly that while the model was answering correctly.
MAX_TOKENS = 3000
LETTERS = "ABCD"
#: Clockwise turns applied to the page image, one per option.
TURNS = (0, 90, 180, 270)

QUESTION = (
    "These are the same scanned page turned by 0, 90, 180 and 270 degrees, in an unknown "
    "order. Exactly one of them is upright — its text reads normally left-to-right and is "
    "not upside down. Answer with that single letter and nothing else."
)

#: The turn that made an option upright is the turn that corrects the page, and
#: `Orientation.correcting_rotation` is exactly that, so the mapping is its inverse.
_CORRECTION_TO_ORIENTATION = {
    0: Orientation.UPRIGHT,
    90: Orientation.ROT_90_CCW,
    180: Orientation.ROT_180,
    270: Orientation.ROT_90_CW,
}


def _rotations(pdf: Path, page: int, turns: list[int]) -> list[str]:
    """The page rendered once and turned clockwise by each of `turns`, as base64 PNGs."""
    document = pdfium.PdfDocument(str(pdf))
    try:
        pdf_page = document[page - 1]
        width, height = pdf_page.get_size()
        scale = scale_for(width, height, DEFAULT_DPI, DEFAULT_MAX_EDGE_PX)
        image = pdf_page.render(scale=scale).to_pil().convert("L")
    finally:
        document.close()
    out = []
    for turn in turns:
        buffer = io.BytesIO()
        image.rotate(-turn, expand=True).save(buffer, format="PNG")
        out.append(base64.standard_b64encode(buffer.getvalue()).decode("ascii"))
    return out


class AnthropicOrientationArbiter:
    """Settles one page's orientation by asking which rendering reads normally."""

    def __init__(
        self, settings: Settings, client: Anthropic | None = None, seed: int | None = None
    ) -> None:
        self._settings = settings
        self._client = client or Anthropic(api_key=settings.anthropic_api_key, max_retries=4)
        self._random = random.Random(seed)

    def __call__(self, pdf: Path, page: int) -> Orientation | None:
        turns = list(TURNS)
        self._random.shuffle(turns)
        try:
            images = _rotations(pdf, page, turns)
        except (OSError, pdfium.PdfiumError) as exc:
            log.warning("orientation.arbiter_render_failed", page=page, error=type(exc).__name__)
            return None

        content: list[TextBlockParam | ImageBlockParam] = []
        for letter, data in zip(LETTERS, images, strict=True):
            content.append({"type": "text", "text": f"Option {letter}:"})
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": data},
                }
            )
        content.append({"type": "text", "text": QUESTION})
        message: MessageParam = {"role": "user", "content": content}
        try:
            response = self._client.messages.create(
                model=self._settings.model,
                max_tokens=MAX_TOKENS,
                messages=[message],
            )
        except AnthropicError as exc:
            log.warning("orientation.arbiter_failed", page=page, error=type(exc).__name__)
            return None

        answer = "".join(block.text for block in response.content if block.type == "text").strip()
        # Just the letter, or nothing: a model that hedges has not settled anything.
        if len(answer) != 1 or answer not in LETTERS:
            log.warning("orientation.arbiter_unclear", page=page, length=len(answer))
            return None
        return _CORRECTION_TO_ORIENTATION[turns[LETTERS.index(answer)]]
