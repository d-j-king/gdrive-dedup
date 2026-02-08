"""Intelligent filename parsing and merging."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NameComponents:
    """Parsed components of a filename."""

    dates: list[datetime]
    times: list[str]  # Time components (HH:MM:SS or HHMMSS)
    descriptive_text: list[str]
    extension: str
    is_generic: bool


class NameParser:
    """Parse filenames into meaningful components."""

    # Generic junk patterns (case-insensitive)
    GENERIC_PATTERNS = [
        r'^IMG_\d+$',
        r'^DSC_?\d+$',
        r'^DCIM_?\d+$',
        r'^PIC_?\d+$',
        r'^VID_?\d+$',
        r'^MOV_?\d+$',
        r'^download',
        r'^untitled',
        r'^image',
        r'^photo',
        r'^video',
        r'^file',
        r'^[a-f0-9]{8,}$',  # Long hex strings (hashes)
        r'^[a-z0-9_-]{20,}$',  # Random generated names
    ]

    # Copy notation patterns to remove
    COPY_PATTERNS = [
        r'\s*-?\s*copy(\s+of)?',
        r'\s*\(\d+\)',
        r'\s*\[\d+\]',
        r'\s*-\s*\d+$',
        r'\s*copy\s*\d*',
    ]

    # Date patterns (in order of preference for output)
    DATE_PATTERNS = [
        (r'(\d{4})[_-](\d{2})[_-](\d{2})', '%Y-%m-%d'),  # 2024-01-15
        (r'(\d{4})(\d{2})(\d{2})', '%Y%m%d'),  # 20240115
        (r'(\d{2})[_-](\d{2})[_-](\d{4})', '%m-%d-%Y'),  # 01-15-2024
        (r'(\d{2})(\d{2})(\d{4})', '%m%d%Y'),  # 01152024
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[_\s-]?(\d{1,2})[_\s-]?(\d{4})', '%b-%d-%Y'),  # Jan-15-2024
    ]

    # Time patterns
    TIME_PATTERNS = [
        r'(\d{2})[:\-_](\d{2})[:\-_](\d{2})',  # 02:14:50 or 02-14-50
        r'(\d{6})',  # 021450 (HHMMSS)
    ]

    def parse(self, filename: str) -> NameComponents:
        """Parse a filename into components.

        Args:
            filename: Full filename with extension

        Returns:
            NameComponents with extracted parts
        """
        # Split extension
        name, ext = self._split_extension(filename)

        # Remove copy notations
        name = self._remove_copy_notations(name)

        # Extract dates and times
        dates = self._extract_dates(name)
        times = self._extract_times(name)

        # Remove dates and times from name for text extraction
        name_without_datetime = self._remove_dates(name)
        name_without_datetime = self._remove_times(name_without_datetime)

        # Extract descriptive text
        descriptive_text = self._extract_descriptive_text(name_without_datetime)

        # Check if it's generic junk
        is_generic = self._is_generic(name_without_datetime, descriptive_text)

        return NameComponents(
            dates=dates,
            times=times,
            descriptive_text=descriptive_text,
            extension=ext,
            is_generic=is_generic,
        )

    def _split_extension(self, filename: str) -> tuple[str, str]:
        """Split filename into name and extension."""
        if '.' in filename:
            parts = filename.rsplit('.', 1)
            return parts[0], '.' + parts[1]
        return filename, ''

    def _remove_copy_notations(self, name: str) -> str:
        """Remove copy notations like '(1)', 'copy of', etc."""
        for pattern in self.COPY_PATTERNS:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        return name.strip()

    def _extract_dates(self, name: str) -> list[datetime]:
        """Extract dates from filename."""
        dates = []
        for pattern, fmt in self.DATE_PATTERNS:
            matches = re.finditer(pattern, name, flags=re.IGNORECASE)
            for match in matches:
                try:
                    # Reconstruct date string for parsing
                    if '%b' in fmt:
                        # Month name format
                        date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                    else:
                        # Numeric format
                        date_str = ''.join(match.groups())
                        if '-' in fmt:
                            # Add separators
                            if fmt == '%Y-%m-%d':
                                date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                            elif fmt == '%m-%d-%Y':
                                date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

                    date_obj = datetime.strptime(date_str, fmt.replace('_', '-'))
                    dates.append(date_obj)
                except ValueError:
                    continue

        return dates

    def _remove_dates(self, name: str) -> str:
        """Remove date patterns from name."""
        for pattern, _ in self.DATE_PATTERNS:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        return name

    def _extract_times(self, name: str) -> list[str]:
        """Extract time components from filename."""
        times = []
        for pattern in self.TIME_PATTERNS:
            matches = re.finditer(pattern, name)
            for match in matches:
                # Normalize to HH-MM-SS format
                if len(match.groups()) == 3:
                    # Already separated (HH:MM:SS or HH-MM-SS)
                    time_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                else:
                    # Compact format (HHMMSS)
                    time_compact = match.group(1)
                    if len(time_compact) == 6:
                        time_str = f"{time_compact[0:2]}-{time_compact[2:4]}-{time_compact[4:6]}"
                    else:
                        continue
                times.append(time_str)
        return times

    def _remove_times(self, name: str) -> str:
        """Remove time patterns from name."""
        for pattern in self.TIME_PATTERNS:
            name = re.sub(pattern, '', name)
        return name

    def _extract_descriptive_text(self, name: str) -> list[str]:
        """Extract descriptive words from filename."""
        # Split on common separators
        words = re.split(r'[_\-\s.]+', name)

        # Filter out empty, numeric-only, or very short words
        descriptive = []
        for word in words:
            word = word.strip()
            if not word:
                continue
            if word.isdigit():
                continue
            if len(word) < 2:
                continue
            # Keep words with letters
            if re.search(r'[a-zA-Z]{2,}', word):
                descriptive.append(word)

        return descriptive

    def _is_generic(self, name: str, descriptive_text: list[str]) -> bool:
        """Check if filename is generic junk."""
        # If we have descriptive text, it's not generic
        if descriptive_text:
            return False

        # Check against generic patterns
        name_clean = re.sub(r'[_\-\s.]+', '', name).lower()
        for pattern in self.GENERIC_PATTERNS:
            if re.match(pattern, name_clean, flags=re.IGNORECASE):
                return True

        return False


class NameMerger:
    """Merge multiple filenames into one rich filename."""

    def __init__(self):
        self.parser = NameParser()

    def merge_names(self, filenames: list[str], file_size: Optional[int] = None) -> str:
        """Merge multiple filenames into one rich filename.

        Args:
            filenames: List of filenames to merge
            file_size: Optional file size in bytes to append if needed for uniqueness

        Returns:
            Merged filename with all meaningful information
        """
        if not filenames:
            return ""

        if len(filenames) == 1:
            return filenames[0]

        # Parse all filenames
        components = [self.parser.parse(name) for name in filenames]

        # Get extension (use first non-empty)
        extension = next((c.extension for c in components if c.extension), '')

        # Collect all dates
        all_dates = []
        for comp in components:
            all_dates.extend(comp.dates)

        # Get oldest date if any (prefer older dates in name)
        chosen_date: Optional[datetime] = None
        if all_dates:
            chosen_date = min(all_dates)

        # Collect all times
        all_times = []
        for comp in components:
            all_times.extend(comp.times)

        # Get first time if any (use first occurrence)
        chosen_time: Optional[str] = None
        if all_times:
            chosen_time = all_times[0]

        # Collect all descriptive text (deduplicate while preserving order)
        all_text = []
        seen_lower = set()
        for comp in components:
            for word in comp.descriptive_text:
                word_lower = word.lower()
                if word_lower not in seen_lower:
                    all_text.append(word)
                    seen_lower.add(word_lower)

        # Build merged name
        parts = []

        if chosen_date:
            date_str = chosen_date.strftime('%Y-%m-%d')
            # Include time if available for uniqueness
            if chosen_time:
                date_str = f"{date_str}-{chosen_time}"
            parts.append(date_str)

        if all_text:
            parts.extend(all_text)

        # If we got nothing meaningful, fall back to first non-generic name
        if not parts:
            for comp, name in zip(components, filenames):
                if not comp.is_generic:
                    return name
            # All generic, just use first
            return filenames[0]

        # Join with hyphens
        merged = '-'.join(parts)

        # Append file size if provided (for uniqueness across groups)
        if file_size:
            # Convert to human-readable size (KB, MB, GB)
            if file_size < 1024:
                size_str = f"{file_size}B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size // 1024}KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size // (1024 * 1024)}MB"
            else:
                size_str = f"{file_size // (1024 * 1024 * 1024)}GB"
            merged = f"{merged}-{size_str}"

        merged = merged + extension

        return merged
