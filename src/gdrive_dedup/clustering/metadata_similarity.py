"""Metadata-based similarity scoring for video clustering."""

import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

import numpy as np

from ..common.logging import get_logger

logger = get_logger(__name__)


class MetadataFeatures:
    """Metadata features extracted from file records."""

    def __init__(
        self,
        file_id: str,
        name: str,
        created_time: datetime,
        modified_time: datetime,
        path: str,
    ):
        """Initialize metadata features.

        Args:
            file_id: File ID
            name: Filename
            created_time: File creation time
            modified_time: File modification time
            path: Full path to file
        """
        self.file_id = file_id
        self.name = name
        self.created_time = created_time
        self.modified_time = modified_time
        self.path = path

        # Extract derived features
        self.filename_date = self._extract_date_from_filename()
        self.clean_name = self._clean_filename()
        self.folder_path = self._get_folder_path()

    def _extract_date_from_filename(self) -> Optional[datetime]:
        """Extract date from filename if present.

        Handles formats like:
        - 2019-07-31
        - 20190731
        - 2019_07_31
        - Jul_31_2019
        """
        name = self.name.lower()

        # Try various date patterns
        patterns = [
            (r"(\d{4})[_-](\d{2})[_-](\d{2})", "%Y-%m-%d"),
            (r"(\d{8})", "%Y%m%d"),
            (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
        ]

        for pattern, date_format in patterns:
            match = re.search(pattern, name)
            if match:
                try:
                    if len(match.groups()) == 1:
                        # Single group (e.g., 20190731)
                        date_str = match.group(1)
                    else:
                        # Multiple groups (e.g., 2019, 07, 31)
                        date_str = "".join(match.groups())

                    # Parse based on format
                    if date_format == "%Y%m%d":
                        return datetime.strptime(date_str, date_format)
                    else:
                        return datetime.strptime(date_str, date_format)
                except ValueError:
                    continue

        return None

    def _clean_filename(self) -> str:
        """Clean filename for text similarity comparison.

        Removes:
        - File extension
        - Common junk patterns (IMG_, DSC_, etc.)
        - Dates and timestamps
        - Special characters
        """
        name = self.name.lower()

        # Remove extension
        name = re.sub(r"\.\w+$", "", name)

        # Remove common junk patterns
        junk_patterns = [
            r"^img[_-]?\d+",
            r"^dsc[_-]?\d+",
            r"^vid[_-]?\d+",
            r"^mov[_-]?\d+",
            r"^\d{8}[_-]\d{6}",  # 20190731_123456
            r"\d{4}[_-]\d{2}[_-]\d{2}",  # 2019-07-31
            r"\(\d+\)",  # (1), (2), etc.
            r"\s*-?\s*copy(\s+of)?",  # copy, copy of
        ]

        for pattern in junk_patterns:
            name = re.sub(pattern, "", name)

        # Remove special characters, keep only alphanumeric and spaces
        name = re.sub(r"[^a-z0-9\s]", " ", name)

        # Normalize whitespace
        name = " ".join(name.split())

        return name.strip()

    def _get_folder_path(self) -> str:
        """Extract folder path from full path."""
        if "/" in self.path:
            return self.path.rsplit("/", 1)[0]
        return ""


class MetadataSimilarityScorer:
    """Compute similarity based on metadata features."""

    def __init__(
        self,
        temporal_weight: float = 0.50,
        filename_weight: float = 0.35,
        path_weight: float = 0.15,
    ):
        """Initialize metadata similarity scorer.

        Args:
            temporal_weight: Weight for temporal similarity
            filename_weight: Weight for filename text similarity
            path_weight: Weight for folder path similarity
        """
        total = temporal_weight + filename_weight + path_weight
        self.temporal_weight = temporal_weight / total
        self.filename_weight = filename_weight / total
        self.path_weight = path_weight / total

        logger.info(
            f"Metadata weights: temporal={self.temporal_weight:.2f}, "
            f"filename={self.filename_weight:.2f}, path={self.path_weight:.2f}"
        )

    def compute_similarity(
        self, meta_a: MetadataFeatures, meta_b: MetadataFeatures
    ) -> float:
        """Compute metadata similarity between two files.

        Args:
            meta_a: Metadata for file A
            meta_b: Metadata for file B

        Returns:
            Similarity score (0-1)
        """
        temporal_sim = self._temporal_similarity(meta_a, meta_b)
        filename_sim = self._filename_similarity(meta_a, meta_b)
        path_sim = self._path_similarity(meta_a, meta_b)

        total = (
            self.temporal_weight * temporal_sim
            + self.filename_weight * filename_sim
            + self.path_weight * path_sim
        )

        return total

    def _temporal_similarity(
        self, meta_a: MetadataFeatures, meta_b: MetadataFeatures
    ) -> float:
        """Compute temporal similarity.

        Videos from the same date/session get high scores.

        Args:
            meta_a: Metadata for file A
            meta_b: Metadata for file B

        Returns:
            Temporal similarity (0-1)
        """
        # Use filename date if available, otherwise use created_time
        date_a = meta_a.filename_date or meta_a.created_time
        date_b = meta_b.filename_date or meta_b.created_time

        # Compute time difference
        time_diff = abs((date_a - date_b).total_seconds())

        # Scoring function:
        # Same day (0-24 hours): 1.0 → 0.9
        # Same week (1-7 days): 0.9 → 0.7
        # Same month (7-30 days): 0.7 → 0.4
        # Beyond 30 days: exponential decay

        if time_diff < 24 * 3600:  # Same day
            # Linear decay from 1.0 to 0.9
            return 1.0 - (time_diff / (24 * 3600)) * 0.1

        elif time_diff < 7 * 24 * 3600:  # Same week
            # Linear decay from 0.9 to 0.7
            days = time_diff / (24 * 3600)
            return 0.9 - ((days - 1) / 6) * 0.2

        elif time_diff < 30 * 24 * 3600:  # Same month
            # Linear decay from 0.7 to 0.4
            days = time_diff / (24 * 3600)
            return 0.7 - ((days - 7) / 23) * 0.3

        else:  # Beyond 30 days
            # Exponential decay
            months = time_diff / (30 * 24 * 3600)
            return max(0.0, 0.4 * np.exp(-months / 3))

    def _filename_similarity(
        self, meta_a: MetadataFeatures, meta_b: MetadataFeatures
    ) -> float:
        """Compute filename text similarity.

        Uses sequence matching on cleaned filenames.

        Args:
            meta_a: Metadata for file A
            meta_b: Metadata for file B

        Returns:
            Filename similarity (0-1)
        """
        if not meta_a.clean_name or not meta_b.clean_name:
            return 0.0

        # Use SequenceMatcher for fuzzy text matching
        matcher = SequenceMatcher(None, meta_a.clean_name, meta_b.clean_name)
        ratio = matcher.ratio()

        # Boost score if they share significant common substrings
        # (e.g., actor name, scene description)
        common_blocks = matcher.get_matching_blocks()
        total_match_len = sum(block.size for block in common_blocks)

        # If they share a long substring (>5 chars), boost the score
        if total_match_len > 5:
            boost = min(0.2, total_match_len / 50)  # Up to 20% boost
            ratio = min(1.0, ratio + boost)

        return ratio

    def _path_similarity(
        self, meta_a: MetadataFeatures, meta_b: MetadataFeatures
    ) -> float:
        """Compute folder path similarity.

        Files in same folder get score of 1.0, nearby folders get lower scores.

        Args:
            meta_a: Metadata for file A
            meta_b: Metadata for file B

        Returns:
            Path similarity (0-1)
        """
        if not meta_a.folder_path or not meta_b.folder_path:
            return 0.0

        # Same folder = 1.0
        if meta_a.folder_path == meta_b.folder_path:
            return 1.0

        # Compare path components
        path_a_parts = meta_a.folder_path.split("/")
        path_b_parts = meta_b.folder_path.split("/")

        # Count matching path components (from root)
        common_prefix = 0
        for pa, pb in zip(path_a_parts, path_b_parts):
            if pa == pb:
                common_prefix += 1
            else:
                break

        # Score based on common prefix ratio
        max_depth = max(len(path_a_parts), len(path_b_parts))
        if max_depth == 0:
            return 0.0

        return common_prefix / max_depth
