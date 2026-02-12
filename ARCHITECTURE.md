# GDrive Tools Architecture

This repository contains two complementary tools for Google Drive management:

## Tools Overview

### 1. gdrive-dedup (Duplicate Finder)
**Location**: `/Users/waniel/Documents/vibe-coding/gdrive-dedup/`

**Purpose**: Find and remove exact/near-duplicate files

**Commands**:
- `scan` - Scan Drive for duplicates
- `review` - Interactive duplicate review
- `delete` - Remove duplicates with strategies
- `report` - Export findings
- `auth` - Manage authentication
- `config` - Manage settings

**Dependencies**: Lightweight (~50KB)
- google-api-python-client
- typer, rich, pydantic
- No ML dependencies

**Use Case**: Quick duplicate cleanup, runs on any machine

---

### 2. gdrive-curator (AI-Powered Organizer)
**Location**: `/Users/waniel/Documents/vibe-coding/gdrive-curator/`

**Purpose**: Intelligently organize media by content similarity

**Commands**:
- `analyze` - Extract multi-modal features (faces, poses, scenes)
- `cluster` - Group similar content
- `organize` - Create intelligent folder structures

**Dependencies**: Heavy ML stack (~5GB)
- torch, transformers, mediapipe
- opencv, faiss, scikit-learn
- InsightFace (optional, for face recognition)

**Use Case**: Organize photos/videos by actors, scenes, events

---

## Architecture Principles

### Separation of Concerns
- **Dedup**: Hash-based exact matching (fast, simple)
- **Curator**: ML-based semantic similarity (slow, powerful)

### Shared Components
Both tools share:
- Google Drive authentication
- Configuration management
- File indexing system

### Installation Flexibility
- Install dedup alone for lightweight duplicate cleanup
- Install curator for ML-powered organization
- Or install both for complete Drive management

## Workflow Example

```bash
# Step 1: Clean up duplicates
gdrive-dedup scan
gdrive-dedup delete --keep-oldest

# Step 2: Organize remaining files
gdrive-curator analyze
gdrive-curator cluster
gdrive-curator organize
```

## Project Structure

```
vibe-coding/
├── gdrive-dedup/          # Lightweight dedup tool
│   ├── src/gdrive_dedup/
│   │   ├── cli/           # scan, review, delete, report
│   │   ├── detector/      # Hash-based duplicate detection
│   │   ├── scanner/       # Drive file indexing
│   │   ├── auth/          # OAuth management
│   │   ├── config/        # Settings
│   │   └── common/        # Shared utilities
│   └── pyproject.toml     # Lightweight dependencies
│
└── gdrive-curator/        # ML-powered organizer
    ├── src/gdrive_curator/
    │   ├── cli/           # analyze, cluster, organize
    │   ├── analyzer/      # Feature extraction (faces, poses, scenes)
    │   ├── clustering/    # Similarity-based grouping
    │   ├── organizer/     # Folder structure creation
    │   ├── auth/          # OAuth management (shared pattern)
    │   ├── config/        # Settings (shared pattern)
    │   └── scanner/       # File indexing (shared pattern)
    └── pyproject.toml     # ML dependencies
```

## Future Enhancements

### Planned for gdrive-curator:
- **Hierarchical organization**: Actor folders → Scene subfolders
- **Event detection**: Group by temporal proximity
- **Smart naming**: Auto-generate descriptive folder names
- **Incremental updates**: Process only new files

### Potential shared library:
If code duplication becomes significant, consider:
```
gdrive-common/  # Shared utilities
└── auth, config, scanner base classes
```

## Migration History

- **2026-02-09**: Split ML functionality from gdrive-dedup into gdrive-curator
  - Motivation: Dependency bloat, NumPy 2.x compatibility issues
  - Result: Clean separation, easier maintenance, optional ML install
