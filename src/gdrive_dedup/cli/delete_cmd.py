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
        "merge-names", "--strategy", "-s",
        help="Keep strategy: newest, oldest, shortest, longest, deepest, path, merge-names [default: merge-names]"
    ),
    keep_path: Optional[str] = typer.Option(
        None, "--keep-path", "-p", help="Glob pattern for paths to keep (for path strategy)"
    ),
    same_folder_only: bool = typer.Option(
        True, "--same-folder-only/--all-folders",
        help="Only delete duplicates within the same folder (keep cross-folder duplicates) [default: same-folder-only]"
    ),
    min_size: int = typer.Option(
        0, "--min-size", help="Minimum file size in bytes"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Preview changes without executing (default: dry-run)"
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Execute the deletion (overrides dry-run)"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt (only with --execute)"
    ),
) -> None:
    """Delete duplicate files using a keep strategy."""
    settings = get_settings()

    # If --execute is specified, it overrides dry-run
    if execute:
        dry_run = False

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

            # Filter groups based on same-folder-only flag
            if same_folder_only:
                same_folder_groups = [g for g in duplicate_groups if g.are_all_in_same_folder()]
                cross_folder_groups = [g for g in duplicate_groups if not g.are_all_in_same_folder()]

                if cross_folder_groups:
                    cross_folder_files = sum(g.count for g in cross_folder_groups)
                    print_info(
                        f"Skipping {len(cross_folder_groups)} groups ({cross_folder_files} files) "
                        "with duplicates in different folders"
                    )

                duplicate_groups = same_folder_groups

                if not duplicate_groups:
                    print_info("No same-folder duplicates found!")
                    if cross_folder_groups:
                        print_info("All duplicates are in different folders (intentionally kept)")
                    return

            # Collect files to trash and files to rename
            files_to_trash = []
            files_to_rename = []  # List of (file_id, old_name, new_name)

            # First pass: collect rename info without size
            group_rename_map = {}  # Map group to (file, new_name)
            if hasattr(deletion_strategy, 'get_rename_info'):
                for group in duplicate_groups:
                    rename_info = deletion_strategy.get_rename_info(group, include_size=False)
                    if rename_info:
                        group_rename_map[group.group_id] = (group, rename_info)

                # Detect naming conflicts (same name for different groups)
                name_to_groups = {}
                for group_id, (group, (file, new_name)) in group_rename_map.items():
                    if new_name not in name_to_groups:
                        name_to_groups[new_name] = []
                    name_to_groups[new_name].append(group_id)

                # For conflicting names, regenerate with file size
                conflicting_groups = set()
                for new_name, group_ids in name_to_groups.items():
                    if len(group_ids) > 1:
                        conflicting_groups.update(group_ids)

                # Regenerate names for conflicting groups
                for group_id in conflicting_groups:
                    group, (file, _) = group_rename_map[group_id]
                    rename_info = deletion_strategy.get_rename_info(group, include_size=True)
                    if rename_info:
                        group_rename_map[group_id] = (group, rename_info)

                # Collect final rename operations
                for group_id, (group, (file_to_keep, new_name)) in group_rename_map.items():
                    files_to_rename.append((file_to_keep.file_id, file_to_keep.name, new_name))

            # Collect files to trash
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
            if same_folder_only:
                print_info("Mode: Same-folder duplicates only")
            if files_to_rename:
                print_info(f"Files to rename: {len(files_to_rename)}")
            print_info(f"Files to trash: {len(files_to_trash)}")
            print_info(f"Space to recover: {naturalsize(total_space_saved)}")

            if dry_run:
                print_warning("\n[DRY RUN MODE] Preview only - no files will be modified\n")
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

            # Initialize managers
            service_factory = DriveServiceFactory(oauth_manager)
            rate_limiter = TokenBucketRateLimiter(settings.rate_limit)
            trash_manager = TrashManager(service_factory, rate_limiter)

            # Rename files first (if needed)
            if files_to_rename:
                print_info("\nRenaming files with merged names...")
                progress = create_progress()
                rename_results = {}

                with progress:
                    task = progress.add_task(
                        "[cyan]Renaming files...",
                        total=len(files_to_rename),
                    )

                    for file_id, old_name, new_name in files_to_rename:
                        try:
                            success = trash_manager.rename_file(file_id, new_name, dry_run)
                            rename_results[file_id] = success
                            if not dry_run and success:
                                print_info(f"  {old_name} → {new_name}")
                        except ActionError as e:
                            print_error(f"Failed to rename {old_name}: {e}")
                            rename_results[file_id] = False

                        progress.update(task, advance=1)

                successful_renames = sum(1 for success in rename_results.values() if success)
                if dry_run:
                    print_success(f"[DRY RUN] Would rename {successful_renames} files")
                else:
                    print_success(f"Renamed {successful_renames} files")

            # Trash files
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
                print_info("\nTo execute this deletion, run:")
                cmd_parts = ["gdrive-dedup delete --execute"]
                if strategy != "merge-names":
                    cmd_parts.append(f"--strategy {strategy}")
                if keep_path:
                    cmd_parts.append(f"--keep-path '{keep_path}'")
                if not same_folder_only:
                    cmd_parts.append("--all-folders")
                if min_size > 0:
                    cmd_parts.append(f"--min-size {min_size}")
                print_info(f"  {' '.join(cmd_parts)}")
                print_info("\nOr to skip confirmation prompt:")
                print_info(f"  {' '.join(cmd_parts)} --yes")
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
