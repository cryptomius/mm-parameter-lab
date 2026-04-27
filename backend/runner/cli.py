"""CLI entry point: `python -m runner.cli run <pattern>`."""

from __future__ import annotations

from pathlib import Path

import click

from mm_sim.logging_config import configure, get_logger
from mm_sim.types import ExperimentConfig
from runner import batch
from runner.manifest import expand, load_manifest, select_experiments

DEFAULT_MANIFEST = Path("backend/experiments.yaml")


@click.group()
@click.option("--log-level", default="INFO", help="logging level")
def cli(log_level: str) -> None:
    configure(level=log_level)


@cli.command("run")
@click.argument("pattern")
@click.option("--manifest", type=click.Path(path_type=Path, exists=True), default=DEFAULT_MANIFEST)
@click.option("--workers", type=int, default=1, help="parallel processes")
@click.option("--dry-run", is_flag=True, help="print resolved configs and exit")
def run_cmd(pattern: str, manifest: Path, workers: int, dry_run: bool) -> None:
    log = get_logger("cli")
    raw = load_manifest(manifest)
    matched = select_experiments(raw, pattern)
    if not matched:
        raise click.ClickException(f"no experiments match pattern {pattern!r}")
    cfgs: list[ExperimentConfig] = []
    for entry in matched:
        cfgs.extend(expand(entry))
    log.info("manifest.expanded", pattern=pattern, n_runs=len(cfgs))
    if dry_run:
        for c in cfgs:
            click.echo(f"{c.id}\t{c.sweep_label}\tseed={c.seed}\tgamma={c.quoter.gamma}\t-> {batch.expected_output(c)}")
        return
    batch.run_many(cfgs, workers=workers)


@cli.command("list")
@click.option("--manifest", type=click.Path(path_type=Path, exists=True), default=DEFAULT_MANIFEST)
def list_cmd(manifest: Path) -> None:
    raw = load_manifest(manifest)
    for e in raw:
        click.echo(f"{e.get('id'):40s}  finding={e.get('finding')}  {e.get('description', '')}")


if __name__ == "__main__":
    cli()
