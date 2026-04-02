import typer

app = typer.Typer(
    name="vidi",
    help="YouTube video analyzer powered by Google Gemini.",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
