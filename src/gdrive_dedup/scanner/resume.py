"""Scan checkpoint/resume functionality."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..common.logging import get_logger

logger = get_logger(__name__)


class ScanCheckpoint:
    """Manages scan state for resume functionality."""

    def __init__(self, checkpoint_path: Path) -> None:
        """Initialize checkpoint manager.

        Args:
            checkpoint_path: Path to checkpoint file
        """
        self.checkpoint_path = checkpoint_path
        self.page_token: Optional[str] = None
        self.files_scanned: int = 0
        self.last_update: Optional[datetime] = None

    def save(self, page_token: Optional[str], files_scanned: int) -> None:
        """Save checkpoint state.

        Args:
            page_token: Current API page token
            files_scanned: Number of files scanned so far
        """
        self.page_token = page_token
        self.files_scanned = files_scanned
        self.last_update = datetime.now()

        checkpoint_data = {
            "page_token": self.page_token,
            "files_scanned": self.files_scanned,
            "last_update": self.last_update.isoformat(),
        }

        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.debug(f"Saved checkpoint: {self.files_scanned} files")

    def load(self) -> bool:
        """Load checkpoint state.

        Returns:
            True if checkpoint was loaded, False if no checkpoint exists
        """
        if not self.checkpoint_path.exists():
            return False

        try:
            with open(self.checkpoint_path, "r") as f:
                checkpoint_data = json.load(f)

            self.page_token = checkpoint_data.get("page_token")
            self.files_scanned = checkpoint_data.get("files_scanned", 0)

            last_update_str = checkpoint_data.get("last_update")
            if last_update_str:
                self.last_update = datetime.fromisoformat(last_update_str)

            logger.info(
                f"Loaded checkpoint: {self.files_scanned} files, "
                f"last updated {self.last_update}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return False

    def clear(self) -> None:
        """Clear checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.debug("Cleared checkpoint")

        self.page_token = None
        self.files_scanned = 0
        self.last_update = None
