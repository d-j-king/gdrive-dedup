"""Configuration management commands."""

import typer

from ..config.settings import get_settings, reset_settings
from .formatters import create_table, print_error, print_info, print_success

config_app = typer.Typer(help="Manage configuration settings")


@config_app.command()
def show() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = create_table(title="Configuration")
    table.add_column("Setting", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Data directory", str(settings.data_dir))
    table.add_row("Rate limit (req/s)", str(settings.rate_limit))
    table.add_row("Page size", str(settings.page_size))
    table.add_row("Batch size", str(settings.batch_size))
    table.add_row("Min file size", str(settings.min_file_size))
    table.add_row("Byte compare", str(settings.byte_compare))
    table.add_row("Log level", settings.log_level)
    table.add_row("Log file", str(settings.log_file) if settings.log_file else "None")

    from .formatters import console
    console.print(table)


@config_app.command()
def set(
    key: str = typer.Argument(..., help="Setting key"),
    value: str = typer.Argument(..., help="Setting value"),
) -> None:
    """Set a configuration value."""
    settings = get_settings()

    valid_keys = {
        "rate_limit": float,
        "page_size": int,
        "batch_size": int,
        "min_file_size": int,
        "byte_compare": bool,
        "log_level": str,
    }

    if key not in valid_keys:
        print_error(
            f"Invalid key: {key}. Valid keys: {', '.join(valid_keys.keys())}"
        )
        raise typer.Exit(1)

    try:
        # Convert value to appropriate type
        converter = valid_keys[key]
        if converter == bool:
            converted_value = value.lower() in ["true", "1", "yes"]
        else:
            converted_value = converter(value)

        # Set attribute
        setattr(settings, key, converted_value)
        print_success(f"Set {key} = {converted_value}")
        print_info("Note: Settings are not persisted across sessions")

    except ValueError as e:
        print_error(f"Invalid value for {key}: {e}")
        raise typer.Exit(1)


@config_app.command()
def reset() -> None:
    """Reset configuration to defaults."""
    if typer.confirm("Reset all settings to defaults?", default=False):
        reset_settings()
        print_success("Configuration reset to defaults")
    else:
        print_info("Cancelled")
