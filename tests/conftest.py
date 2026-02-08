"""Shared pytest fixtures."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from gdrive_dedup.detector.models import FileRecord


@pytest.fixture
def sample_file() -> FileRecord:
    """Create a sample file record."""
    return FileRecord(
        file_id="file1",
        name="test.txt",
        size=1024,
        md5="abc123",
        mime_type="text/plain",
        created_time=datetime(2024, 1, 1, 12, 0, 0),
        modified_time=datetime(2024, 1, 1, 12, 0, 0),
        path="/folder/test.txt",
        trashed=False,
        owned_by_me=True,
    )


@pytest.fixture
def sample_files() -> list[FileRecord]:
    """Create multiple sample file records."""
    return [
        FileRecord(
            file_id=f"file{i}",
            name=f"test{i}.txt",
            size=1024,
            md5="abc123",
            mime_type="text/plain",
            created_time=datetime(2024, 1, i, 12, 0, 0),
            modified_time=datetime(2024, 1, i, 12, 0, 0),
            path=f"/folder{i}/test{i}.txt",
            trashed=False,
            owned_by_me=True,
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def mock_drive_service() -> Mock:
    """Create a mock Drive API service."""
    service = Mock()
    files_resource = Mock()
    service.files.return_value = files_resource
    return service


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"
