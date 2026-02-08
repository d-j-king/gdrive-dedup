"""Tests for data models."""

from datetime import datetime

from gdrive_dedup.detector.models import DuplicateGroup, FileRecord


def test_file_record_creation() -> None:
    """Test creating a FileRecord."""
    file = FileRecord(
        file_id="test123",
        name="test.txt",
        size=1024,
        md5="abc123",
        mime_type="text/plain",
        created_time=datetime(2024, 1, 1),
        modified_time=datetime(2024, 1, 2),
        path="/test.txt",
    )

    assert file.file_id == "test123"
    assert file.name == "test.txt"
    assert file.size == 1024
    assert file.md5 == "abc123"


def test_duplicate_group_wasted_size() -> None:
    """Test DuplicateGroup wasted size calculation."""
    files = [
        FileRecord(
            file_id=f"file{i}",
            name=f"test{i}.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, i),
            path=f"/test{i}.txt",
        )
        for i in range(1, 4)
    ]

    group = DuplicateGroup(group_id=1, files=files, size=1024, md5="abc123")

    assert group.count == 3
    assert group.total_size == 3072  # 1024 * 3
    assert group.wasted_size == 2048  # 1024 * 2


def test_duplicate_group_newest_file() -> None:
    """Test finding newest file in group."""
    files = [
        FileRecord(
            file_id="file1",
            name="test1.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 1),
            path="/test1.txt",
        ),
        FileRecord(
            file_id="file2",
            name="test2.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, 1),
            modified_time=datetime(2024, 1, 5),
            path="/test2.txt",
        ),
    ]

    group = DuplicateGroup(group_id=1, files=files, size=1024, md5="abc123")
    newest = group.newest_file()

    assert newest.file_id == "file2"
    assert newest.modified_time == datetime(2024, 1, 5)
