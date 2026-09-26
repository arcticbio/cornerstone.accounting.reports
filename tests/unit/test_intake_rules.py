"""The pure rules of continuous intake (SPEC §18.3 to §18.8)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from crr.config.loader import Component
from crr.intake.calendar import add_months, closes_on, is_open, month_end, months_to_prepare
from crr.intake.decide import (
    ComponentState,
    Kind,
    after_build,
    closed,
    decide,
    held,
)
from crr.intake.files import SUPERSEDED_PREFIX, IntakeFile, choose, strip_prefix
from crr.intake.state import Attempt, InputSig, MonthState, VersionEntry, fingerprint
from crr.intake.status import (
    headline_of,
    is_status_filename,
    render_status,
    status_filename,
)
from crr.models import BuildStatus

T0 = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
PM = Component("pm_source", "1 - Property Manager Report", "required", "rentmanager-missoula")
BS = Component("cornerstone_balance_sheet", "2 - Balance Sheet", "required", "cornerstone-qbo")
PL = Component("cornerstone_profit_loss_ytd", "3 - Profit and Loss", "required", "cornerstone-qbo")
DIST = Component(
    "cornerstone_distribution_schedule", "4 - Distribution Schedule", "optional", "cornerstone-qbo"
)
ALL = (PM, BS, PL, DIST)


def pdf(name: str, minutes: int = 0, md5: str | None = None, fid: str | None = None) -> IntakeFile:
    return IntakeFile(
        id=fid or f"id-{name}",
        name=name,
        uploaded_at=T0 + timedelta(minutes=minutes),
        md5=md5 or f"md5-{name}",
    )


def folders(**by_role: list[IntakeFile]) -> tuple[ComponentState, ...]:
    key = {"pm": PM, "bs": BS, "pl": PL, "dist": DIST}
    return tuple(ComponentState(c, choose(by_role.get(k, []))) for k, c in key.items())


def full(minutes: int = 0) -> tuple[ComponentState, ...]:
    return folders(
        pm=[pdf("pm.pdf", minutes)], bs=[pdf("bs.pdf", minutes)], pl=[pdf("pl.pdf", minutes)]
    )


def run(
    components: tuple[ComponentState, ...],
    state: MonthState | None = None,
    *,
    now: datetime = T0 + timedelta(hours=2),
    force: bool = False,
):  # type: ignore[no-untyped-def]
    return decide(
        components,
        state or MonthState(),
        now=now,
        settle_minutes=60,
        max_failed_attempts=3,
        force=force,
    )


def built(components: tuple[ComponentState, ...], version: int = 1, **kw) -> MonthState:  # type: ignore[no-untyped-def]
    current = {c.component.role: c.choice.current for c in components if c.choice.current}
    entry = VersionEntry(
        version=version,
        built_at=T0 + timedelta(hours=1),
        status=kw.get("status", BuildStatus.BUILT),
        fingerprint=fingerprint(current),  # type: ignore[arg-type]
        output_file=f"x - v{version}.pdf",
        inputs=[InputSig.of(r, f) for r, f in current.items() if f],
    )
    return MonthState(versions=[entry])


# -- §18.4 choosing the file ------------------------------------------------------------
class TestChoose:
    def test_one_pdf_is_current_and_nothing_is_renamed(self) -> None:
        choice = choose([pdf("a.pdf")])
        assert choice.current is not None and choice.current.name == "a.pdf"
        assert choice.renames == () and choice.set_aside == ()

    def test_the_newest_upload_wins_and_the_rest_are_marked(self) -> None:
        old, new = pdf("old.pdf", 0), pdf("new.pdf", 30)
        choice = choose([new, old])
        assert choice.current == new
        assert choice.set_aside == (old,)
        assert choice.renames == ((old, SUPERSEDED_PREFIX + "old.pdf"),)

    def test_an_already_marked_file_is_not_marked_twice(self) -> None:
        old, new = pdf(SUPERSEDED_PREFIX + "old.pdf", 0), pdf("new.pdf", 30)
        assert choose([old, new]).renames == ()

    def test_deleting_the_newest_brings_the_older_one_back_and_unmarks_it(self) -> None:
        # After `new.pdf` is deleted, only the marked file remains: it wins and loses its mark.
        survivor = pdf(SUPERSEDED_PREFIX + "old.pdf", 0)
        choice = choose([survivor])
        assert choice.current == survivor
        assert choice.renames == ((survivor, "old.pdf"),)

    def test_a_marked_newer_upload_still_wins(self) -> None:
        # The prefix is output, never input: a person copying a marked file back in wins.
        marked_new, plain_old = pdf(SUPERSEDED_PREFIX + "x.pdf", 30), pdf("y.pdf", 0)
        choice = choose([plain_old, marked_new])
        assert choice.current == marked_new
        assert set(choice.renames) == {
            (marked_new, "x.pdf"),
            (plain_old, SUPERSEDED_PREFIX + "y.pdf"),
        }

    def test_non_pdfs_are_ignored_and_listed(self) -> None:
        photo = IntakeFile("p", "photo.jpg", T0 + timedelta(hours=1), is_pdf=False)
        choice = choose([pdf("a.pdf"), photo])
        assert choice.current is not None and choice.current.name == "a.pdf"
        assert choice.ignored == (photo,)
        assert not choice.is_empty

    def test_only_non_pdfs_means_no_current_file(self) -> None:
        photo = IntakeFile("p", "photo.jpg", T0, is_pdf=False)
        choice = choose([photo])
        assert choice.current is None and not choice.is_empty

    def test_ties_break_the_same_way_every_run(self) -> None:
        a, b = pdf("a.pdf", 0), pdf("b.pdf", 0)
        assert choose([a, b]).current == choose([b, a]).current

    def test_repeated_prefixes_are_all_stripped(self) -> None:
        assert strip_prefix("SUPERSEDED - superseded - a.pdf") == "a.pdf"


# -- §18.3 the calendar -------------------------------------------------------------------
class TestCalendar:
    def test_a_month_closes_42_days_after_it_ends(self) -> None:
        assert month_end("2026-09") == date(2026, 9, 30)
        assert closes_on("2026-09", 42) == date(2026, 11, 11)
        assert month_end("2028-02") == date(2028, 2, 29)

    def test_open_through_the_last_day_inclusive(self) -> None:
        assert is_open("2026-09", date(2026, 11, 11), 42)
        assert not is_open("2026-09", date(2026, 11, 12), 42)

    def test_the_current_and_next_month_are_prepared(self) -> None:
        assert months_to_prepare(date(2026, 12, 15), 1) == ["2026-12", "2027-01"]
        assert add_months("2026-01", -1) == "2025-12"


# -- §18.5 readiness, §18.7 when to build --------------------------------------------------
class TestDecide:
    def test_an_empty_month_writes_no_status(self) -> None:
        verdict = run(folders())
        assert verdict.kind is Kind.NONE and verdict.headline is None

    def test_missing_required_components_are_named(self) -> None:
        verdict = run(folders(pm=[pdf("pm.pdf")]))
        assert verdict.kind is Kind.WAITING
        assert verdict.headline == "Waiting for Balance Sheet, Profit and Loss"

    def test_a_missing_optional_component_does_not_block(self) -> None:
        assert run(full()).kind is Kind.BUILD

    def test_a_folder_holding_only_a_non_pdf_is_still_missing(self) -> None:
        photo = IntakeFile("p", "bs.jpg", T0, is_pdf=False)
        verdict = run(folders(pm=[pdf("pm.pdf")], bs=[photo], pl=[pdf("pl.pdf")]))
        assert verdict.headline == "Waiting for Balance Sheet"

    def test_a_recent_upload_waits_to_settle(self) -> None:
        verdict = run(full(), now=T0 + timedelta(minutes=59))
        assert verdict.kind is Kind.SETTLING
        assert verdict.headline == "Waiting for uploads to settle"
        assert run(full(), now=T0 + timedelta(minutes=60)).kind is Kind.BUILD

    def test_a_set_aside_upload_also_counts_towards_settling(self) -> None:
        # Someone uploads a replacement; until it settles, nothing builds from either file.
        components = folders(
            pm=[pdf("pm.pdf")], bs=[pdf("bs.pdf"), pdf("bs2.pdf", 100)], pl=[pdf("pl.pdf")]
        )
        assert run(components, now=T0 + timedelta(minutes=130)).kind is Kind.SETTLING

    def test_unchanged_files_are_not_rebuilt(self) -> None:
        components = full()
        verdict = run(components, built(components))
        assert verdict.kind is Kind.CURRENT
        assert verdict.headline == "Built v1 (current)"

    def test_a_review_build_consumes_its_files_too(self) -> None:
        components = full()
        verdict = run(components, built(components, status=BuildStatus.NEEDS_REVIEW))
        assert verdict.kind is Kind.REVIEW and verdict.headline == "Needs review (v1)"

    def test_a_changed_file_builds_the_next_version(self) -> None:
        state = built(full())
        changed = folders(
            pm=[pdf("pm.pdf")], bs=[pdf("bs.pdf", md5="new-content")], pl=[pdf("pl.pdf")]
        )
        assert run(changed, state).kind is Kind.BUILD

    def test_an_optional_component_arriving_later_builds_again(self) -> None:
        state = built(full())
        later = folders(
            pm=[pdf("pm.pdf")], bs=[pdf("bs.pdf")], pl=[pdf("pl.pdf")], dist=[pdf("d.pdf", 5)]
        )
        assert run(later, state).kind is Kind.BUILD

    def test_pending_changes_keep_the_last_build_in_the_headline(self) -> None:
        state = built(full())
        changed = folders(pm=[pdf("pm.pdf")], bs=[pdf("bs2.pdf", 200)], pl=[pdf("pl.pdf")])
        verdict = run(changed, state, now=T0 + timedelta(minutes=210))
        assert verdict.kind is Kind.SETTLING
        assert verdict.headline == "Built v1 - newer files waiting"

    def test_a_required_file_deleted_after_a_build(self) -> None:
        state = built(full(), status=BuildStatus.NEEDS_REVIEW)
        verdict = run(folders(pm=[pdf("pm.pdf")], pl=[pdf("pl.pdf")]), state)
        assert verdict.kind is Kind.WAITING
        assert verdict.headline == "Needs review (v1) - newer files waiting"

    def test_three_failures_stop_retrying_until_the_files_change(self) -> None:
        components = full()
        fp = fingerprint(
            {c.component.role: c.choice.current for c in components if c.choice.current}
        )  # type: ignore[misc]
        state = MonthState(attempts=[Attempt(fingerprint=fp, at=T0, error="E") for _ in range(3)])
        verdict = run(components, state)
        assert verdict.kind is Kind.STOPPED
        assert verdict.headline == "Failed 3 times, stopped retrying"
        assert run(components, state, force=True).kind is Kind.BUILD
        other = folders(pm=[pdf("pm2.pdf")], bs=[pdf("bs.pdf")], pl=[pdf("pl.pdf")])
        assert run(other, state).kind is Kind.BUILD

    def test_force_rebuilds_unchanged_files_but_never_skips_readiness(self) -> None:
        components = full()
        assert run(components, built(components), force=True).kind is Kind.BUILD
        assert run(full(), force=True, now=T0 + timedelta(minutes=5)).kind is Kind.SETTLING
        assert run(folders(pm=[pdf("pm.pdf")]), force=True).kind is Kind.WAITING

    def test_renaming_does_not_change_the_fingerprint(self) -> None:
        a = {"pm_source": pdf("pm.pdf", fid="F1", md5="M")}
        b = {"pm_source": IntakeFile("F1", "renamed.pdf", T0, md5="M")}
        assert fingerprint(a) == fingerprint(b)


class TestAfterwards:
    def test_held_without_a_previous_build(self) -> None:
        verdict = held("over the $3.00 limit", "detail", MonthState(), "fp")
        assert verdict.kind is Kind.HELD and verdict.headline == "Held - over the $3.00 limit"

    def test_held_with_a_previous_build_keeps_it_visible_and_says_held(self) -> None:
        verdict = held("x", "detail", built(full()), "fp")
        assert verdict.headline == "Built v1 - newer files held"

    def test_a_failure_with_a_previous_build_says_so(self) -> None:
        state = built(full())
        state.attempts.append(Attempt(fingerprint="fp", at=T0, error="E"))
        verdict = after_build(BuildStatus.FAILED, None, state, "fp", 3)
        assert verdict.headline == "Built v1 - newer files failed, will retry"

    def test_a_first_failure_will_retry(self) -> None:
        state = MonthState(attempts=[Attempt(fingerprint="fp", at=T0, error="E")])
        verdict = after_build(BuildStatus.FAILED, None, state, "fp", 3)
        assert verdict.headline == "Failed (attempt 1 of 3), will retry"

    def test_a_built_version_is_current(self) -> None:
        state = built(full(), version=2)
        verdict = after_build(BuildStatus.BUILT, 2, state, state.versions[0].fingerprint, 3)
        assert verdict.headline == "Built v2 (current)"

    def test_closed(self) -> None:
        assert closed(date(2026, 11, 11), built(full(), version=3)).headline == (
            "Closed 2026-11-11 (v3 is final)"
        )
        assert closed(date(2026, 11, 11), MonthState()).headline == (
            "Closed 2026-11-11 (nothing built)"
        )


# -- §18.8 the status file ----------------------------------------------------------------
class TestStatusFile:
    def test_the_filename_is_the_headline(self) -> None:
        name = status_filename("Built v2 (current)")
        assert name == "STATUS - Built v2 (current).txt"
        assert is_status_filename(name) and headline_of(name) == "Built v2 (current)"

    def test_a_headline_never_makes_a_path(self) -> None:
        assert "/" not in status_filename("Held - a/b")

    def test_the_body_explains_files_and_history(self) -> None:
        first = full()
        state = built(first)
        second = folders(
            pm=[pdf("pm.pdf")],
            bs=[pdf("bs.pdf"), pdf("bs-final.pdf", 300)],
            pl=[pdf("pl.pdf")],
            dist=[IntakeFile("j", "scan.jpg", T0, is_pdf=False)],
        )
        current = {c.component.role: c.choice.current for c in second if c.choice.current}
        state.versions.append(
            VersionEntry(
                version=2,
                built_at=T0 + timedelta(hours=7),
                status=BuildStatus.BUILT,
                fingerprint=fingerprint(current),  # type: ignore[arg-type]
                output_file="x - v2.pdf",
                inputs=[InputSig.of(r, f) for r, f in current.items() if f],
            )
        )
        verdict = run(second, state, now=T0 + timedelta(hours=8))
        body = render_status(
            property_name="Fort Grounds",
            period_label="September 2026",
            verdict=verdict,
            components=second,
            state=state,
            closes=date(2026, 11, 11),
            settle_minutes=60,
        )
        assert "Status: Built v2 (current)" in body
        assert 'Balance Sheet: "bs-final.pdf"' in body
        assert 'set aside: "SUPERSEDED - bs.pdf"' in body
        assert 'ignored: "scan.jpg" - not a PDF' in body
        assert "Distribution Schedule: none - optional" in body
        assert "v2 - 2026-10-05 16:00 UTC - built - Balance Sheet replaced" in body
        assert body.count("Balance Sheet replaced") == 1  # found by the Drive rehearsal
        assert "v1 - 2026-10-05 10:00 UTC - built - first build" in body
        assert body.index("v2 -") < body.index("v1 -")  # newest first
        assert "Changes after 2026-11-11 are ignored." in body


@pytest.mark.parametrize("minutes", [0, 59])
def test_settle_boundary(minutes: int) -> None:
    assert run(full(), now=T0 + timedelta(minutes=minutes)).kind is Kind.SETTLING
