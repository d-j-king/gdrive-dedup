"""Pass 1: Group files by size."""

from ..common.logging import get_logger
from ..scanner.file_index import FileIndex

logger = get_logger(__name__)


class SizePass:
    """First pass: group files by size."""

    def __init__(self, file_index: FileIndex) -> None:
        """Initialize size pass.

        Args:
            file_index: File index to query
        """
        self.file_index = file_index

    def find_candidates(self, min_size: int = 0) -> dict[int, list[str]]:
        """Find files with duplicate sizes.

        Args:
            min_size: Minimum file size to consider

        Returns:
            Dictionary mapping size to list of file IDs
        """
        logger.info(f"Pass 1: Grouping files by size (min_size={min_size})")
        candidates = self.file_index.find_by_size(min_size)

        total_files = sum(len(files) for files in candidates.values())
        logger.info(
            f"Found {total_files} files in {len(candidates)} size groups "
            f"(avg {total_files / len(candidates):.1f} files/group)"
        )

        return candidates
