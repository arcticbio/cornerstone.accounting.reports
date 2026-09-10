"""Typer CLI (SPEC §11). Human summary to stdout, structured logs to stderr."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from crr import __version__
from crr.log import configure

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


@app.command("validate-config")
def validate_config() -> None:
    """Validate schemas, outputs and the property registry (Phase 0 stub: loads YAML only)."""
    import yaml

    from crr.settings import Settings

    settings = Settings()
    loaded = 0
    for path in sorted(settings.config_dir.rglob("*.yaml")):
        with path.open("rb") as fh:
            yaml.safe_load(fh)
        loaded += 1
    typer.echo(f"validate-config: loaded {loaded} YAML file(s) (stub — full validation in Phase 2)")


@app.command("eval")
def eval_cmd(
    classifier: str = typer.Option("golden", "--classifier", help="golden|anthropic"),
    gate: bool = typer.Option(False, "--gate", help="Exit non-zero below the accuracy thresholds"),
) -> None:
    """Score a classifier against the golden labels (Phase 0 stub)."""
    typer.echo(f"eval not implemented (classifier={classifier}, gate={gate})")


if __name__ == "__main__":  # pragma: no cover
    app()
