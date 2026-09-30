"""The live test of 30 September 2026: four hours, hands off, on what changed since the first.

B is a half-hour tick of the Azure schedule; every time below is minutes after it, and runs
start at B, B+30, … B+240. Nobody runs, forces or helps the system: property managers and
Cornerstone accounting upload into the month folders the schedule prepared, and a reviewer
tidies an output folder and then follows the status's own advice. Nothing is carried over from
the first test: its months were moved out of production, every file uploaded here is a fresh
export (`conductor.FRESH_EXPORTS`), and every first build classifies from scratch.

What it validates, each against predictions written before B:

- **D-26, the 30-minute settle.** A month is built by the first run starting 30 or more minutes
  after its last upload. River Falls October's last upload lands ~32 minutes before the B+60
  run, which builds it; Timber Place October's ~27 minutes before, and it waits for B+90.
- **F2, a deferred month says so.** September's eight reports land within three minutes. The
  B+150 run has eight fresh September builds to start, about 20 minutes of work, then four
  October months: two first builds (`Ready - building on the next run`) and two corrections
  (`Built v1 - newer files ready, building next run`). The B+180 run builds them.
- **F3, a missing report is named.** A reviewer trashes Lolo Peak Village October's v1 from
  `output/`; the status says `Built v1 - report file missing`; the reviewer restores it from
  the shared drive's Trash, as the status advises, and the status reads current again.
- **Capacity: reused labels are not cross-checked again.** Six one-file rebuilds, three on the
  big reports (Bridgewater 24 pages, Timber Place 25 scanned, River Falls 29 scanned). Each
  classify step should take seconds; on 29 September the same rebuilds took 25 to 57 s.
- **D-25, the documented exception.** Missoula exports Lolo Peak Village's report and files it
  as Mullan Crossing's. Rent Manager's `Property:` line matches no Mullan Crossing record, so
  it lands as `Needs review (v1)` with `unresolved_record`; the right report then builds v2.
- **ec061b7, one publish probe per building run.** The runs at B, B+30 and B+210 have nothing
  to build and write no probe; each of the other six writes exactly one.
"""

from __future__ import annotations

from plan import (
    ACCOUNTING,
    BS,
    COBALT,
    DS,
    MCCATHREN,
    MISSOULA,
    NAMES,
    OCT,
    PL,
    PM,
    PM_WHO,
    REVIEWER,
    SEP,
    Act,
    Expect,
)

__all__ = ["ACTS", "BS", "DS", "EXPECTS", "OCT", "PL", "PM", "SEP", "Act", "Expect"]

END_OFFSET = 240  # the last tick whose run is observed
BUDGET_USD = 25.0  # no new scenario starts past this model spend; ~$8 is expected
FRESH_EXPORTS = True
TEST_MONTHS = ("2026-09 September", "2026-10 October")

_MONTH = {SEP: ("September", "Sep", "09"), OCT: ("October", "Oct", "10")}
_COBALT_CODE = {"bridgewater": "411", "salmon-crossing": "405"}


def owner_report_name(prop: str, period: str, suffix: str = "") -> str:
    """How each manager names its export: its own habit, not ours."""
    month, mon, mm = _MONTH[period]
    n = NAMES[prop]
    who = PM_WHO[prop]
    if who == MISSOULA:
        return f"{n} - Owner Report - {month} 2026{suffix}.pdf"
    if who == MCCATHREN:
        return f"{n} Owner Packet {mm}-2026{suffix}.pdf"
    assert who == COBALT
    return f"{_COBALT_CODE[prop]} {n} Owner Statement {mon} 2026{suffix}.pdf"


def accounting_name(prop: str, period: str, what: str, suffix: str = "") -> str:
    return f"{NAMES[prop]} {what} 2026-{_MONTH[period][2]}{suffix}.pdf"


def full_set(
    sid: str,
    at: float,
    prop: str,
    period: str,
    *,
    pm_at: float | None = None,
    pm_src: str = "pm",
    ds: bool = True,
    note: str = "",
) -> list[Act]:
    """A month's files: accounting's statements at `at`, the manager's report at `pm_at`."""
    pm_time = at if pm_at is None else pm_at
    acts = [
        Act(
            pm_time,
            sid,
            PM_WHO[prop],
            "upload",
            prop,
            period,
            PM,
            pm_src,
            owner_report_name(prop, period),
            note=note,
        ),
        Act(
            at,
            sid,
            ACCOUNTING,
            "upload",
            prop,
            period,
            BS,
            "bs",
            accounting_name(prop, period, "Balance Sheet"),
        ),
        Act(
            at + 0.5,
            sid,
            ACCOUNTING,
            "upload",
            prop,
            period,
            PL,
            "pl",
            accounting_name(prop, period, "P&L YTD"),
        ),
    ]
    if ds:
        acts.append(
            Act(
                at + 0.5,
                sid,
                ACCOUNTING,
                "upload",
                prop,
                period,
                DS,
                "ds",
                accounting_name(prop, period, "Distribution Schedule"),
            )
        )
    return acts


