"""Rich formatting utilities for terminal output."""

from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console()


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}", style="red")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}", style="yellow")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_panel(title: str, content: str, style: str = "blue") -> None:
    """Print content in a panel.

    Args:
        title: Panel title
        content: Panel content
        style: Panel border style
    """
    console.print(Panel(content, title=title, border_style=style))


def create_progress() -> Progress:
    """Create a progress bar with common columns.

    Returns:
        Configured Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def create_table(title: Optional[str] = None, **kwargs: Any) -> Table:
    """Create a Rich table with common styling.

    Args:
        title: Optional table title
        **kwargs: Additional Table arguments

    Returns:
        Configured Table instance
    """
    return Table(title=title, show_header=True, header_style="bold cyan", **kwargs)
