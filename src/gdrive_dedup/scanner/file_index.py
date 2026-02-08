"""SQLite-backed file index."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from ..common.logging import get_logger
from ..detector.models import DuplicateGroup, FileRecord

logger = get_logger(__name__)


class FileIndex:
    """SQLite database for storing file metadata."""

    def __init__(self, db_path: Path) -> None:
        """Initialize file index.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._create_schema()

    def _create_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                md5 TEXT,
                mime_type TEXT NOT NULL,
                created_time TEXT NOT NULL,
                modified_time TEXT NOT NULL,
                path TEXT NOT NULL,
                trashed INTEGER NOT NULL DEFAULT 0,
                owned_by_me INTEGER NOT NULL DEFAULT 1
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_size ON files(size)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_md5 ON files(md5)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trashed ON files(trashed)")
        self.conn.commit()
        logger.debug(f"Initialized file index at {self.db_path}")

    def add_file(self, file: FileRecord) -> None:
        """Add or update a file in the index.

        Args:
            file: File record to add
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        self.conn.execute(
            """
            INSERT OR REPLACE INTO files
            (file_id, name, size, md5, mime_type, created_time, modified_time, path, trashed, owned_by_me)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file.file_id,
                file.name,
                file.size,
                file.md5,
                file.mime_type,
                file.created_time.isoformat(),
                file.modified_time.isoformat(),
                file.path,
                1 if file.trashed else 0,
                1 if file.owned_by_me else 0,
            ),
        )

    def add_files(self, files: list[FileRecord]) -> None:
        """Add multiple files in a batch.

        Args:
            files: List of file records to add
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO files
            (file_id, name, size, md5, mime_type, created_time, modified_time, path, trashed, owned_by_me)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f.file_id,
                    f.name,
                    f.size,
                    f.md5,
                    f.mime_type,
                    f.created_time.isoformat(),
                    f.modified_time.isoformat(),
                    f.path,
                    1 if f.trashed else 0,
                    1 if f.owned_by_me else 0,
                )
                for f in files
            ],
        )
        self.conn.commit()

    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """Get a file by ID.

        Args:
            file_id: File ID to retrieve

        Returns:
            File record or None if not found
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.execute(
            "SELECT * FROM files WHERE file_id = ?",
            (file_id,),
        )
        row = cursor.fetchone()
        return self._row_to_file(row) if row else None

    def count_files(self) -> int:
        """Get total number of files in index.

        Returns:
            File count
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.execute("SELECT COUNT(*) FROM files WHERE trashed = 0")
        return cursor.fetchone()[0]

    def find_by_size(self, min_size: int = 0) -> dict[int, list[str]]:
        """Find all files grouped by size.

        Args:
            min_size: Minimum file size to consider

        Returns:
            Dictionary mapping size to list of file IDs
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.execute(
            """
            SELECT size, GROUP_CONCAT(file_id) as ids
            FROM files
            WHERE trashed = 0 AND size >= ? AND md5 IS NOT NULL
            GROUP BY size
            HAVING COUNT(*) > 1
            """,
            (min_size,),
        )

        result: dict[int, list[str]] = {}
        for row in cursor:
            size, ids = row
            result[size] = ids.split(",")
        return result

    def find_by_md5(self, md5_list: list[str]) -> dict[str, list[str]]:
        """Find files by MD5 checksums.

        Args:
            md5_list: List of MD5 checksums to search for

        Returns:
            Dictionary mapping MD5 to list of file IDs
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        placeholders = ",".join("?" * len(md5_list))
        cursor = self.conn.execute(
            f"""
            SELECT md5, GROUP_CONCAT(file_id) as ids
            FROM files
            WHERE trashed = 0 AND md5 IN ({placeholders})
            GROUP BY md5
            HAVING COUNT(*) > 1
            """,
            md5_list,
        )

        result: dict[str, list[str]] = {}
        for row in cursor:
            md5, ids = row
            if md5:
                result[md5] = ids.split(",")
        return result

    def get_files_by_ids(self, file_ids: list[str]) -> list[FileRecord]:
        """Get multiple files by their IDs.

        Args:
            file_ids: List of file IDs

        Returns:
            List of file records
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        if not file_ids:
            return []

        placeholders = ",".join("?" * len(file_ids))
        cursor = self.conn.execute(
            f"SELECT * FROM files WHERE file_id IN ({placeholders})",
            file_ids,
        )

        return [self._row_to_file(row) for row in cursor]

    def clear(self) -> None:
        """Clear all files from the index."""
        if not self.conn:
            raise RuntimeError("Database connection not initialized")

        self.conn.execute("DELETE FROM files")
        self.conn.commit()
        logger.info("Cleared file index")

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _row_to_file(self, row: tuple) -> FileRecord:
        """Convert database row to FileRecord.

        Args:
            row: Database row tuple

        Returns:
            FileRecord instance
        """
        return FileRecord(
            file_id=row[0],
            name=row[1],
            size=row[2],
            md5=row[3],
            mime_type=row[4],
            created_time=datetime.fromisoformat(row[5]),
            modified_time=datetime.fromisoformat(row[6]),
            path=row[7],
            trashed=bool(row[8]),
            owned_by_me=bool(row[9]),
        )

    def __enter__(self) -> "FileIndex":
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()
