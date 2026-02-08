"""Interactive duplicate review command."""

from typing import Optional

import typer
from humanize import naturalsize

from ..config.settings import get_settings
from ..detector.pipeline import DetectionPipeline
from ..scanner.file_index import FileIndex
from .formatters import create_table, print_error, print_info, print_success

review_app = typer.Typer(help="Review duplicate files interactively")


@review_app.command()
def review(
    group_id: Optional[int] = typer.Option(
        None, "--group", "-g", help="Review specific group ID"
    ),
    sort: str = typer.Option(
        "wasted", "--sort", "-s", help="Sort by: wasted, size, count"
    ),
    min_size: int = typer.Option(
        0, "--min-size", help="Minimum file size in bytes"
    ),
) -> None:
    """Interactively review duplicate file groups."""
    settings = get_settings()

    try:
        # Load duplicate groups from index
        with FileIndex(settings.db_path) as file_index:
            if file_index.count_files() == 0:
                print_error("No scan data found. Run 'gdrive-dedup scan' first.")
                raise typer.Exit(1)

            pipeline = DetectionPipeline(file_index)
            duplicate_groups = pipeline.detect_duplicates(min_size=min_size)

            if not duplicate_groups:
                print_success("No duplicates found!")
                return

            # Sort groups
            if sort == "wasted":
                duplicate_groups.sort(key=lambda g: g.wasted_size, reverse=True)
            elif sort == "size":
                duplicate_groups.sort(key=lambda g: g.size, reverse=True)
            elif sort == "count":
                duplicate_groups.sort(key=lambda g: g.count, reverse=True)
            else:
                print_error(f"Invalid sort option: {sort}")
                raise typer.Exit(1)

            # Filter to specific group if requested
            if group_id is not None:
                duplicate_groups = [g for g in duplicate_groups if g.group_id == group_id]
                if not duplicate_groups:
                    print_error(f"Group {group_id} not found")
                    raise typer.Exit(1)

            # Display groups
            print_info(f"Found {len(duplicate_groups)} duplicate groups\n")

            for group in duplicate_groups:
                print_info(
                    f"Group {group.group_id}: {group.count} files, "
                    f"{naturalsize(group.size)} each, "
                    f"{naturalsize(group.wasted_size)} wasted"
                )
                print_info(f"MD5: {group.md5}\n")

                table = create_table()
                table.add_column("File ID", style="cyan", width=33)
                table.add_column("Name", style="white", width=40)
                table.add_column("Modified", style="yellow", width=20)
                table.add_column("Path", style="green")

                for file in group.files:
                    table.add_row(
                        file.file_id,
                        file.name[:37] + "..." if len(file.name) > 40 else file.name,
                        file.modified_time.strftime("%Y-%m-%d %H:%M"),
                        file.path[:60] + "..." if len(file.path) > 63 else file.path,
                    )

                from .formatters import console
                console.print(table)
                print_info("")

            print_info(f"\nTotal groups: {len(duplicate_groups)}")
            total_wasted = sum(g.wasted_size for g in duplicate_groups)
            print_info(f"Total wasted space: {naturalsize(total_wasted)}")

    except Exception as e:
        print_error(f"Review failed: {e}")
        raise typer.Exit(1)
