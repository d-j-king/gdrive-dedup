"""Application settings."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="GDRIVE_DEDUP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".gdrive-dedup",
        description="Data directory for database, tokens, etc.",
    )

    # API settings
    rate_limit: float = Field(
        default=10.0,
        description="API requests per second",
    )
    page_size: int = Field(
        default=1000,
        description="Number of files to fetch per page",
    )
    batch_size: int = Field(
        default=100,
        description="Number of operations to batch",
    )

    # Scan settings
    min_file_size: int = Field(
        default=0,
        description="Minimum file size in bytes to consider",
    )
    byte_compare: bool = Field(
        default=False,
        description="Enable byte-by-byte comparison for extra accuracy",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    log_file: Optional[Path] = Field(
        default=None,
        description="Optional log file path",
    )

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def token_path(self) -> Path:
        """Path to OAuth token file."""
        return self.data_dir / "token.json"

    @property
    def credentials_path(self) -> Path:
        """Path to OAuth credentials file."""
        return self.data_dir / "credentials.json"

    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.data_dir / "file_index.db"

    @property
    def checkpoint_path(self) -> Path:
        """Path to scan checkpoint file."""
        return self.data_dir / "scan_checkpoint.json"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset global settings instance."""
    global _settings
    _settings = None
