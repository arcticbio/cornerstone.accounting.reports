"""`crr reconcile`: make every open property-month match what its folders hold (SPEC §18.9).

Stateless between runs — everything is re-read from the store — so a missed, duplicated or
crashed run needs no recovery: the next one sees the true state and carries on. The only
thing that decides *what* to build is `crr.intake.decide`; this module gathers the facts,
applies the file-level holds that need the files themselves, runs the v1 pipeline unchanged,
and publishes the result as the next version.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from crr.classify.orientation_check import OrientationArbiter
from crr.classify.protocol import Classifier
from crr.compose.composer import output_filename
from crr.config.loader import Component, ConfigBundle
from crr.intake.calendar import closes_on, is_open, months_to_prepare
from crr.intake.decide import (
    ComponentState,
    Kind,
    Verdict,
    after_build,
    built_headline,
    closed,
    current_files,
    decide,
    held,
)
from crr.intake.files import choose
from crr.intake.reuse import ReusingClassifier, reusable_input
from crr.intake.state import Attempt, InputSig, MonthState, VersionEntry
from crr.intake.status import (
    headline_of,
    render_status,
    render_summary,
    status_filename,
    summary_line,
)
from crr.intake.store import IntakeStore
from crr.log import get_logger
from crr.manifest.model import BuildManifest
from crr.manifest.writer import write_manifest
from crr.models import BuildStatus, PeriodId, Property, SourceDocument
from crr.pipeline import build_property
from crr.preprocess.text import document_text_layer, page_count, sha256_file
from crr.review.report import render_review
from crr.settings import Settings

log = get_logger(__name__)

ClassifierFactory = Callable[[str], Classifier]


@dataclass(frozen=True)
class Options:
    property_ids: tuple[str, ...] = ()
    period: PeriodId | None = None
    force: bool = False
    dry_run: bool = False


@dataclass
class Outcome:
    """One line of the run's report."""

    property_id: str
    period: PeriodId
    kind: Kind
    headline: str | None
    version: int | None = None
    usd: float = 0.0
    note: str = ""


@dataclass
class _Month:
    prop: Property
    period: PeriodId
    components: tuple[Component, ...]
    states: tuple[ComponentState, ...] = ()
    state: MonthState = field(default_factory=MonthState)


