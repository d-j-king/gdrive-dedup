"""Pass 2: Group files by MD5 checksum."""

from ..common.logging import get_logger
from ..scanner.file_index import FileIndex

logger = get_logger(__name__)


class ChecksumPass:
    """Second pass: group files by MD5 checksum."""

    def __init__(self, file_index: FileIndex) -> None:
        """Initialize checksum pass.

        Args:
            file_index: File index to query
        """
        self.file_index = file_index

    def find_duplicates(self, size_groups: dict[int, list[str]]) -> dict[str, list[str]]:
        """Find true duplicates by MD5 checksum.

        Args:
            size_groups: Groups of files with same size

        Returns:
            Dictionary mapping MD5 to list of file IDs
        """
        logger.info("Pass 2: Grouping by MD5 checksum")

        # Get all file IDs from size groups
        all_file_ids = [
            file_id for file_ids in size_groups.values() for file_id in file_ids
        ]

        if not all_file_ids:
            logger.info("No candidates to check")
            return {}

        # Get files and extract MD5s
        files = self.file_index.get_files_by_ids(all_file_ids)
        md5_list = [f.md5 for f in files if f.md5]

        if not md5_list:
            logger.info("No files with MD5 checksums")
            return {}

        # Find duplicates by MD5
        md5_groups = self.file_index.find_by_md5(md5_list)

        total_files = sum(len(files) for files in md5_groups.values())
        logger.info(
            f"Found {total_files} duplicate files in {len(md5_groups)} groups "
            f"(avg {total_files / len(md5_groups):.1f} files/group)"
        )

        return md5_groups
