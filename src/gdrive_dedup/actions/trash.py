"""Trash file operations."""

from typing import Any

from googleapiclient.errors import HttpError

from ..auth.service import DriveServiceFactory
from ..common.exceptions import ActionError
from ..common.logging import get_logger
from ..common.rate_limiter import TokenBucketRateLimiter
from ..common.retry import exponential_backoff

logger = get_logger(__name__)


class TrashManager:
    """Manages trashing files (never hard-deletes)."""

    def __init__(
        self,
        service_factory: DriveServiceFactory,
        rate_limiter: TokenBucketRateLimiter,
    ) -> None:
        """Initialize trash manager.

        Args:
            service_factory: Factory for creating Drive API service
            rate_limiter: Rate limiter for API requests
        """
        self.service_factory = service_factory
        self.rate_limiter = rate_limiter

    @exponential_backoff()
    def trash_file(self, file_id: str, dry_run: bool = False) -> bool:
        """Trash a single file.

        Args:
            file_id: File ID to trash
            dry_run: If True, don't actually trash the file

        Returns:
            True if successful, False otherwise

        Raises:
            ActionError: If trash operation fails
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would trash file: {file_id}")
            return True

        try:
            service = self.service_factory.create_service()
            self.rate_limiter.acquire()

            # SAFETY INVARIANT: Only update trashed=True, never use files.delete()
            service.files().update(
                fileId=file_id,
                body={"trashed": True},
            ).execute()

            logger.info(f"Trashed file: {file_id}")
            return True

        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"File not found: {file_id}")
                return False
            raise ActionError(f"Failed to trash file {file_id}: {e}") from e
        except Exception as e:
            raise ActionError(f"Failed to trash file {file_id}: {e}") from e

    def trash_files(self, file_ids: list[str], dry_run: bool = False) -> dict[str, bool]:
        """Trash multiple files.

        Args:
            file_ids: List of file IDs to trash
            dry_run: If True, don't actually trash files

        Returns:
            Dictionary mapping file ID to success status
        """
        results = {}

        for file_id in file_ids:
            try:
                results[file_id] = self.trash_file(file_id, dry_run)
            except ActionError as e:
                logger.error(f"Failed to trash {file_id}: {e}")
                results[file_id] = False

        successful = sum(1 for success in results.values() if success)
        logger.info(
            f"Trashed {successful}/{len(file_ids)} files "
            f"{'(dry run)' if dry_run else ''}"
        )

        return results
