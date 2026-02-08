"""Scan command."""

from typing import Optional

import typer
from humanize import naturalsize

from ..auth.oauth import OAuthManager
from ..auth.service import DriveServiceFactory
from ..common.exceptions import AuthenticationError, ScanError
from ..common.rate_limiter import TokenBucketRateLimiter
from ..config.settings import get_settings
from ..detector.pipeline import DetectionPipeline
from ..scanner.drive_scanner import DriveScanner
from ..scanner.file_index import FileIndex
from ..scanner.resume import ScanCheckpoint
from .formatters import (
    create_progress,
    create_table,
    print_error,
    print_info,
    print_panel,
    print_success,
)

scan_app = typer.Typer(help="Scan Google Drive for duplicate files")


@scan_app.command()
def scan(
    folder: Optional[str] = typer.Option(
        None, "--folder", "-f", help="Folder ID to scan (default: entire drive)"
    ),
    owned_only: bool = typer.Option(
        True, "--owned-only/--all-files", help="Only scan files you own"
    ),
    resume: bool = typer.Option(
        False, "--resume", "-r", help="Resume interrupted scan"
    ),
    byte_compare: bool = typer.Option(
        False, "--byte-compare", help="Enable byte-by-byte comparison"
    ),
    min_size: int = typer.Option(
        0, "--min-size", help="Minimum file size in bytes"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be scanned without scanning"
    ),
) -> None:
    """Scan Google Drive for duplicate files."""
    settings = get_settings()

    try:
        # Initialize components
        oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)

        if not oauth_manager.is_authenticated():
            raise AuthenticationError(
                "Not authenticated. Run 'gdrive-dedup auth login' first."
            )

        service_factory = DriveServiceFactory(oauth_manager)
        rate_limiter = TokenBucketRateLimiter(settings.rate_limit)

        if dry_run:
            print_info("Dry run mode - no files will be scanned")
            print_info(f"Folder: {folder or 'Entire drive'}")
            print_info(f"Owned only: {owned_only}")
            print_info(f"Min size: {naturalsize(min_size) if min_size > 0 else 'None'}")
            return

        # Create file index
        with FileIndex(settings.db_path) as file_index:
            scanner = DriveScanner(service_factory, rate_limiter, settings.page_size)
            checkpoint = ScanCheckpoint(settings.checkpoint_path)

            if resume:
                if checkpoint.load():
                    print_info(f"Resuming from checkpoint: {checkpoint.files_scanned} files")
                else:
                    print_info("No checkpoint found, starting fresh scan")
            else:
                # Clear previous data
                file_index.clear()
                checkpoint.clear()

            # Scan files
            print_info("Scanning Google Drive...")
            progress = create_progress()

            with progress:
                task = progress.add_task(
                    "[cyan]Scanning files...",
                    total=None,
                )

                files_scanned = 0
                batch = []

                for file_record in scanner.scan_files(
                    folder_id=folder,
                    owned_only=owned_only,
                    min_size=min_size,
                ):
                    batch.append(file_record)
                    files_scanned += 1

                    # Batch insert for performance
                    if len(batch) >= settings.batch_size:
                        file_index.add_files(batch)
                        batch = []
                        checkpoint.save(None, files_scanned)

                    progress.update(task, completed=files_scanned)

                # Insert remaining files
                if batch:
                    file_index.add_files(batch)

                progress.update(task, description="[green]Scan complete!")

            checkpoint.clear()
            print_success(f"Scanned {files_scanned} files")

            # Run duplicate detection
            print_info("Detecting duplicates...")
            pipeline = DetectionPipeline(file_index)
            duplicate_groups = pipeline.detect_duplicates(
                min_size=min_size,
                byte_compare=byte_compare,
            )

            if not duplicate_groups:
                print_success("No duplicates found!")
                return

            # Display summary
            total_duplicates = sum(g.count for g in duplicate_groups)
            total_wasted = sum(g.wasted_size for g in duplicate_groups)

            summary_text = f"""
Files scanned: {files_scanned:,}
Duplicate groups: {len(duplicate_groups):,}
Duplicate files: {total_duplicates:,}
Wasted space: {naturalsize(total_wasted)}
"""

            print_panel("Scan Summary", summary_text.strip(), style="green")

            # Show top duplicate groups
            print_info("\nTop 10 duplicate groups by wasted space:")

            table = create_table()
            table.add_column("Group", style="cyan", width=8)
            table.add_column("Files", style="yellow", width=8)
            table.add_column("Size", style="green", width=12)
            table.add_column("Wasted", style="red", width=12)
            table.add_column("Name", style="white")

            for group in duplicate_groups[:10]:
                table.add_row(
                    str(group.group_id),
                    str(group.count),
                    naturalsize(group.size),
                    naturalsize(group.wasted_size),
                    group.files[0].name[:50],
                )

            from .formatters import console
            console.print(table)

            print_info("\nRun 'gdrive-dedup review' to interactively review duplicates")
            print_info("Run 'gdrive-dedup delete --strategy <strategy>' to remove duplicates")

    except AuthenticationError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except ScanError as e:
        print_error(f"Scan failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(1)
