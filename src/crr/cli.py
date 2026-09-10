"""Typer CLI (SPEC §11). Human summary to stdout, structured logs to stderr."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from crr import __version__
from crr.log import configure
from crr.models import SourceDocument
from crr.settings import Settings

app = typer.Typer(
    name="crr",
    help="Cornerstone Report Runner — assemble quarterly investor report packages.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main(
    log_level: str = typer.Option("INFO", "--log-level", help="DEBUG|INFO|WARNING|ERROR"),
) -> None:
    """Root callback: sets up logging for every subcommand."""
    configure(log_level.upper())


@app.command()
def version() -> None:
    """Print the runner version."""
    typer.echo(f"crr {__version__}")


@app.command()
def inspect(
    pdf: Annotated[
        Path | None,
        typer.Argument(help="PDF to inspect", exists=True, dir_okay=False),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table")] = False,
    repo: Annotated[
        str | None, typer.Option("--repo", help="local|gdrive: list a period instead of a PDF")
    ] = None,
    period: Annotated[str | None, typer.Option("--period", help="Period id to list")] = None,
) -> None:
    """Inspect one PDF, or — with `--repo` and `--period` — list what a period holds."""
    if repo is not None:
        _inspect_period(repo, period)
        return
    if pdf is None:
        typer.echo("give a PDF, or --repo <local|gdrive> --period <id>", err=True)
        raise typer.Exit(code=1)

    from crr.preprocess.inspect import inspect_pdf

    facts = inspect_pdf(pdf)
    if as_json:
        typer.echo(facts.model_dump_json(indent=2))
        return
    typer.echo(f"{pdf.name}")
    typer.echo(f"  sha256        {facts.sha256}")
    typer.echo(f"  pages         {facts.page_count}")
    typer.echo(f"  text layer    {facts.has_text_layer}")
    typer.echo(f"  {'page':>4}  {'size (pt)':>13}  {'rot':>3}  {'chars':>6}  footer")
    for page in facts.pages:
        size = f"{page.width_pt:.0f}x{page.height_pt:.0f}"
        footer = (page.footer_line or "")[:64]
        typer.echo(
            f"  {page.page:>4}  {size:>13}  {page.rotate:>3}  {page.text_chars:>6}  {footer}"
        )


@app.command()
def classify(
    pdf: Annotated[Path, typer.Argument(help="PDF to classify", exists=True, dir_okay=False)],
    schema_id: Annotated[str, typer.Option("--schema", help="Source schema id")],
    classifier: Annotated[str, typer.Option("--classifier", help="anthropic|golden")] = "anthropic",
    doc_role: Annotated[str, typer.Option("--role", help="Document role to label")] = "pm_source",
    property_id: Annotated[
        str | None,
        typer.Option("--property", help="Property id (required for --classifier golden)"),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Write the labels as JSON here")] = None,
) -> None:
    """Classify every page of one PDF and print the labels."""
    import json as _json

    from crr.classify.footer_check import apply_footer_check
    from crr.classify.protocol import PageInput
    from crr.config import load_config
    from crr.preprocess.render import render_pages
    from crr.preprocess.text import document_text_layer, sha256_file
    from crr.settings import Settings

    settings = Settings()
    bundle = load_config(settings.config_dir)
    if schema_id not in bundle.schemas:
        typer.echo(
            f"unknown schema {schema_id!r}; have {', '.join(sorted(bundle.schemas))}", err=True
        )
        raise typer.Exit(code=1)
    schema = bundle.schemas[schema_id]

    sha = sha256_file(pdf)
    texts, has_text = document_text_layer(pdf, max_chars=settings.page_text_chars)
    doc = SourceDocument(
        role=doc_role,
        schema_id=schema_id,
        path=pdf,
        sha256=sha,
        page_count=len(texts),
        has_text_layer=has_text,
    )
    pages_dir = settings.work_dir / "classify" / sha[:16]
    images = render_pages(
        pdf, sha, pages_dir, dpi=settings.render_dpi, max_edge=settings.render_max_edge_px
    )
    page_inputs = [
        PageInput(page=n, image_path=images[n], text=texts[n - 1] or None) for n in sorted(images)
    ]

    engine = _make_classifier(classifier, settings, property_id)
    result = engine.classify(doc, schema, page_inputs)
    labelled = apply_footer_check(result.pages, schema, {n: texts[n - 1] for n in sorted(images)})

    typer.echo(f"{pdf.name}  schema={schema_id}  classifier={engine.name}")
    typer.echo(f"  {'page':>4}  {'section':<30}{'cont':>5}{'conf':>7}  {'footer':<28} record")
    for label in labelled:
        agrees = "" if label.footer_agrees is None else ("=" if label.footer_agrees else " !=")
        typer.echo(
            f"  {label.page:>4}  {label.section_id:<30}{label.is_continuation!s:>5}"
            f"{label.confidence:>7.2f}  {(label.footer_label or '-')[:26]:<26}{agrees:<2} "
            f"{label.record_qualifier or ''}"
        )
    if result.usage.api_calls:
        typer.echo(
            f"  tokens: input={result.usage.input_tokens} "
            f"cache_read={result.usage.cache_read_tokens} "
            f"cache_write={result.usage.cache_write_tokens} "
            f"output={result.usage.output_tokens} calls={result.usage.api_calls}"
        )
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _json.dumps([label.model_dump(mode="json") for label in labelled], indent=2) + "\n"
        )
        typer.echo(f"  wrote {out}")


def _make_classifier(kind: str, settings: Settings, property_id: str | None):  # type: ignore[no-untyped-def]
    """Build a classifier by name. Kept out of the command body so `build` can reuse it."""
    from crr.classify.golden_classifier import GoldenClassifier
    from crr.golden import load_all_golden

    if kind == "golden":
        if property_id is None:
            typer.echo("--classifier golden needs --property <id>", err=True)
            raise typer.Exit(code=1)
        golden = load_all_golden(settings.golden_dir)
        if property_id not in golden:
            typer.echo(f"no golden labels for {property_id!r}", err=True)
            raise typer.Exit(code=1)
        return GoldenClassifier(golden[property_id])
    if kind == "anthropic":
        from crr.classify.anthropic_classifier import AnthropicClassifier

        try:
            return AnthropicClassifier(settings)
        except RuntimeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None
    typer.echo(f"unknown classifier {kind!r}; use anthropic or golden", err=True)
    raise typer.Exit(code=1)


def _make_orientation_arbiter(settings: Settings):  # type: ignore[no-untyped-def]
    """The tie-breaker for a page the two orientation checks disagree on (SPEC §7.6).

    Needs a key of its own right: a golden build has no key and simply goes without, which
    turns an unsettled disagreement into `orientation_uncertain` rather than a wrong rotation.
    """
    if not settings.orientation_check or not settings.anthropic_api_key:
        return None
    from crr.classify.orientation_arbiter import AnthropicOrientationArbiter

    return AnthropicOrientationArbiter(settings)


def _inspect_period(repo: str, period: str | None) -> None:
    """What each property has in `inputs/` for a period, and whether it is ready to build."""
    from crr.config import ConfigError, load_config
    from crr.settings import Settings

    if period is None:
        typer.echo("--repo needs --period <id>", err=True)
        raise typer.Exit(code=1)

    settings = Settings()
    try:
        bundle = load_config(settings.config_dir)
    except ConfigError as exc:
        typer.echo(f"config invalid:\n{exc}", err=True)
        raise typer.Exit(code=1) from None

    repository = _make_repository(repo, settings, bundle)
    filenames = bundle.properties.cornerstone_files
    typer.echo(f"period {period} via {repo}")
    ready = 0
    for entry in bundle.properties.properties:
        prop = entry.to_domain()
        if hasattr(repository, "present_inputs"):
            present = {
                role: file is not None
                for role, file in repository.present_inputs(prop, period).items()
            }
        else:
            inputs_dir = repository.period_dir(prop, period) / "inputs"
            names = bundle.properties.input_filenames(prop.id)
            present = {role: (inputs_dir / name).is_file() for role, name in names.items()}
        has_pm = present.get("pm_source", False)
        ready += int(has_pm)
        missing = [role for role, there in present.items() if not there]
        optional_only = all(role in filenames for role in missing)
        state = "ready" if has_pm else "NOT READY"
        note = ""
        if missing:
            note = "  missing: " + ", ".join(sorted(missing))
            if has_pm and optional_only:
                note += " (optional)"
        typer.echo(f"  {entry.id:<20} {state:<10}{note}")
    typer.echo(f"{ready}/{len(bundle.properties.properties)} propert(ies) ready to build")


@app.command("validate-config")
def validate_config() -> None:
    """Validate the schemas, output definitions and property registry (SPEC §4, §9.6)."""
    from crr.config import ConfigError, load_config
    from crr.settings import Settings

    settings = Settings()
    try:
        bundle = load_config(settings.config_dir)
    except ConfigError as exc:
        typer.echo(f"config invalid ({len(exc.problems)} problem(s)):", err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"config ok: {len(bundle.schemas)} schema(s), {len(bundle.outputs)} output "
        f"definition(s), {len(bundle.properties.properties)} propert(ies)"
    )
    for schema in bundle.schemas.values():
        typer.echo(
            f"  schema {schema.schema_id:<22} v{schema.version}  {len(schema.sections)} sections"
        )
    for output in bundle.outputs.values():
        typer.echo(
            f"  output {output.output_id:<28} v{output.version}  "
            f"{len(output.leaves)} flow item(s), {len(output.drop)} dropped"
        )


@app.command()
def build(
    period: Annotated[
        str | None,
        typer.Option("--period", help="Period id, e.g. 2026-06 (default: the month just ended)"),
    ] = None,
    property_ids: Annotated[
        list[str] | None, typer.Option("--property", help="Property id; repeatable")
    ] = None,
    classifier: Annotated[str, typer.Option("--classifier", help="anthropic|golden")] = "anthropic",
    repo: Annotated[str, typer.Option("--repo", help="local|gdrive")] = "local",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Plan but do not compose")] = False,
    work_dir: Annotated[Path | None, typer.Option("--work-dir")] = None,
) -> None:
    """Build investor packages for a period.

    Exit codes (SPEC §6.8): 0 all built, 2 any needs review, 1 any failed.
    """
    from crr.config import ConfigError, load_config
    from crr.models import BuildStatus
    from crr.pipeline import build_property
    from crr.settings import Settings

    settings = Settings()
    if work_dir is not None:
        settings = settings.model_copy(update={"work_dir": work_dir})
    try:
        bundle = load_config(settings.config_dir)
    except ConfigError as exc:
        typer.echo(f"config invalid:\n{exc}", err=True)
        raise typer.Exit(code=1) from None

    if period is None:
        period = bundle.properties.previous_period()
        typer.echo(f"no --period given; building {period} (the month just ended)")

    wanted = property_ids or [p.id for p in bundle.properties.properties]
    unknown = [p for p in wanted if p not in {e.id for e in bundle.properties.properties}]
    if unknown:
        typer.echo(f"unknown propert(ies): {', '.join(unknown)}", err=True)
        raise typer.Exit(code=1)

    repository = _make_repository(repo, settings, bundle)
    results = []
    for property_id in wanted:
        prop = bundle.properties.property(property_id).to_domain()
        engine = _make_classifier(classifier, settings, property_id)
        result = build_property(
            prop,
            period,
            config=bundle,
            settings=settings,
            repository=repository,
            classifier=engine,
            arbiter=_make_orientation_arbiter(settings),
            dry_run=dry_run,
        )
        results.append(result)
        marker = {
            BuildStatus.BUILT: "ok",
            BuildStatus.NEEDS_REVIEW: "review",
            BuildStatus.FAILED: "FAILED",
        }[result.status]
        pages = len(result.manifest.plan)
        detail = ""
        if result.status is BuildStatus.NEEDS_REVIEW:
            detail = "  " + ", ".join(sorted({r.code for r in result.reasons}))
        elif result.status is BuildStatus.FAILED:
            detail = f"  {result.manifest.error}"
        typer.echo(f"{property_id:<20} {marker:<8} {pages:>3} pages{detail}")

    _print_cost(results)

    if any(r.status is BuildStatus.FAILED for r in results):
        raise typer.Exit(code=1)
    if any(r.status is BuildStatus.NEEDS_REVIEW for r in results):
        raise typer.Exit(code=2)


def _print_cost(results: list) -> None:  # type: ignore[type-arg]
    """Tokens and the USD estimate for the run (PLAN Phase 9). The estimate comes from the
    settings price table and is recorded in every manifest as `cost`."""
    calls = sum(r.manifest.cost.api_calls for r in results)
    if not calls:
        return
    tokens = {
        "input": sum(r.manifest.cost.tokens.input for r in results),
        "cache read": sum(r.manifest.cost.tokens.cache_read for r in results),
        "cache write": sum(r.manifest.cost.tokens.cache_write for r in results),
        "output": sum(r.manifest.cost.tokens.output for r in results),
    }
    usd = sum(r.manifest.cost.usd_estimate for r in results)
    typer.echo("")
    typer.echo(f"{calls} API call(s) over {len(results)} propert(ies)")
    typer.echo("  " + "  ".join(f"{name}={count:,}" for name, count in tokens.items()))
    typer.echo(f"  estimated ${usd:.2f} (${usd / max(len(results), 1):.2f} per property)")


def _make_repository(kind: str, settings: Settings, bundle):  # type: ignore[no-untyped-def]
    from crr.repository.local_fs import LocalFsRepository

    if kind == "local":

        def schema_for_role(prop, role):  # type: ignore[no-untyped-def]
            output = bundle.output_for_property(prop.id)
            for source in output.sources.values():
                if source.role == role:
                    return source.schema_id
            return bundle.properties.manager(prop.property_manager).schema_id

        return LocalFsRepository(
            settings.bundle_root,
            bundle.properties,
            schema_for_role,
            publish_root=settings.local_publish_root,
        )
    if kind == "gdrive":
        from crr.repository.drive_client import DriveError, GoogleDriveApi
        from crr.repository.google_drive import GoogleDriveRepository

        if not settings.google_service_account_b64:
            typer.echo("GOOGLE_SERVICE_ACCOUNT_B64 is not set", err=True)
            raise typer.Exit(code=1)
        if not settings.gdrive_root_folder_id:
            typer.echo("CRR_GDRIVE_ROOT_FOLDER_ID is not set", err=True)
            raise typer.Exit(code=1)

        def gdrive_schema_for_role(prop, role):  # type: ignore[no-untyped-def]
            output = bundle.output_for_property(prop.id)
            for source in output.sources.values():
                if source.role == role:
                    return source.schema_id
            return bundle.properties.manager(prop.property_manager).schema_id

        try:
            api = GoogleDriveApi.from_b64(settings.google_service_account_b64)
        except DriveError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None
        return GoogleDriveRepository(
            api, settings.gdrive_root_folder_id, bundle.properties, gdrive_schema_for_role
        )
    typer.echo(f"unknown repo {kind!r}; use local or gdrive", err=True)
    raise typer.Exit(code=1)


@app.command("eval")
def eval_cmd(
    classifier: Annotated[str, typer.Option("--classifier", help="golden|anthropic")] = "golden",
    pm: Annotated[str | None, typer.Option("--pm", help="Score one property manager only")] = None,
    property_ids: Annotated[
        list[str] | None, typer.Option("--property", help="Property id; repeatable")
    ] = None,
    gate: Annotated[
        bool, typer.Option("--gate", help="Exit non-zero below the accuracy thresholds")
    ] = False,
    report: Annotated[
        Path | None, typer.Option("--report", help="Write the markdown report here")
    ] = None,
) -> None:
    """Score a classifier against the golden labels (SPEC §8)."""
    from crr.config import ConfigError, load_config
    from crr.evaluate import evaluate, gate_failures, render_report, report_filename
    from crr.golden import load_all_golden
    from crr.settings import Settings

    settings = Settings()
    try:
        bundle = load_config(settings.config_dir)
    except ConfigError as exc:
        typer.echo(f"config invalid:\n{exc}", err=True)
        raise typer.Exit(code=1) from None

    golden = load_all_golden(settings.golden_dir)
    result = evaluate(
        golden,
        bundle,
        settings,
        lambda property_id: _make_classifier(classifier, settings, property_id),
        property_ids=property_ids,
        pm_id=pm,
        arbiter=_make_orientation_arbiter(settings),
    )
    if not result.documents:
        typer.echo("no golden documents in scope", err=True)
        raise typer.Exit(code=1)

    failures = gate_failures(result, settings)
    text = render_report(result, settings, failures)

    destination = report or (Path("eval/reports") / report_filename(result))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    (destination.parent / "LATEST.md").write_text(text)

    overall = result.overall()
    for manager, scores in sorted(result.by_manager().items()):
        accuracy = scores.page.accuracy
        f1 = scores.boundary.f1
        typer.echo(
            f"{manager:<12} pages={scores.page.scored:>4} "
            f"accuracy={'—' if accuracy is None else f'{accuracy:.4f}'} "
            f"boundary_f1={'—' if f1 is None else f'{f1:.4f}'}"
        )
    typer.echo(
        f"{'overall':<12} pages={overall.page.scored:>4} "
        f"accuracy={'—' if overall.page.accuracy is None else f'{overall.page.accuracy:.4f}'} "
        f"boundary_f1={'—' if overall.boundary.f1 is None else f'{overall.boundary.f1:.4f}'}"
    )
    typer.echo(f"report: {destination}")

    if failures:
        for failure in failures:
            typer.echo(f"below threshold: {failure}", err=True)
        if gate:
            raise typer.Exit(code=1)


if __name__ == "__main__":  # pragma: no cover
    app()
