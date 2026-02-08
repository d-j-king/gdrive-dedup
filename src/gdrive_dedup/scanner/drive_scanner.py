"""Google Drive file scanner."""

from datetime import datetime
from typing import Any, Iterator, Optional

from ..auth.service import DriveServiceFactory
from ..common.constants import PAGE_SIZE, WORKSPACE_MIME_TYPES
from ..common.exceptions import ScanError
from ..common.logging import get_logger
from ..common.rate_limiter import TokenBucketRateLimiter
from ..common.retry import exponential_backoff
from ..detector.models import FileRecord

logger = get_logger(__name__)


class DriveScanner:
    """Scans Google Drive for files and metadata."""

    def __init__(
        self,
        service_factory: DriveServiceFactory,
        rate_limiter: TokenBucketRateLimiter,
        page_size: int = PAGE_SIZE,
    ) -> None:
        """Initialize drive scanner.

        Args:
            service_factory: Factory for creating Drive API service
            rate_limiter: Rate limiter for API requests
            page_size: Number of files to fetch per page
        """
        self.service_factory = service_factory
        self.rate_limiter = rate_limiter
        self.page_size = page_size
        self._folder_cache: dict[str, str] = {}

    @exponential_backoff()
    def scan_files(
        self,
        folder_id: Optional[str] = None,
        owned_only: bool = True,
        min_size: int = 0,
    ) -> Iterator[FileRecord]:
        """Scan files from Google Drive.

        Args:
            folder_id: Optional folder ID to scan (None for entire drive)
            owned_only: If True, only scan files owned by the user
            min_size: Minimum file size in bytes

        Yields:
            FileRecord instances

        Raises:
            ScanError: If scan fails
        """
        try:
            service = self.service_factory.create_service()

            # Build query
            query_parts = ["trashed = false"]

            # Exclude workspace files
            for mime_type in WORKSPACE_MIME_TYPES:
                query_parts.append(f"mimeType != '{mime_type}'")

            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            if owned_only:
                query_parts.append("'me' in owners")

            if min_size > 0:
                query_parts.append(f"size >= {min_size}")

            query = " and ".join(query_parts)

            # Fields to retrieve
            fields = (
                "nextPageToken, files(id, name, size, md5Checksum, mimeType, "
                "createdTime, modifiedTime, parents, trashed, ownedByMe)"
            )

            page_token = None
            total_files = 0

            while True:
                self.rate_limiter.acquire()

                response = (
                    service.files()
                    .list(
                        q=query,
                        pageSize=self.page_size,
                        pageToken=page_token,
                        fields=fields,
                        orderBy="modifiedTime desc",
                    )
                    .execute()
                )

                files = response.get("files", [])

                for file_data in files:
                    # Skip files without size or MD5
                    if "size" not in file_data or "md5Checksum" not in file_data:
                        continue

                    try:
                        file_record = self._parse_file(file_data)
                        yield file_record
                        total_files += 1
                    except Exception as e:
                        logger.warning(f"Failed to parse file {file_data.get('id')}: {e}")
                        continue

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            logger.info(f"Scanned {total_files} files")

        except Exception as e:
            raise ScanError(f"Failed to scan drive: {e}") from e

    def get_file_path(self, file_id: str, parents: list[str]) -> str:
        """Get full path to a file.

        Args:
            file_id: File ID
            parents: List of parent folder IDs

        Returns:
            File path string
        """
        if not parents:
            return "/"

        path_parts = []
        current_id = parents[0]

        # Walk up the parent chain
        while current_id:
            if current_id in self._folder_cache:
                folder_name = self._folder_cache[current_id]
            else:
                folder_name = self._fetch_folder_name(current_id)
                self._folder_cache[current_id] = folder_name

            if folder_name:
                path_parts.insert(0, folder_name)

            # Get parent of this folder
            parent_id = self._fetch_parent_id(current_id)
            if not parent_id or parent_id == current_id:
                break
            current_id = parent_id

        return "/" + "/".join(path_parts) if path_parts else "/"

    @exponential_backoff()
    def _fetch_folder_name(self, folder_id: str) -> str:
        """Fetch folder name by ID.

        Args:
            folder_id: Folder ID

        Returns:
            Folder name
        """
        try:
            service = self.service_factory.create_service()
            self.rate_limiter.acquire()

            file = service.files().get(fileId=folder_id, fields="name").execute()
            return file.get("name", "")
        except Exception as e:
            logger.warning(f"Failed to fetch folder name for {folder_id}: {e}")
            return ""

    @exponential_backoff()
    def _fetch_parent_id(self, folder_id: str) -> Optional[str]:
        """Fetch parent folder ID.

        Args:
            folder_id: Folder ID

        Returns:
            Parent folder ID or None
        """
        try:
            service = self.service_factory.create_service()
            self.rate_limiter.acquire()

            file = service.files().get(fileId=folder_id, fields="parents").execute()
            parents = file.get("parents", [])
            return parents[0] if parents else None
        except Exception as e:
            logger.debug(f"Failed to fetch parent for {folder_id}: {e}")
            return None

    def _parse_file(self, file_data: dict[str, Any]) -> FileRecord:
        """Parse file data from API response.

        Args:
            file_data: File data from API

        Returns:
            FileRecord instance
        """
        parents = file_data.get("parents", [])
        path = self.get_file_path(file_data["id"], parents)

        return FileRecord(
            file_id=file_data["id"],
            name=file_data["name"],
            size=int(file_data.get("size", 0)),
            md5=file_data.get("md5Checksum"),
            mime_type=file_data.get("mimeType", ""),
            created_time=datetime.fromisoformat(
                file_data["createdTime"].replace("Z", "+00:00")
            ),
            modified_time=datetime.fromisoformat(
                file_data["modifiedTime"].replace("Z", "+00:00")
            ),
            path=path,
            trashed=file_data.get("trashed", False),
            owned_by_me=file_data.get("ownedByMe", True),
        )
