"""Multi-pass duplicate detection pipeline."""

from ..common.logging import get_logger
from ..scanner.file_index import FileIndex
from .byte_pass import BytePass
from .checksum_pass import ChecksumPass
from .models import DuplicateGroup
from .size_pass import SizePass

logger = get_logger(__name__)


class DetectionPipeline:
    """Orchestrates multi-pass duplicate detection."""

    def __init__(self, file_index: FileIndex) -> None:
        """Initialize detection pipeline.

        Args:
            file_index: File index to analyze
        """
        self.file_index = file_index
        self.size_pass = SizePass(file_index)
        self.checksum_pass = ChecksumPass(file_index)
        self.byte_pass = BytePass()

    def detect_duplicates(
        self,
        min_size: int = 0,
        byte_compare: bool = False,
    ) -> list[DuplicateGroup]:
        """Run duplicate detection pipeline.

        Args:
            min_size: Minimum file size to consider
            byte_compare: Enable byte-by-byte comparison

        Returns:
            List of duplicate groups
        """
        logger.info("Starting duplicate detection pipeline")

        # Pass 1: Group by size
        size_groups = self.size_pass.find_candidates(min_size)

        if not size_groups:
            logger.info("No duplicate candidates found")
            return []

        # Pass 2: Group by MD5
        md5_groups = self.checksum_pass.find_duplicates(size_groups)

        if not md5_groups:
            logger.info("No true duplicates found")
            return []

        # Pass 3: Optional byte comparison
        if byte_compare:
            md5_groups = self.byte_pass.verify_duplicates(md5_groups)

        # Convert to DuplicateGroup objects
        duplicate_groups = []
        for group_id, (md5, file_ids) in enumerate(md5_groups.items(), start=1):
            files = self.file_index.get_files_by_ids(file_ids)

            if len(files) > 1:
                # All files in group have same size
                size = files[0].size

                group = DuplicateGroup(
                    group_id=group_id,
                    files=files,
                    size=size,
                    md5=md5,
                )
                duplicate_groups.append(group)

        # Sort by wasted space (largest first)
        duplicate_groups.sort(key=lambda g: g.wasted_size, reverse=True)

        logger.info(f"Detection complete: {len(duplicate_groups)} duplicate groups found")
        return duplicate_groups
