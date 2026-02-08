"""CSV and JSON export functionality."""

import csv
import json
from pathlib import Path

from ..common.logging import get_logger
from ..detector.models import DuplicateGroup

logger = get_logger(__name__)


class ReportExporter:
    """Exports duplicate groups to CSV or JSON."""

    def export_csv(self, groups: list[DuplicateGroup], output_path: Path) -> None:
        """Export duplicate groups to CSV.

        Args:
            groups: List of duplicate groups
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "group_id",
                "file_id",
                "name",
                "size",
                "md5",
                "created_time",
                "modified_time",
                "path",
                "owned_by_me",
            ])

            # Data
            for group in groups:
                for file in group.files:
                    writer.writerow([
                        group.group_id,
                        file.file_id,
                        file.name,
                        file.size,
                        file.md5,
                        file.created_time.isoformat(),
                        file.modified_time.isoformat(),
                        file.path,
                        file.owned_by_me,
                    ])

        logger.info(f"Exported {len(groups)} groups to CSV: {output_path}")

    def export_json(self, groups: list[DuplicateGroup], output_path: Path) -> None:
        """Export duplicate groups to JSON.

        Args:
            groups: List of duplicate groups
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "total_groups": len(groups),
            "total_files": sum(g.count for g in groups),
            "total_wasted_space": sum(g.wasted_size for g in groups),
            "groups": [
                {
                    "group_id": group.group_id,
                    "size": group.size,
                    "md5": group.md5,
                    "count": group.count,
                    "wasted_size": group.wasted_size,
                    "files": [
                        {
                            "file_id": f.file_id,
                            "name": f.name,
                            "size": f.size,
                            "md5": f.md5,
                            "created_time": f.created_time.isoformat(),
                            "modified_time": f.modified_time.isoformat(),
                            "path": f.path,
                            "owned_by_me": f.owned_by_me,
                        }
                        for f in group.files
                    ],
                }
                for group in groups
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(groups)} groups to JSON: {output_path}")
