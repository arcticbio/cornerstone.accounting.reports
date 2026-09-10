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
    pdf: Annotated[Path, typer.Argument(help="PDF to inspect", exists=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table")] = False,
) -> None:
    """Page sizes, the text-layer probe and footer lines for one PDF."""
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


@app.command("eval")
def eval_cmd(
    classifier: str = typer.Option("golden", "--classifier", help="golden|anthropic"),
    gate: bool = typer.Option(False, "--gate", help="Exit non-zero below the accuracy thresholds"),
) -> None:
    """Score a classifier against the golden labels (Phase 0 stub)."""
    typer.echo(f"eval not implemented (classifier={classifier}, gate={gate})")


if __name__ == "__main__":  # pragma: no cover
    app()
