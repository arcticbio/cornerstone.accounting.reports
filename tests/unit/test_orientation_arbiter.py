"""The orientation arbiter (SPEC §7.6).

The mapping from "option D reads normally" back to an `Orientation` is the exact step the
model itself gets backwards, so it is worth pinning: the turn that made an option upright is
the turn that corrects the page, i.e. `Orientation.correcting_rotation`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from crr.classify import orientation_arbiter as arb
from crr.classify.orientation_arbiter import LETTERS, TURNS, AnthropicOrientationArbiter
from crr.models import Orientation
from crr.settings import Settings

PDF = Path("does-not-matter.pdf")


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)] if text is not None else []


class _Messages:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return _Response(self.answer)


class _Client:
    def __init__(self, answer: str) -> None:
        self.messages = _Messages(answer)


@pytest.fixture(autouse=True)
def no_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """Four distinguishable stand-ins for the rendered rotations; no PDF is opened."""
    monkeypatch.setattr(arb, "_rotations", lambda pdf, page, turns: ["aa", "bb", "cc", "dd"])


def _arbiter(answer: str, seed: int | None = 0) -> AnthropicOrientationArbiter:
    return AnthropicOrientationArbiter(
        Settings(anthropic_api_key="test"),  # type: ignore[call-arg]
        client=_Client(answer),  # type: ignore[arg-type]
        seed=seed,
    )


@pytest.mark.parametrize(
    ("turn", "expected"),
    [
        (0, Orientation.UPRIGHT),
        (90, Orientation.ROT_90_CCW),
        (180, Orientation.ROT_180),
        (270, Orientation.ROT_90_CW),
    ],
)
def test_the_upright_option_names_the_correcting_turn(
    turn: int, expected: Orientation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whichever letter the model picks, the answer is the orientation whose
    `correcting_rotation` is the turn that was applied to that option."""
    monkeypatch.setattr(arb.random.Random, "shuffle", lambda self, seq: None)
    arbiter = _arbiter(LETTERS[TURNS.index(turn)])
    assert arbiter(PDF, 3) is expected
    assert expected.correcting_rotation == turn


def test_options_are_shuffled_between_calls() -> None:
    """A fixed order would let a position-biased model look right for the wrong reason."""
    arbiter = _arbiter("A", seed=1)
    orders = {arbiter(PDF, 3) for _ in range(12)}
    assert len(orders) > 1


def test_four_labelled_images_and_one_question_are_sent() -> None:
    arbiter = _arbiter("A")
    arbiter(PDF, 3)
    content = arbiter._client.messages.calls[0]["messages"][0]["content"]  # type: ignore[attr-defined]
    assert [b["type"] for b in content] == ["text", "image"] * 4 + ["text"]
    assert [b["text"] for b in content if b["type"] == "text"][:4] == [
        f"Option {letter}:" for letter in LETTERS
    ]


@pytest.mark.parametrize("answer", ["", "  ", "B or C", "E", "I think B"])
def test_anything_but_a_single_letter_is_unsettled(answer: str) -> None:
    """A hedge is not an answer; the page goes to review instead of taking a guess."""
    assert _arbiter(answer)(PDF, 3) is None


def test_an_api_error_is_unsettled_not_an_exception() -> None:
    from anthropic import APIConnectionError

    class _Failing:
        def create(self, **kwargs: Any) -> _Response:
            raise APIConnectionError(request=None)  # type: ignore[arg-type]

    arbiter = _arbiter("A")
    arbiter._client.messages = _Failing()  # type: ignore[assignment]
    assert arbiter(PDF, 3) is None


def test_token_budget_leaves_room_to_think() -> None:
    """16 tokens returned an empty text block while the model was answering correctly, which
    read as a refusal and sent a good page to review."""
    assert arb.MAX_TOKENS >= 1000
