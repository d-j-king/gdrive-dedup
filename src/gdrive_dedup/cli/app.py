"""Main CLI application."""

import typer

from ..common.logging import setup_logging
from ..config.settings import get_settings
from .auth_cmd import auth_app
from .config_cmd import config_app
from .delete_cmd import delete, delete_app
from .report_cmd import report, report_app
from .review_cmd import review, review_app
from .scan_cmd import scan, scan_app

app = typer.Typer(
    name="gdrive-dedup",
    help="Find and remove duplicate files in Google Drive",
    add_completion=False,
)

# Register subcommands
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")

# Add main commands
app.command(name="scan")(scan)
app.command(name="review")(review)
app.command(name="delete")(delete)
app.command(name="report")(report)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Google Drive duplicate file finder and remover."""
    settings = get_settings()
    log_level = "DEBUG" if verbose else settings.log_level
    setup_logging(level=log_level, log_file=settings.log_file)
