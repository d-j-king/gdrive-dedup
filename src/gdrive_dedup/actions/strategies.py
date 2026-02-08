"""Deletion strategies for choosing which duplicates to keep."""

from fnmatch import fnmatch
from typing import Optional

from ..common.logging import get_logger
from ..detector.models import DuplicateGroup, FileRecord

logger = get_logger(__name__)


class DeletionStrategy:
    """Base class for deletion strategies."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Select which files to trash from a duplicate group.

        Args:
            group: Duplicate group
            keep_path: Optional glob pattern for paths to keep

        Returns:
            List of files to trash
        """
        raise NotImplementedError


class KeepNewestStrategy(DeletionStrategy):
    """Keep the most recently modified file."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Keep newest, trash rest."""
        if keep_path:
            # Check if any file matches the keep path
            matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]
            if matching_files:
                # Keep all matching files, trash non-matching
                return [f for f in group.files if not fnmatch(f.path, keep_path)]

        newest = group.newest_file()
        return [f for f in group.files if f.file_id != newest.file_id]


class KeepOldestStrategy(DeletionStrategy):
    """Keep the oldest file by modification time."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Keep oldest, trash rest."""
        if keep_path:
            matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]
            if matching_files:
                return [f for f in group.files if not fnmatch(f.path, keep_path)]

        oldest = group.oldest_file()
        return [f for f in group.files if f.file_id != oldest.file_id]


class KeepShortestPathStrategy(DeletionStrategy):
    """Keep the file with the shortest path."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Keep shortest path, trash rest."""
        if keep_path:
            matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]
            if matching_files:
                return [f for f in group.files if not fnmatch(f.path, keep_path)]

        shortest = group.shortest_path()
        return [f for f in group.files if f.file_id != shortest.file_id]


class KeepLongestPathStrategy(DeletionStrategy):
    """Keep the file with the longest path."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Keep longest path, trash rest."""
        if keep_path:
            matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]
            if matching_files:
                return [f for f in group.files if not fnmatch(f.path, keep_path)]

        longest = group.longest_path()
        return [f for f in group.files if f.file_id != longest.file_id]


class KeepPathStrategy(DeletionStrategy):
    """Keep files matching a specific path pattern."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Keep files matching path pattern, trash rest."""
        if not keep_path:
            logger.warning("No keep_path specified for path strategy, keeping first file")
            return group.files[1:]

        # Keep all files matching the pattern
        matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]

        if not matching_files:
            logger.warning(
                f"No files match pattern '{keep_path}' in group {group.group_id}, "
                "keeping first file"
            )
            return group.files[1:]

        # Trash all non-matching files
        return [f for f in group.files if not fnmatch(f.path, keep_path)]


def get_strategy(strategy_name: str) -> DeletionStrategy:
    """Get deletion strategy by name.

    Args:
        strategy_name: Strategy name (newest, oldest, shortest, longest, path)

    Returns:
        DeletionStrategy instance

    Raises:
        ValueError: If strategy name is invalid
    """
    strategies = {
        "newest": KeepNewestStrategy,
        "oldest": KeepOldestStrategy,
        "shortest": KeepShortestPathStrategy,
        "longest": KeepLongestPathStrategy,
        "path": KeepPathStrategy,
    }

    strategy_class = strategies.get(strategy_name.lower())
    if not strategy_class:
        raise ValueError(
            f"Invalid strategy '{strategy_name}'. "
            f"Valid options: {', '.join(strategies.keys())}"
        )

    return strategy_class()
