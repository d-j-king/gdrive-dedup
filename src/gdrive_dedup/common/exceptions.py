"""Custom exception hierarchy."""


class GDriveDedupError(Exception):
    """Base exception for all gdrive-dedup errors."""


class AuthenticationError(GDriveDedupError):
    """Authentication or authorization failed."""


class ScanError(GDriveDedupError):
    """Error during drive scanning."""


class DetectionError(GDriveDedupError):
    """Error during duplicate detection."""


class ActionError(GDriveDedupError):
    """Error performing file actions (trash, delete)."""


class RateLimitError(GDriveDedupError):
    """Rate limit exceeded."""


class ConfigError(GDriveDedupError):
    """Configuration error."""
