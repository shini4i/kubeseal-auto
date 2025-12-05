"""Rich console utilities for styled terminal output.

This module provides a consistent, visually appealing interface for all
CLI output using the Rich library.
"""

from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.theme import Theme

# Custom theme with consistent colors
_THEME = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "highlight": "cyan bold",
        "muted": "dim",
    }
)

# Shared console instance
console = Console(theme=_THEME)


def info(message: str) -> None:
    """Print an informational message.

    Args:
        message: The message to display.

    """
    console.print(f"[info]ℹ[/info] {message}")


def success(message: str) -> None:
    """Print a success message.

    Args:
        message: The message to display.

    """
    console.print(f"[success]✓[/success] {message}")


def warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: The message to display.

    """
    console.print(f"[warning]⚠[/warning] {message}")


def error(message: str) -> None:
    """Print an error message.

    Args:
        message: The message to display.

    """
    console.print(f"[error]✗[/error] {message}")


def action(message: str) -> None:
    """Print an action/progress message.

    Args:
        message: The message to display.

    """
    console.print(f"[info]→[/info] {message}")


def step(message: str) -> None:
    """Print a sub-step message.

    Args:
        message: The message to display.

    """
    console.print(f"[muted]•[/muted] {message}")


def highlight(text: str) -> str:
    """Return text wrapped in highlight markup.

    Args:
        text: The text to highlight.

    Returns:
        Text wrapped in Rich markup for highlighting.

    """
    return f"[highlight]{text}[/highlight]"


@contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    """Display a spinner while performing an operation.

    Args:
        message: The status message to display.

    Yields:
        None

    """
    with console.status(f"[info]{message}[/info]", spinner="dots"):
        yield


def create_download_progress() -> Progress:
    """Create a progress bar configured for file downloads.

    Returns:
        A configured Progress instance for download operations.

    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def create_task_progress() -> Progress:
    """Create a progress bar configured for task processing.

    Returns:
        A configured Progress instance for batch operations.

    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[muted]{task.completed}/{task.total}[/muted]"),
        console=console,
    )


def summary_panel(title: str, items: dict[str, str]) -> None:
    """Print a summary panel with key-value pairs.

    Args:
        title: Title for the panel.
        items: Dictionary of label -> value pairs to display.

    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column(style="cyan")

    for label, value in items.items():
        table.add_row(f"{label}:", value)

    console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="green"))


def newline() -> None:
    """Print an empty line."""
    console.print()
