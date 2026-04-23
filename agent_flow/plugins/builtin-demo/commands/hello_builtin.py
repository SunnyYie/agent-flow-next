from __future__ import annotations

import click


@click.command(name="hello-builtin")
def cli() -> None:
    click.echo("hello-from-builtin")
