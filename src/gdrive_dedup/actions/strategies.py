"""Deletion strategies for choosing which duplicates to keep."""

from fnmatch import fnmatch
from typing import Optional

from ..common.logging import get_logger
from ..detector.models import DuplicateGroup, FileRecord
from .name_merger import NameMerger

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


class KeepDeepestPathStrategy(DeletionStrategy):
    """Keep the file with the deepest path (most nested in folder structure)."""

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Keep deepest path, trash rest."""
        if keep_path:
            matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]
            if matching_files:
                return [f for f in group.files if not fnmatch(f.path, keep_path)]

        # Calculate depth by counting path separators
        def path_depth(file: FileRecord) -> int:
            return file.path.count('/')

        deepest = max(group.files, key=path_depth)
        return [f for f in group.files if f.file_id != deepest.file_id]


class MergeNamesStrategy(DeletionStrategy):
    """Merge all meaningful filename information, then trash duplicates."""

    def __init__(self):
        self.name_merger = NameMerger()

    def select_files_to_trash(
        self, group: DuplicateGroup, keep_path: Optional[str] = None
    ) -> list[FileRecord]:
        """Merge names, keep one file (renamed), trash rest."""
        if keep_path:
            matching_files = [f for f in group.files if fnmatch(f.path, keep_path)]
            if matching_files:
                return [f for f in group.files if not fnmatch(f.path, keep_path)]

        # All files will be returned for potential trashing
        # But we'll mark one for keeping/renaming via get_rename_info()
        # For now, return all but the newest (we'll rename the newest)
        newest = group.newest_file()
        return [f for f in group.files if f.file_id != newest.file_id]

    def get_rename_info(self, group: DuplicateGroup, include_size: bool = False) -> Optional[tuple[FileRecord, str]]:
        """Get the file to keep and its new merged name.

        Args:
            group: Duplicate group
            include_size: Whether to include file size in the name for uniqueness

        Returns:
            Tuple of (file_to_keep, new_name) or None if no rename needed
        """
        # Extract just the filenames (not full paths)
        filenames = [f.name for f in group.files]

        # Merge the names, optionally including file size
        file_size = group.size if include_size else None
        merged_name = self.name_merger.merge_names(filenames, file_size)

        # Keep the newest file (arbitrary choice, content is identical)
        file_to_keep = group.newest_file()

        # Only rename if the merged name is different from current
        if merged_name != file_to_keep.name:
            logger.info(
                f"Will rename {file_to_keep.name} -> {merged_name} "
                f"(merged from {len(filenames)} duplicates)"
            )
            return (file_to_keep, merged_name)

        return None


def get_strategy(strategy_name: str) -> DeletionStrategy:
    """Get deletion strategy by name.

    Args:
        strategy_name: Strategy name (newest, oldest, shortest, longest, deepest, path, merge-names)

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
        "deepest": KeepDeepestPathStrategy,
        "path": KeepPathStrategy,
        "merge-names": MergeNamesStrategy,
    }

    strategy_class = strategies.get(strategy_name.lower())
    if not strategy_class:
        raise ValueError(
            f"Invalid strategy '{strategy_name}'. "
            f"Valid options: {', '.join(strategies.keys())}"
        )

    return strategy_class()
