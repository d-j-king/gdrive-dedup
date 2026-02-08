"""Delete command for removing duplicates."""

from typing import Optional

import typer
from humanize import naturalsize

from ..actions.strategies import get_strategy
from ..actions.trash import TrashManager
from ..auth.oauth import OAuthManager
from ..auth.service import DriveServiceFactory
from ..common.exceptions import ActionError, AuthenticationError
from ..common.rate_limiter import TokenBucketRateLimiter
from ..config.settings import get_settings
from ..detector.pipeline import DetectionPipeline
from ..scanner.file_index import FileIndex
from .formatters import (
    create_progress,
    print_error,
    print_info,
    print_success,
    print_warning,
)

delete_app = typer.Typer(help="Delete duplicate files")


@delete_app.command()
def delete(
    strategy: str = typer.Option(
        ..., "--strategy", "-s", help="Keep strategy: newest, oldest, shortest, longest, path"
    ),
    keep_path: Optional[str] = typer.Option(
        None, "--keep-path", "-p", help="Glob pattern for paths to keep (for path strategy)"
    ),
    min_size: int = typer.Option(
        0, "--min-size", help="Minimum file size in bytes"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Delete duplicate files using a keep strategy."""
    settings = get_settings()

    try:
        # Validate strategy
        try:
            deletion_strategy = get_strategy(strategy)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(1)

        # Check authentication
        oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)
        if not oauth_manager.is_authenticated():
            raise AuthenticationError(
                "Not authenticated. Run 'gdrive-dedup auth login' first."
            )

        # Load duplicate groups
        with FileIndex(settings.db_path) as file_index:
            if file_index.count_files() == 0:
                print_error("No scan data found. Run 'gdrive-dedup scan' first.")
                raise typer.Exit(1)

            pipeline = DetectionPipeline(file_index)
            duplicate_groups = pipeline.detect_duplicates(min_size=min_size)

            if not duplicate_groups:
                print_success("No duplicates found!")
                return

            # Collect files to trash
            files_to_trash = []
            for group in duplicate_groups:
                trash_list = deletion_strategy.select_files_to_trash(group, keep_path)
                files_to_trash.extend(trash_list)

            if not files_to_trash:
                print_info("No files to delete with the selected strategy.")
                return

            # Calculate savings
            total_space_saved = sum(f.size for f in files_to_trash)

            print_info(f"Strategy: {strategy}")
            if keep_path:
                print_info(f"Keep path pattern: {keep_path}")
            print_info(f"Files to trash: {len(files_to_trash)}")
            print_info(f"Space to recover: {naturalsize(total_space_saved)}")

            if dry_run:
                print_warning("\n[DRY RUN] No files will be trashed\n")
            else:
                print_warning(
                    "\nWARNING: Files will be moved to trash (not permanently deleted)"
                )

            # Confirm
            if not yes and not dry_run:
                confirm = typer.confirm(
                    f"\nTrash {len(files_to_trash)} files?",
                    default=False,
                )
                if not confirm:
                    print_info("Cancelled.")
                    return

            # Trash files
            service_factory = DriveServiceFactory(oauth_manager)
            rate_limiter = TokenBucketRateLimiter(settings.rate_limit)
            trash_manager = TrashManager(service_factory, rate_limiter)

            print_info("\nTrash operations in progress...")
            progress = create_progress()

            file_ids = [f.file_id for f in files_to_trash]
            results = {}

            with progress:
                task = progress.add_task(
                    "[cyan]Trashing files...",
                    total=len(file_ids),
                )

                for file_id in file_ids:
                    try:
                        success = trash_manager.trash_file(file_id, dry_run)
                        results[file_id] = success
                    except ActionError as e:
                        print_error(f"Failed to trash {file_id}: {e}")
                        results[file_id] = False

                    progress.update(task, advance=1)

            # Summary
            successful = sum(1 for success in results.values() if success)
            failed = len(results) - successful

            if dry_run:
                print_success(f"\n[DRY RUN] Would trash {successful} files")
            else:
                print_success(f"\nTrashed {successful} files")
                if failed > 0:
                    print_warning(f"Failed to trash {failed} files")

                print_info(f"Space recovered: {naturalsize(total_space_saved)}")

    except AuthenticationError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Delete operation failed: {e}")
        raise typer.Exit(1)