def reissue(sid: str, at: float, prop: str, period: str, role: str, src: str, note: str) -> Act:
    what = {BS: "Balance Sheet", PL: "P&L YTD"}[role]
    suffix = " reissued" if src.endswith("reissued") else " corrected"
    return Act(
        at,
        sid,
        ACCOUNTING,
        "upload",
        prop,
        period,
        role,
        src,
        accounting_name(prop, period, what, suffix),
        note=note,
    )


# Month-major build order (SPEC §18.9): September's months, alphabetical by property id, then
# October's — bridgewater, fort-grounds, lolo-peak-village, mullan-crossing, river-falls,
# salmon-crossing, timber-place, waypointe.

ACTS: list[Act] = [
    # --- October, an orderly month for four Missoula properties (built at B+60).
    *full_set("O1", 2, "fort-grounds", OCT, ds=False),
    Act(
        20,
        "O1",
        ACCOUNTING,
        "upload",
        "fort-grounds",
        OCT,
        DS,
        "ds",
        accounting_name("fort-grounds", OCT, "Distribution Schedule"),
        note="the optional schedule, 18 minutes later: absorbed into v1, not a v2",
    ),
    *full_set("O2", 2, "lolo-peak-village", OCT),
    *full_set("O3", 3, "mullan-crossing", OCT, ds=False),
    *full_set("O4", 3, "waypointe", OCT),
    # --- The settle boundary (D-26): River Falls lands ~32 minutes before the B+60 run starts,
    # Timber Place ~27. Runs take their clock ~20 s after the tick (SPEC §18.5).
    *full_set("O5", 27.5, "river-falls", OCT, note="~32 min before the B+60 run"),
    *full_set("O6", 32.5, "timber-place", OCT, note="~27 min before the B+60 run"),
    # --- F3: a reviewer tidies Lolo Peak Village's output folder, then follows the status.
    Act(
        80,
        "O2",
        REVIEWER,
        "trash_output",
        "lolo-peak-village",
        OCT,
        name="- v1.pdf",
        note="a reviewer deletes the published v1 by mistake",
    ),
    Act(
        100,
        "O2",
        REVIEWER,
        "untrash",
        "lolo-peak-village",
        OCT,
        name="- v1.pdf",
        note="the reviewer restores it from the shared drive's Trash, as the status advises",
    ),
    # --- A one-file rebuild: Mullan Crossing's schedule after its v1 (built at B+120).
    Act(
        75,
        "O3",
        ACCOUNTING,
        "upload",
        "mullan-crossing",
        OCT,
        DS,
        "ds",
        accounting_name("mullan-crossing", OCT, "Distribution Schedule"),
        note="the optional schedule after v1",
    ),
    # --- Two October corrections that settle in time for the B+150 run, which defers them.
    reissue("O4", 105, "waypointe", OCT, PL, "pl-corrected", "a corrected P&L"),
    reissue("O1", 110, "fort-grounds", OCT, BS, "bs-corrected", "a corrected Balance Sheet"),
    # --- Quarter-end: every September file within three minutes, and Cobalt's October with it.
    # Accounting posts its statements first; the managers' reports follow.
    *full_set("S1", 95, "bridgewater", SEP, pm_at=97),
    *full_set("S2", 95, "fort-grounds", SEP, pm_at=96),
    *full_set("S3", 95, "lolo-peak-village", SEP, pm_at=96),
    *full_set(
        "S4",
        95,
        "mullan-crossing",
        SEP,
        pm_at=96,
        pm_src="pm@lolo-peak-village",
        note="Missoula exports Lolo Peak Village's report and files it as Mullan Crossing's",
    ),
    *full_set("S5", 95, "river-falls", SEP, pm_at=96.5),
    *full_set("S6", 95, "salmon-crossing", SEP, pm_at=97),
    *full_set("S7", 95, "timber-place", SEP, pm_at=96.5),
    *full_set("S8", 95, "waypointe", SEP, pm_at=96),
    *full_set("O7", 96, "bridgewater", OCT, pm_at=97),
    *full_set("O8", 96, "salmon-crossing", OCT, pm_at=97),
    # --- After the crunch: the right Mullan Crossing report, and three reissued Balance Sheets
    # on the big reports (built at B+240).
    Act(
        200,
        "S4",
        MISSOULA,
        "upload",
        "mullan-crossing",
        SEP,
        PM,
        "pm",
        owner_report_name("mullan-crossing", SEP, " (corrected)"),
        note="the right report; the wrong one is set aside, not deleted",
    ),
    reissue("S1", 200, "bridgewater", SEP, BS, "bs-reissued", "reissued; 24-page report reused"),
    reissue("S5", 200, "river-falls", SEP, BS, "bs-reissued", "reissued; 29-page scan reused"),
    reissue("S7", 200, "timber-place", SEP, BS, "bs-reissued", "reissued; 25-page scan reused"),
]

