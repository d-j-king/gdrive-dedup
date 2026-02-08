"""OAuth2 authentication flow."""

import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..common.constants import SCOPES
from ..common.exceptions import AuthenticationError
from ..common.logging import get_logger

logger = get_logger(__name__)


class OAuthManager:
    """Manages OAuth2 authentication flow and token storage."""

    def __init__(self, token_path: Path, credentials_path: Path) -> None:
        """Initialize OAuth manager.

        Args:
            token_path: Path to store/load access token
            credentials_path: Path to OAuth client credentials
        """
        self.token_path = token_path
        self.credentials_path = credentials_path
        self._creds: Optional[Credentials] = None

    def login(self) -> Credentials:
        """Perform OAuth login flow.

        Returns:
            Valid credentials

        Raises:
            AuthenticationError: If credentials file not found or login fails
        """
        if not self.credentials_path.exists():
            raise AuthenticationError(
                f"Credentials file not found at {self.credentials_path}\n"
                "Please download OAuth credentials from Google Cloud Console:\n"
                "1. Go to https://console.cloud.google.com/apis/credentials\n"
                "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                "3. Download JSON and save to the path above"
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)
            self._save_token(creds)
            self._creds = creds
            logger.info("Successfully authenticated with Google Drive")
            return creds
        except Exception as e:
            raise AuthenticationError(f"Login failed: {e}") from e

    def logout(self) -> None:
        """Remove stored credentials."""
        if self.token_path.exists():
            self.token_path.unlink()
            logger.info("Logged out successfully")
        self._creds = None

    def get_credentials(self) -> Optional[Credentials]:
        """Get valid credentials, refreshing if needed.

        Returns:
            Valid credentials or None if not authenticated
        """
        if self._creds and self._creds.valid:
            return self._creds

        if self.token_path.exists():
            try:
                self._creds = Credentials.from_authorized_user_file(
                    str(self.token_path),
                    SCOPES,
                )

                if self._creds and self._creds.expired and self._creds.refresh_token:
                    logger.info("Refreshing expired token...")
                    self._creds.refresh(Request())
                    self._save_token(self._creds)

                return self._creds if self._creds and self._creds.valid else None
            except Exception as e:
                logger.warning(f"Failed to load/refresh token: {e}")
                return None

        return None

    def is_authenticated(self) -> bool:
        """Check if user is authenticated.

        Returns:
            True if valid credentials exist
        """
        return self.get_credentials() is not None

    def _save_token(self, creds: Credentials) -> None:
        """Save credentials to token file.

        Args:
            creds: Credentials to save
        """
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w") as f:
            json.dump(
                {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                },
                f,
            )
