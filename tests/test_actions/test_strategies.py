"""Tests for deletion strategies."""

from datetime import datetime

from gdrive_dedup.actions.strategies import (
    KeepNewestStrategy,
    KeepOldestStrategy,
    KeepShortestPathStrategy,
    get_strategy,
)
from gdrive_dedup.detector.models import DuplicateGroup, FileRecord


def test_keep_newest_strategy() -> None:
    """Test keep newest strategy."""
    files = [
        FileRecord(
            file_id="file1",
            name="test.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 1),
            path="/test1.txt",
        ),
        FileRecord(
            file_id="file2",
            name="test.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 5),
            path="/test2.txt",
        ),
    ]

    group = DuplicateGroup(group_id=1, files=files, size=1024, md5="abc123")
    strategy = KeepNewestStrategy()
    to_trash = strategy.select_files_to_trash(group)

    assert len(to_trash) == 1
    assert to_trash[0].file_id == "file1"


def test_keep_oldest_strategy() -> None:
    """Test keep oldest strategy."""
    files = [
        FileRecord(
            file_id="file1",
            name="test.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 1),
            path="/test1.txt",
        ),
        FileRecord(
            file_id="file2",
            name="test.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 5),
            path="/test2.txt",
        ),
    ]

    group = DuplicateGroup(group_id=1, files=files, size=1024, md5="abc123")
    strategy = KeepOldestStrategy()
    to_trash = strategy.select_files_to_trash(group)

    assert len(to_trash) == 1
    assert to_trash[0].file_id == "file2"


def test_keep_shortest_path_strategy() -> None:
    """Test keep shortest path strategy."""
    files = [
        FileRecord(
            file_id="file1",
            name="test.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 1),
            path="/very/long/path/to/file/test1.txt",
        ),
        FileRecord(
            file_id="file2",
            name="test.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 1),
            path="/test2.txt",
        ),
    ]

    group = DuplicateGroup(group_id=1, files=files, size=1024, md5="abc123")
    strategy = KeepShortestPathStrategy()
    to_trash = strategy.select_files_to_trash(group)

    assert len(to_trash) == 1
    assert to_trash[0].file_id == "file1"


def test_get_strategy() -> None:
    """Test strategy factory."""
    strategy = get_strategy("newest")
    assert isinstance(strategy, KeepNewestStrategy)

    strategy = get_strategy("oldest")
    assert isinstance(strategy, KeepOldestStrategy)
