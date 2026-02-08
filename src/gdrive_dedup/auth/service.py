"""Google Drive API service factory."""

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest

from ..common.exceptions import AuthenticationError
from ..common.logging import get_logger
from .oauth import OAuthManager

logger = get_logger(__name__)


class DriveServiceFactory:
    """Factory for creating Google Drive API service instances."""

    def __init__(self, oauth_manager: OAuthManager) -> None:
        """Initialize service factory.

        Args:
            oauth_manager: OAuth manager for authentication
        """
        self.oauth_manager = oauth_manager

    def create_service(self) -> Any:
        """Create authenticated Drive API service.

        Returns:
            Google Drive API service instance

        Raises:
            AuthenticationError: If not authenticated
        """
        creds = self.oauth_manager.get_credentials()
        if not creds:
            raise AuthenticationError(
                "Not authenticated. Please run 'gdrive-dedup auth login' first."
            )

        try:
            service = build("drive", "v3", credentials=creds)
            logger.debug("Created Drive API service")
            return service
        except Exception as e:
            raise AuthenticationError(f"Failed to create Drive service: {e}") from e


def set_request_timeout(request: HttpRequest, timeout: int = 60) -> HttpRequest:
    """Set timeout for API request.

    Args:
        request: HTTP request object
        timeout: Timeout in seconds

    Returns:
        Request with timeout set
    """
    request.http.timeout = timeout
    return request
