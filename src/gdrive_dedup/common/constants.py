"""Constants used throughout the application."""

# OAuth2 scopes
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Google Workspace MIME types (no MD5, should be excluded)
WORKSPACE_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
    "application/vnd.google-apps.site",
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
}

# API limits
PAGE_SIZE = 1000
BATCH_SIZE = 100
DEFAULT_RATE_LIMIT = 10  # requests per second

# File index
INDEX_DB_NAME = "file_index.db"
CHECKPOINT_FILE = "scan_checkpoint.json"

# Token storage
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"
