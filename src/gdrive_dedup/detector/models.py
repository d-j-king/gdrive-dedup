"""Data models for files and duplicate groups."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class FileRecord:
    """Represents a file in Google Drive."""

    file_id: str
    name: str
    size: int
    md5: Optional[str]
    mime_type: str
    created_time: datetime
    modified_time: datetime
    path: str
    trashed: bool = False
    owned_by_me: bool = True

    @property
    def is_workspace_file(self) -> bool:
        """Check if this is a Google Workspace file (no MD5)."""
        from ..common.constants import WORKSPACE_MIME_TYPES
        return self.mime_type in WORKSPACE_MIME_TYPES


@dataclass
class DuplicateGroup:
    """A group of duplicate files."""

    group_id: int
    files: list[FileRecord]
    size: int
    md5: Optional[str] = None

    @property
    def total_size(self) -> int:
        """Total size of all duplicates in this group."""
        return self.size * len(self.files)

    @property
    def wasted_size(self) -> int:
        """Wasted space (size of all duplicates except one)."""
        return self.size * (len(self.files) - 1)

    @property
    def count(self) -> int:
        """Number of duplicate files in this group."""
        return len(self.files)

    def newest_file(self) -> FileRecord:
        """Get the most recently modified file."""
        return max(self.files, key=lambda f: f.modified_time)

    def oldest_file(self) -> FileRecord:
        """Get the oldest file by modification time."""
        return min(self.files, key=lambda f: f.modified_time)

    def shortest_path(self) -> FileRecord:
        """Get file with shortest path."""
        return min(self.files, key=lambda f: len(f.path))

    def longest_path(self) -> FileRecord:
        """Get file with longest path."""
        return max(self.files, key=lambda f: len(f.path))

    def are_all_in_same_folder(self) -> bool:
        """Check if all files in this group are in the same folder.

        Returns:
            True if all files are in the same folder, False otherwise
        """
        if len(self.files) <= 1:
            return True

        # Extract folder path (everything before the last /)
        def get_folder(path: str) -> str:
            return path.rsplit('/', 1)[0] if '/' in path else ''

        folders = {get_folder(f.path) for f in self.files}
        return len(folders) == 1
