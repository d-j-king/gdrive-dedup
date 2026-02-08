# gdrive-dedup

A CLI tool to find and remove duplicate files in Google Drive.

## Features

- **Multi-pass duplicate detection**: Size → MD5 → optional byte comparison
- **Safe deletion**: Only trashes files, never hard-deletes
- **Interactive review**: Browse and select duplicates before removing
- **Batch operations**: Multiple deletion strategies (keep newest/oldest/path)
- **Progress tracking**: Resume interrupted scans
- **Export reports**: CSV/JSON output for audit trails

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd gdrive-dedup

# Install with pip (development mode)
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

## Setup

1. **Create OAuth credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Create a new project or select existing
   - Enable Google Drive API
   - Create OAuth 2.0 Client ID (Desktop app)
   - Download the JSON credentials

2. **Save credentials**:
   ```bash
   # Default location
   mkdir -p ~/.gdrive-dedup
   cp ~/Downloads/credentials.json ~/.gdrive-dedup/credentials.json
   ```

3. **Authenticate**:
   ```bash
   gdrive-dedup auth login
   ```

## Usage

```bash
# Authenticate
gdrive-dedup auth login
gdrive-dedup auth status

# Scan for duplicates
gdrive-dedup scan

# Scan specific folder
gdrive-dedup scan --folder FOLDER_ID

# Review duplicates interactively
gdrive-dedup review

# Delete duplicates (keep newest)
gdrive-dedup delete --strategy newest --dry-run
gdrive-dedup delete --strategy newest

# Export report
gdrive-dedup report --format csv -o duplicates.csv

# Configuration
gdrive-dedup config show
gdrive-dedup config set rate_limit 5
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy src/
```

## License

MIT