class Reconciler:
    def __init__(
        self,
        *,
        config: ConfigBundle,
        settings: Settings,
        store: IntakeStore,
        classifier_for: ClassifierFactory,
        arbiter: OrientationArbiter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.settings = settings
        self.store = store
        self.classifier_for = classifier_for
        self.arbiter = arbiter
        self.clock = clock
        self.monotonic = monotonic

    # -- the run ---------------------------------------------------------------------------
    def run(self, options: Options | None = None) -> list[Outcome]:
        options = options or Options()
        started = self.monotonic()
        now = self.clock()
        today = now.date()
        wanted = options.property_ids or tuple(p.id for p in self.config.properties.properties)
        outcomes: list[Outcome] = []
        open_months: list[_Month] = []

        for property_id in wanted:
            prop = self.config.properties.property(property_id).to_domain()
            components = self.config.components_for(property_id)
            existing = set(self.store.list_months(prop))
            prepare = set(months_to_prepare(today, self.settings.folders_ahead))
            for period in sorted(existing | prepare):
                if options.period and period != options.period:
                    continue
                if is_open(period, today, self.settings.lookback_days):
                    if not options.dry_run:
                        self.store.ensure_month(prop, period, [c.folder for c in components])
                    open_months.append(_Month(prop, period, components))
                elif period in existing:
                    closing = self._close(prop, period, components, options)
                    if closing is not None:
                        outcomes.append(closing)

        # Oldest month first across every property: the month nearest its deadline goes first.
        open_months.sort(key=lambda m: (m.period, m.prop.id))
        latest_line: dict[str, tuple[PeriodId, str]] = {}
        for month in open_months:
            deadline_passed = self.monotonic() - started > self.settings.run_soft_deadline_s
            outcome = self._month(month, now, options, deadline_passed)
            outcomes.append(outcome)
            if outcome.headline:
                label = self.config.properties.period_label(month.period)
                line = summary_line(month.prop.name, label, outcome.headline)
                previous = latest_line.get(month.prop.id)
                if previous is None or month.period >= previous[0]:
                    latest_line[month.prop.id] = (month.period, line)

        if not options.dry_run and not options.property_ids and not options.period:
            ordered = [
                latest_line[p.id][1]
                for p in self.config.properties.properties
                if p.id in latest_line
            ]
            self.store.write_summary(render_summary(ordered, now))
        return outcomes

    # -- one open month -------------------------------------------------------------------
    def _month(
        self, month: _Month, now: datetime, options: Options, deadline_passed: bool
    ) -> Outcome:
        prop, period = month.prop, month.period
        states = self._look(month)
        if not options.dry_run and any(s.choice.renames for s in states):
            for s in states:
                for file, name in s.choice.renames:
                    self.store.rename(prop, period, s.component.folder, file, name)
            states = self._look(month)  # the names the status shows are the ones in Drive
        month.states = states
        month.state = self.store.read_state(prop, period) or MonthState()

        verdict = decide(
            states,
            month.state,
            now=now,
            settle_minutes=self.settings.settle_minutes,
            max_failed_attempts=self.settings.max_failed_attempts,
            force=options.force,
        )
        if verdict.kind is Kind.NONE and self.store.read_status(prop, period) is not None:
            # Everything uploaded was deleted again. A stale status must not outlive the files.
            missing = [c.label for c in month.components if c.requirement == "required"]
            verdict = Verdict(
                Kind.WAITING,
                "Waiting for " + ", ".join(missing),
                "Nothing is in this month's folders any more.",
            )
        outcome = Outcome(prop.id, period, verdict.kind, verdict.headline)

        if verdict.build:
            if options.dry_run:
                outcome.note = "would build"
                return outcome
            if deadline_passed:
                # Leave the status as it is; the next run starts this build (SPEC §18.9 step 5).
                outcome.note = "deferred to the next run"
                outcome.headline = None
                return outcome
            verdict, outcome = self._build(month, verdict, now)

        if verdict.headline is not None and not options.dry_run:
            self._write_status(month, verdict)
        return outcome

    def _look(self, month: _Month) -> tuple[ComponentState, ...]:
        return tuple(
            ComponentState(c, choose(self.store.list_component(month.prop, month.period, c.folder)))
            for c in month.components
        )

    def _write_status(self, month: _Month, verdict: Verdict) -> None:
        assert verdict.headline is not None
        body = render_status(
            property_name=month.prop.name,
            period_label=self.config.properties.period_label(month.period),
            verdict=verdict,
            components=month.states,
            state=month.state,
            closes=closes_on(month.period, self.settings.lookback_days),
            settle_minutes=self.settings.settle_minutes,
        )
        if self.store.write_status(
            month.prop, month.period, status_filename(verdict.headline), body
        ):
            log.info(
                "intake.status",
                property=month.prop.id,
                period=month.period,
                kind=verdict.kind.value,
            )

    # -- a closed month ---------------------------------------------------------------------
    def _close(
        self, prop: Property, period: PeriodId, components: tuple[Component, ...], options: Options
    ) -> Outcome | None:
        """Write the final status once. A month nobody ever used stays silent."""
        current = self.store.read_status(prop, period)
        if current is None or headline_of(current[0]).startswith("Closed "):
            return None
        month = _Month(prop, period, components)
        month.states = self._look(month)
        month.state = self.store.read_state(prop, period) or MonthState()
        verdict = closed(closes_on(period, self.settings.lookback_days), month.state)
        if not options.dry_run:
            self._write_status(month, verdict)
        return Outcome(prop.id, period, verdict.kind, verdict.headline)

    # -- building -----------------------------------------------------------------------------
    def _build(self, month: _Month, ready: Verdict, now: datetime) -> tuple[Verdict, Outcome]:
        prop, period, state = month.prop, month.period, month.state
        fp = ready.fingerprint
        assert fp is not None
        work_root = self.settings.work_dir / "reconcile"
        inputs_dir = work_root / "downloads" / period / prop.id
        shutil.rmtree(inputs_dir, ignore_errors=True)

        current = current_files(month.states)
        documents: list[SourceDocument] = []
        for s in month.states:
            file = current.get(s.component.role)
            if file is None:
                continue
            local = self.store.download(file, inputs_dir / f"{s.component.role}.pdf")
            problem = _open_problem(local)
            if problem is not None:
                short, detail = problem
                verdict = held(
                    f"{s.component.label} {short}",
                    f'"{file.name}" in {s.component.label} {detail}. Replace it with a PDF '
                    "that opens without a password.",
                    state,
                    fp,
                )
                return verdict, Outcome(prop.id, period, Kind.HELD, verdict.headline)
            _, has_text = document_text_layer(local)
            documents.append(
                SourceDocument(
                    role=s.component.role,
                    schema_id=s.component.schema_id,
                    path=local,
                    sha256=sha256_file(local),
                    page_count=page_count(local),
                    has_text_layer=has_text,
                )
            )

        inner = self.classifier_for(prop.id)
        is_model = inner.name.startswith("anthropic")
        previous = self._previous_manifest(prop, period, state)
        schema_sha = {
            sid: self.config.sha256.get(f"schemas/{sid}.yaml", "") for sid in self.config.schemas
        }
        classifier = ReusingClassifier(
            inner,
            previous,
            model=self.settings.model if is_model else None,
            schema_sha256=schema_sha,
        )
        pages_to_classify = sum(
            d.page_count
            for d in documents
            if reusable_input(
                previous,
                role=d.role,
                source_sha256=d.sha256,
                schema_sha256=schema_sha.get(d.schema_id),
                classifier=classifier.identity(),
            )
            is None
        )
        estimate = pages_to_classify * self.settings.cost_per_page_usd if is_model else 0.0
        if estimate > self.settings.max_build_usd:
            ceiling = self.settings.max_build_usd
            verdict = held(
                f"would cost about ${estimate:.2f}, over the ${ceiling:.2f} limit",
                f"Classifying {pages_to_classify} pages would cost about ${estimate:.2f}, more "
                f"than the ${ceiling:.2f} allowed for one build. Check that every folder holds "
                "the right document; an unexpectedly long file is the usual cause.",
                state,
                fp,
            )
            return verdict, Outcome(prop.id, period, Kind.HELD, verdict.headline)

        staged = _Staged(documents, self, prop)
        result = build_property(
            prop,
            period,
            config=self.config,
            settings=self.settings.model_copy(update={"work_dir": work_root}),
            repository=staged,
            classifier=classifier,
            arbiter=self.arbiter,
        )
        manifest = result.manifest
        usd = manifest.cost.usd_estimate

        if result.status is BuildStatus.FAILED:
            error = (manifest.error or "error").split(":", 1)[0]
            state.attempts.append(Attempt(fingerprint=fp, at=self.clock(), error=error))
            self.store.write_state(prop, period, state)
            verdict = after_build(
                BuildStatus.FAILED, None, state, fp, self.settings.max_failed_attempts
            )
            return verdict, Outcome(prop.id, period, verdict.kind, verdict.headline, usd=usd)

        # Re-read just before publishing: if an overlapping run published these exact files
        # meanwhile, this build is a duplicate and is discarded (SPEC §18.9 step 4).
        fresh = self.store.read_state(prop, period) or MonthState()
        fresh.attempts = state.attempts
        latest = fresh.latest
        seen = state.latest.version if state.latest else 0
        if latest is not None and latest.version > seen and latest.fingerprint == fp:
            month.state = fresh
            verdict = Verdict(
                Kind.REVIEW if latest.status is BuildStatus.NEEDS_REVIEW else Kind.CURRENT,
                built_headline(latest),
                f"v{latest.version} was built from exactly the files listed below.",
                fp,
            )
            return verdict, Outcome(
                prop.id, period, verdict.kind, verdict.headline, latest.version, usd, "duplicate"
            )

        version = _free_version(fresh, self.store.output_names(prop, period))
        review = result.status is BuildStatus.NEEDS_REVIEW
        stem = output_filename(prop.name, self.config.properties.period_label(period))[
            : -len(".pdf")
        ]
        pdf_name = f"{stem} - v{version}" + (" - NEEDS REVIEW" if review else "") + ".pdf"

        by_role = {s.component.role: s for s in month.states}
        for ref in manifest.inputs:
            file = current[ref.role]
            ref.upload_name, ref.file_id, ref.md5 = file.name, file.id, file.md5
            ref.uploaded_at = file.uploaded_at
            ref.reused_classification = ref.role in classifier.reused
        manifest.version = version
        manifest.input_fingerprint = fp
        manifest.omitted_optional = [
            s.component.label
            for s in month.states
            if s.component.requirement == "optional" and s.choice.current is None
        ]
        assert result.output_path is not None and manifest.output is not None
        manifest.output.file = pdf_name
        manifest_path = write_manifest(manifest, result.manifest_path)

        published = self.store.publish(prop, period, result.output_path, pdf_name)
        self.store.publish(prop, period, manifest_path, f"v{version}.json", manifests=True)
        if review:
            with tempfile.TemporaryDirectory() as tmp:
                note = Path(tmp) / f"REVIEW - v{version}.md"
                note.write_text(render_review(manifest))
                self.store.publish(prop, period, note, note.name)

        fresh.versions.append(
            VersionEntry(
                version=version,
                built_at=manifest.built_at,
                status=result.status,
                fingerprint=fp,
                output_file=published,
                inputs=[InputSig.of(role, f) for role, f in current.items()],
                review_codes=sorted({r.code for r in manifest.review_reasons}),
            )
        )
        self.store.write_state(prop, period, fresh)  # the commit point: this version exists
        month.state = fresh
        log.info(
            "intake.published",
            property=prop.id,
            period=period,
            version=version,
            status=result.status.value,
            reused=sorted(classifier.reused),
            roles=sorted(by_role),
        )
        verdict = after_build(result.status, version, fresh, fp, self.settings.max_failed_attempts)
        return verdict, Outcome(prop.id, period, verdict.kind, verdict.headline, version, usd)

    def _previous_manifest(
        self, prop: Property, period: PeriodId, state: MonthState
    ) -> BuildManifest | None:
        latest = state.latest
        if latest is None:
            return None
        try:
            data = self.store.read_manifest(prop, period, latest.version)
            return BuildManifest.model_validate(data) if data else None
        except Exception:  # an unreadable manifest only costs a re-classification
            log.warning("intake.previous_manifest_unreadable", property=prop.id, period=period)
            return None

    def previous_pm_pages(self, prop: Property, period: PeriodId) -> int | None:
        """PM source pages from the newest version of an earlier month (the drift check)."""
        for earlier in sorted(
            (m for m in self.store.list_months(prop) if m < period), reverse=True
        ):
            state = self.store.read_state(prop, earlier)
            latest = state.latest if state else None
            if latest is None:
                continue
            data = self.store.read_manifest(prop, earlier, latest.version)
            for source in (data or {}).get("inputs", []):
                if source.get("role") == "pm_source" and isinstance(source.get("pages"), int):
                    return int(source["pages"])
        return None


class _Staged:
    """The v1 pipeline's repository, over files the reconciler has already chosen and
    downloaded. Publishing is the reconciler's job (versions, names, the index), so the
    pipeline's own publish step only records that it was reached."""

    name = "staged"

    def __init__(self, documents: list[SourceDocument], owner: Reconciler, prop: Property) -> None:
        self._documents = documents
        self._owner = owner
        self._prop = prop

    def list_periods(self, prop: Property) -> list[PeriodId]:
        return []

    def fetch_inputs(self, prop: Property, period: PeriodId, dest: Path) -> list[SourceDocument]:
        return list(self._documents)

    def publish(self, prop: Property, period: PeriodId, files: list[Path], status: Any) -> None:
        return None

    def preflight_publish(self) -> None:
        return None

    def previous_pm_pages(self, prop: Property, period: PeriodId, work_dir: Path) -> int | None:
        return self._owner.previous_pm_pages(prop, period)


def _open_problem(path: Path) -> tuple[str, str] | None:
    """(headline words, sentence) when a file cannot be used as a PDF, else None (SPEC §18.6)."""
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            return "is password-protected", "is password-protected"
        if len(reader.pages) == 0:
            return "has no pages", "has no pages"
    except Exception:
        return "cannot be opened", "cannot be opened as a PDF"
    return None


def _free_version(state: MonthState, names: list[str]) -> int:
    """One more than any version the index or the folder already shows."""
    highest = state.next_version - 1
    for name in names:
        marker = name.rfind(" - v")
        if marker < 0:
            continue
        digits = ""
        for ch in name[marker + 4 :]:
            if not ch.isdigit():
                break
            digits += ch
        if digits:
            highest = max(highest, int(digits))
    return highest + 1
