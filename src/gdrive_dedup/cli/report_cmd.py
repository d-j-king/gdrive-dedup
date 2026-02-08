"""Report command for exporting duplicate data."""

from pathlib import Path

import typer
from humanize import naturalsize

from ..config.settings import get_settings
from ..detector.pipeline import DetectionPipeline
from ..reporting.exporter import ReportExporter
from ..scanner.file_index import FileIndex
from .formatters import print_error, print_info, print_success

report_app = typer.Typer(help="Export duplicate reports")


@report_app.command()
def report(
    format: str = typer.Option(
        "csv", "--format", "-f", help="Output format: csv or json"
    ),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Output file path"
    ),
    min_size: int = typer.Option(
        0, "--min-size", help="Minimum file size in bytes"
    ),
) -> None:
    """Export duplicate file report to CSV or JSON."""
    settings = get_settings()

    try:
        # Validate format
        if format.lower() not in ["csv", "json"]:
            print_error(f"Invalid format: {format}. Must be 'csv' or 'json'")
            raise typer.Exit(1)

        # Load duplicate groups
        with FileIndex(settings.db_path) as file_index:
            if file_index.count_files() == 0:
                print_error("No scan data found. Run 'gdrive-dedup scan' first.")
                raise typer.Exit(1)

            pipeline = DetectionPipeline(file_index)
            duplicate_groups = pipeline.detect_duplicates(min_size=min_size)

            if not duplicate_groups:
                print_info("No duplicates found!")
                return

            # Export report
            exporter = ReportExporter()

            if format.lower() == "csv":
                exporter.export_csv(duplicate_groups, output)
            else:
                exporter.export_json(duplicate_groups, output)

            # Summary
            total_files = sum(g.count for g in duplicate_groups)
            total_wasted = sum(g.wasted_size for g in duplicate_groups)

            print_success(f"Exported report to: {output}")
            print_info(f"Groups: {len(duplicate_groups)}")
            print_info(f"Files: {total_files}")
            print_info(f"Wasted space: {naturalsize(total_wasted)}")

    except Exception as e:
        print_error(f"Report export failed: {e}")
        raise typer.Exit(1)
