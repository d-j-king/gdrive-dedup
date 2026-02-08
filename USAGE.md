# Google Drive Dedup - Usage Guide

## Quick Start

### 1. Installation

```bash
# Clone the repository
cd gdrive-dedup

# Install the package
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

### 2. Setup Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Select "Desktop app" as the application type
   - Download the JSON file
5. Save the credentials:
   ```bash
   mkdir -p ~/.gdrive-dedup
   cp ~/Downloads/client_secret_*.json ~/.gdrive-dedup/credentials.json
   ```

### 3. Authenticate

```bash
gdrive-dedup auth login
```

This will:
- Open your browser
- Ask you to sign in to Google
- Request permission to access your Drive
- Save the access token locally

### 4. Scan for Duplicates

```bash
# Scan entire drive
gdrive-dedup scan

# Scan specific folder
gdrive-dedup scan --folder FOLDER_ID

# Scan with minimum file size (e.g., 1MB)
gdrive-dedup scan --min-size 1048576

# Dry run (see what would be scanned)
gdrive-dedup scan --dry-run
```

### 5. Review Duplicates

```bash
# Review all duplicate groups
gdrive-dedup review

# Review specific group
gdrive-dedup review --group 1

# Sort by different criteria
gdrive-dedup review --sort size    # by file size
gdrive-dedup review --sort count   # by number of duplicates
gdrive-dedup review --sort wasted  # by wasted space (default)
```

### 6. Delete Duplicates

**IMPORTANT**: Files are moved to trash, not permanently deleted. You can restore them from Google Drive trash within 30 days.

```bash
# Keep newest file, trash older copies (dry run first!)
gdrive-dedup delete --strategy newest --dry-run
gdrive-dedup delete --strategy newest

# Keep oldest file
gdrive-dedup delete --strategy oldest

# Keep file with shortest path
gdrive-dedup delete --strategy shortest

# Keep file with longest path
gdrive-dedup delete --strategy longest

# Keep files matching a path pattern
gdrive-dedup delete --strategy path --keep-path "/Important/*"

# Skip confirmation prompt
gdrive-dedup delete --strategy newest --yes
```

### 7. Export Reports

```bash
# Export to CSV
gdrive-dedup report --format csv --output duplicates.csv

# Export to JSON
gdrive-dedup report --format json --output duplicates.json
```

## Advanced Usage

### Configuration

View current configuration:
```bash
gdrive-dedup config show
```

Modify settings (in-memory only):
```bash
gdrive-dedup config set rate_limit 5.0
gdrive-dedup config set log_level DEBUG
```

Use environment variables for persistent settings:
```bash
export GDRIVE_DEDUP_RATE_LIMIT=5.0
export GDRIVE_DEDUP_LOG_LEVEL=DEBUG
gdrive-dedup scan
```

Or create a `.env` file (see `.env.example`).

### Resume Interrupted Scans

If a scan is interrupted, resume it:
```bash
gdrive-dedup scan --resume
```

### Scan Only Your Files

By default, only files you own are scanned. To scan all files (including shared):
```bash
gdrive-dedup scan --all-files
```

### Verbose Logging

Enable detailed debug output:
```bash
gdrive-dedup --verbose scan
```

## Workflow Examples

### Example 1: Clean Up Photos

```bash
# Scan for duplicate photos (>100KB)
gdrive-dedup scan --min-size 102400

# Review the duplicates
gdrive-dedup review --sort wasted

# Keep newest copies, trash older ones (preview first)
gdrive-dedup delete --strategy newest --dry-run

# Actually delete
gdrive-dedup delete --strategy newest

# Export report for records
gdrive-dedup report --format csv --output photo-cleanup-$(date +%Y%m%d).csv
```

### Example 2: Preserve Files in Important Folder

```bash
# Scan entire drive
gdrive-dedup scan

# Delete duplicates but keep anything in "Important" folder
gdrive-dedup delete --strategy path --keep-path "/Important/*" --dry-run
gdrive-dedup delete --strategy path --keep-path "/Important/*"
```

### Example 3: Large Drive Cleanup

```bash
# Scan only large files (>10MB)
gdrive-dedup scan --min-size 10485760

# Review biggest space wasters
gdrive-dedup review --sort wasted

# Export full report before deletion
gdrive-dedup report --format json --output pre-cleanup.json

# Delete keeping newest
gdrive-dedup delete --strategy newest --yes
```

## Safety Features

1. **Trash-Only Operations**: Files are never permanently deleted, only moved to trash
2. **Dry Run Mode**: Preview operations with `--dry-run` before executing
3. **Confirmation Prompts**: Required by default (skip with `--yes`)
4. **Scan Resume**: Interrupted scans can be resumed with checkpoints
5. **Audit Reports**: Export CSV/JSON reports before making changes
6. **Rate Limiting**: Automatic API throttling to respect Google's limits
7. **Retry Logic**: Exponential backoff for transient API errors

## Troubleshooting

### Authentication Issues

```bash
# Check authentication status
gdrive-dedup auth status

# Re-authenticate
gdrive-dedup auth logout
gdrive-dedup auth login
```

### Rate Limit Errors

Reduce the rate limit:
```bash
gdrive-dedup config set rate_limit 5.0
```

### Large Drives

For drives with 100K+ files:
- Use `--min-size` to filter small files
- Enable resume with `--resume` if interrupted
- Monitor the SQLite database at `~/.gdrive-dedup/file_index.db`

### No Duplicates Found

Google Workspace files (Docs, Sheets, Slides) are automatically excluded because they don't have MD5 checksums. Only regular files are scanned.

## Data Storage

All data is stored in `~/.gdrive-dedup/`:
- `credentials.json` - OAuth client credentials
- `token.json` - Access token
- `file_index.db` - SQLite database of scanned files
- `scan_checkpoint.json` - Resume checkpoint

To reset everything:
```bash
rm -rf ~/.gdrive-dedup
```

## Privacy & Security

- OAuth credentials are stored locally only
- Access token has standard Google Drive API scopes
- No data is sent to third parties
- File metadata is stored in local SQLite database
- You can revoke access anytime at https://myaccount.google.com/permissions
