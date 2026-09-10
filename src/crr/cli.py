"""Typer CLI (SPEC §11).

Exit codes for ``build``: 0 all BUILT, 2 any NEEDS_REVIEW, 1 any FAILED (SPEC §6.9).
"""

from __future__ import annotations

from typing import Annotated

import typer

from crr import __version__
from crr.log import configure_logging
from crr.settings import get_settings

app = typer.Typer(
    name="crr",
    help="Cornerstone Report Runner — assembles quarterly investor report PDFs.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main(
    log_level: Annotated[
        str, typer.Option("--log-level", help="Python log level for the JSON log on stderr.")
    ] = "INFO",
) -> None:
    """Configure logging before any command runs."""
    configure_logging(level=log_level)


@app.command()
def version() -> None:
    """Print the runner version."""
    typer.echo(f"crr {__version__}")


@app.command(name="validate-config")
def validate_config() -> None:
    """Validate schemas, outputs and properties. Exit 1 on error.

    Phase 0 stub: loads the YAML and reports what it found. Full validation lands in Phase 2
    (SPEC §4, §9.6).
    """
    import yaml

    settings = get_settings()
    from pathlib import Path

    config_dir = Path("config")
    problems: list[str] = []
    loaded: dict[str, int] = {}
    for label, pattern in (
        ("properties", "properties.yaml"),
        ("schemas", "schemas/*.yaml"),
        ("outputs", "outputs/*.yaml"),
    ):
        paths = sorted(config_dir.glob(pattern))
        if not paths:
            problems.append(f"no {label} found under {config_dir / pattern}")
        for path in paths:
            try:
                yaml.safe_load(path.read_text())
            except yaml.YAMLError as exc:
                problems.append(f"{path}: {exc}")
        loaded[label] = len(paths)

    for label, count in loaded.items():
        typer.echo(f"{label}: {count} file(s) loaded")
    typer.echo(f"bundle root: {settings.bundle_root}")

    if problems:
        for problem in problems:
            typer.echo(f"error: {problem}", err=True)
        raise typer.Exit(code=1)
    typer.echo("validate-config: OK (stub — full validation lands in Phase 2)")


@app.command(name="eval")
def eval_command(
    classifier: Annotated[str, typer.Option("--classifier")] = "golden",
    pm: Annotated[str | None, typer.Option("--pm")] = None,
    gate: Annotated[bool, typer.Option("--gate")] = False,
) -> None:
    """Score a classifier against the golden labels.

    Phase 0 stub: exits 0. The real harness lands in Phase 5 (SPEC §8).
    """
    typer.echo("eval not implemented")


if __name__ == "__main__":  # pragma: no cover
    app()
