"""Authentication commands."""

import typer

from ..auth.oauth import OAuthManager
from ..common.exceptions import AuthenticationError
from ..config.settings import get_settings
from .formatters import print_error, print_info, print_success, print_panel

auth_app = typer.Typer(help="Manage Google Drive authentication")


@auth_app.command("login")
def login() -> None:
    """Authenticate with Google Drive."""
    settings = get_settings()
    oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)

    try:
        if oauth_manager.is_authenticated():
            print_info("Already authenticated. Logging out first...")
            oauth_manager.logout()

        print_info("Starting authentication flow...")
        print_info("A browser window will open for you to authorize the application.")

        oauth_manager.login()

        print_success("Successfully authenticated with Google Drive!")
        print_info(f"Token saved to: {settings.token_path}")

    except AuthenticationError as e:
        print_error(f"Authentication failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(1)


@auth_app.command("logout")
def logout() -> None:
    """Remove stored credentials."""
    settings = get_settings()
    oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)

    try:
        if not oauth_manager.is_authenticated():
            print_warning("Not currently authenticated.")
            return

        oauth_manager.logout()
        print_success("Successfully logged out.")

    except Exception as e:
        print_error(f"Logout failed: {e}")
        raise typer.Exit(1)


@auth_app.command("status")
def status() -> None:
    """Show authentication status."""
    settings = get_settings()
    oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)

    try:
        if oauth_manager.is_authenticated():
            print_success("Authenticated with Google Drive")
            print_info(f"Token location: {settings.token_path}")

            creds = oauth_manager.get_credentials()
            if creds:
                scopes_text = "\n".join(f"  • {scope}" for scope in (creds.scopes or []))
                print_panel(
                    "Granted Scopes",
                    scopes_text,
                    style="green",
                )
        else:
            print_warning("Not authenticated")
            print_info("Run 'gdrive-dedup auth login' to authenticate.")

    except Exception as e:
        print_error(f"Failed to check status: {e}")
        raise typer.Exit(1)


from .formatters import print_warning
