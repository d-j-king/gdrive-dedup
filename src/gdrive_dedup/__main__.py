"""Entry point for the CLI application."""

from .cli.app import app


def main() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    main()
