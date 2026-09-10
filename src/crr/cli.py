"""Typer CLI (SPEC §11). Human summary to stdout, structured logs to stderr."""

from __future__ import annotations

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