READY = "Ready - building on the next run"
NEWER_READY = "newer files ready, building next run"
QUICK = "classify_max_s:20"  # on 29 September the same one-file rebuilds took 25 to 57 s

EXPECTS: list[Expect] = [
    # O1 Fort Grounds Oct: the late schedule absorbed; a correction deferred, then built.
    Expect("O1", "fort-grounds", OCT, 30, "Waiting for uploads to settle", 0),
    Expect(
        "O1",
        "fort-grounds",
        OCT,
        60,
        "Built v1 (current)",
        1,
        "with the schedule",
        "",
        "omitted:none",
    ),
    Expect(
        "O1", "fort-grounds", OCT, 120, "Built v1 - newer files waiting", 1, "correction settling"
    ),
    Expect(
        "O1",
        "fort-grounds",
        OCT,
        150,
        f"Built v1 - {NEWER_READY}",
        1,
        "F2: deferred",
        "",
        "body:reached its time limit",
    ),
    Expect(
        "O1",
        "fort-grounds",
        OCT,
        180,
        "Built v2 (current)",
        2,
        "one call, labels reused",
        "",
        QUICK,
    ),
    # O2 Lolo Peak Village Oct: F3.
    Expect("O2", "lolo-peak-village", OCT, 30, "Waiting for uploads to settle", 0),
    Expect("O2", "lolo-peak-village", OCT, 60, "Built v1 (current)", 1),
    Expect(
        "O2",
        "lolo-peak-village",
        OCT,
        90,
        "Built v1 - report file missing",
        1,
        "F3",
        "",
        "body:restore it from the shared drive's Trash",
    ),
    Expect(
        "O2", "lolo-peak-village", OCT, 120, "Built v1 (current)", 1, "restored; no new version"
    ),
    Expect("O2", "lolo-peak-village", OCT, 240, "Built v1 (current)", 1, "still v1 at the end"),
    # O3 Mullan Crossing Oct: built without the schedule, then a one-file rebuild with it.
    Expect("O3", "mullan-crossing", OCT, 30, "Waiting for uploads to settle", 0),
    Expect(
        "O3",
        "mullan-crossing",
        OCT,
        60,
        "Built v1 (current)",
        1,
        "without the schedule",
        "",
        "omitted:some",
    ),
    Expect(
        "O3", "mullan-crossing", OCT, 90, "Built v1 - newer files waiting", 1, "schedule settling"
    ),
    Expect("O3", "mullan-crossing", OCT, 120, "Built v2 (current)", 2, "schedule added", "", QUICK),
    # O4 WayPointe Oct: a correction deferred, then built.
    Expect("O4", "waypointe", OCT, 30, "Waiting for uploads to settle", 0),
    Expect("O4", "waypointe", OCT, 60, "Built v1 (current)", 1),
    Expect("O4", "waypointe", OCT, 120, "Built v1 - newer files waiting", 1, "correction settling"),
    Expect(
        "O4",
        "waypointe",
        OCT,
        150,
        f"Built v1 - {NEWER_READY}",
        1,
        "F2: deferred",
        "",
        "body:reached its time limit",
    ),
    Expect(
        "O4", "waypointe", OCT, 180, "Built v2 (current)", 2, "one call, labels reused", "", QUICK
    ),
    # O5 / O6: the settle boundary.
    Expect("O5", "river-falls", OCT, 30, "Waiting for uploads to settle", 0),
    Expect(
        "O5",
        "river-falls",
        OCT,
        60,
        "Built v1 (current)",
        1,
        "D-26: ~32 min after its last upload (60-min rule: B+90)",
        "",
        "body:30 or more minutes",
    ),
    Expect(
        "O6",
        "timber-place",
        OCT,
        60,
        "Waiting for uploads to settle",
        0,
        "D-26: ~27 min after its last upload",
    ),
    Expect("O6", "timber-place", OCT, 90, "Built v1 (current)", 1, "scanned source, OCR"),
    # O7 / O8: October first builds deferred behind September's.
    Expect("O7", "bridgewater", OCT, 120, "Waiting for uploads to settle", 0),
    Expect(
        "O7", "bridgewater", OCT, 150, READY, 0, "F2: deferred", "", "body:reached its time limit"
    ),
    Expect("O7", "bridgewater", OCT, 180, "Built v1 (current)", 1),
    Expect("O8", "salmon-crossing", OCT, 120, "Waiting for uploads to settle", 0),
    Expect("O8", "salmon-crossing", OCT, 150, READY, 0, "F2: deferred"),
    Expect("O8", "salmon-crossing", OCT, 180, "Built v1 (current)", 1),
    # S1-S8 September: settling at B+120, the crunch at B+150.
    *[
        Expect(sid, prop, SEP, 120, "Waiting for uploads to settle", 0)
        for sid, prop in (
            ("S1", "bridgewater"),
            ("S2", "fort-grounds"),
            ("S3", "lolo-peak-village"),
            ("S4", "mullan-crossing"),
            ("S5", "river-falls"),
            ("S6", "salmon-crossing"),
            ("S7", "timber-place"),
            ("S8", "waypointe"),
        )
    ],
    Expect("S1", "bridgewater", SEP, 150, "Built v1 (current)", 1, "first of the crunch"),
    Expect("S2", "fort-grounds", SEP, 150, "Built v1 (current)", 1),
    Expect("S3", "lolo-peak-village", SEP, 150, "Built v1 (current)", 1),
    Expect(
        "S4",
        "mullan-crossing",
        SEP,
        150,
        "Needs review (v1)",
        1,
        "D-25: another entity's Rent Manager report",
        "",
        "codes:unresolved_record",
    ),
    Expect("S5", "river-falls", SEP, 150, "Built v1 (current)", 1),
    Expect("S6", "salmon-crossing", SEP, 150, "Built v1 (current)", 1),
    # The run's 7th and 8th builds start ~17 and ~21 minutes in: either outcome is by design.
    Expect(
        "S7",
        "timber-place",
        SEP,
        150,
        f"Built v1 (current)|{READY}",
        None,
        "7th build, starts ~17 min in",
    ),
    Expect("S8", "waypointe", SEP, 150, f"{READY}|Built v1 (current)", None, "8th, ~21 min in"),
    Expect("S7", "timber-place", SEP, 180, "Built v1 (current)", 1),
    Expect("S8", "waypointe", SEP, 180, "Built v1 (current)", 1),
    # After the crunch.
    Expect(
        "S4",
        "mullan-crossing",
        SEP,
        210,
        "Needs review (v1) - newer files waiting",
        1,
        "the wrong report set aside",
        "",
        "superseded:Owner Report - September 2026.pdf",
    ),
    Expect("S1", "bridgewater", SEP, 210, "Built v1 - newer files waiting", 1),
    Expect("S5", "river-falls", SEP, 210, "Built v1 - newer files waiting", 1),
    Expect("S7", "timber-place", SEP, 210, "Built v1 - newer files waiting", 1),
    Expect("S4", "mullan-crossing", SEP, 240, "Built v2 (current)", 2, "the right report"),
    Expect("S1", "bridgewater", SEP, 240, "Built v2 (current)", 2, "24 pages reused", "", QUICK),
    Expect("S5", "river-falls", SEP, 240, "Built v2 (current)", 2, "29 pages reused", "", QUICK),
    Expect("S7", "timber-place", SEP, 240, "Built v2 (current)", 2, "25 pages reused", "", QUICK),
    # ec061b7: a probe only in a run that builds.
    *[
        Expect("P", "*", "*", tick, None, None, note, "", f"probes:{n}")
        for tick, n, note in (
            (0, 0, "nothing uploaded yet"),
            (30, 0, "everything settling"),
            (60, 1, "five first builds"),
            (90, 1, "one first build"),
            (120, 1, "one rebuild"),
            (150, 1, "the crunch"),
            (180, 1, "the deferred builds"),
            (210, 0, "everything settling"),
            (240, 1, "four rebuilds"),
        )
    ],
]
