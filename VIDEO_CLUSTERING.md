# Video Content Clustering Guide

## Overview

The video clustering feature uses state-of-the-art AI to automatically identify and organize videos with the same actors, scenes, or content. It combines multiple computer vision models to provide robust matching even when faces are obscured or videos are shot from different angles.

## Features

### Multi-Modal Analysis

**Face Recognition (InsightFace)**
- Detects and recognizes faces across videos
- Handles multiple faces per frame
- Creates unique embeddings for each person
- Works with partial faces and different angles

**Body Features (CLIP)**
- Analyzes full body appearance
- Recognizes body shape, build, and proportions
- Detects skin tone and texture
- Identifies tattoos and distinguishing marks
- Understands clothing and accessories

**Pose Detection (MediaPipe)**
- Tracks 33 body keypoints
- Detects body positions and poses
- Helps match videos from same scenes
- Works with full or partial body visibility

**Scene Understanding (CLIP)**
- Analyzes lighting, setting, and environment
- Recognizes props and objects
- Understands context and composition
- Helps identify segments from same recording

### Smart Organization Strategy

**Minimal Disruption Principle**
- Finds the folder with most files in each cluster
- Creates cluster subfolder there (keeps files in place)
- **Duplicates** (not moves) files from other locations
- Preserves your original organization
- Fully reversible (can delete cluster folders)

## Workflow

### 1. Analyze Videos

Extract features from all your videos:

```bash
# Analyze all videos (all features)
gdrive-dedup analyze

# Analyze with specific features only
gdrive-dedup analyze --features face,body

# Faster analysis (fewer frames)
gdrive-dedup analyze --fps 0.5 --max-frames 10

# Test on a few videos first
gdrive-dedup analyze --limit 10
```

**Performance:**
- Apple Silicon (M1/M2/M3): ~10-30 videos/minute
- Automatically uses GPU acceleration if available
- Processes frames on-the-fly (doesn't store videos locally)
- Results stored in `~/.gdrive-dedup/embeddings.db`

**What it does:**
1. Downloads video (streaming, not saved)
2. Extracts keyframes (1 per second by default)
3. Runs face detection on each frame
4. Computes body appearance embeddings
5. Detects pose keypoints
6. Analyzes scene/context
7. Stores all features in database

### 2. Find Clusters

Group similar videos together:

```bash
# Basic clustering (70% similarity threshold)
gdrive-dedup cluster

# Stricter matching (only very similar videos)
gdrive-dedup cluster --min-similarity 0.85

# More lenient (find loosely related videos)
gdrive-dedup cluster --min-similarity 0.60

# Adjust feature weights
gdrive-dedup cluster \
  --face-weight 0.5 \
  --body-weight 0.3 \
  --pose-weight 0.1 \
  --scene-weight 0.1

# Save clusters to file for later
gdrive-dedup cluster --output clusters.json
```

**Similarity Weights (default):**
- Face: 40% - Strong signal for identity
- Body: 25% - Important for matching
- Pose: 20% - Contextual information
- Scene: 15% - Background/setting

**Algorithms:**
- `dbscan` (default): Finds dense clusters, handles noise
- `agglomerative`: Hierarchical clustering, good for nested groups

### 3. Organize into Folders

Create organized cluster folders:

```bash
# Preview what would happen (dry run)
gdrive-dedup organize --dry-run

# Actually organize (with confirmation)
gdrive-dedup organize

# Skip confirmation
gdrive-dedup organize --yes

# Use existing clusters file
gdrive-dedup organize --clusters clusters.json

# Custom cluster names
gdrive-dedup organize --prefix "Scene"
# Creates: Scene_001, Scene_002, etc.

# Only organize large clusters
gdrive-dedup organize --min-size 5
```

**What it does:**

For each cluster:
1. Counts how many files are in each folder
2. Chooses folder with **most files** as primary location
3. Creates cluster subfolder there (e.g., `/Videos/Summer2019/Actor_042/`)
4. Keeps files in primary folder in place (adds shortcuts to cluster)
5. **Copies** (duplicates) files from other folders into cluster
6. Original files stay untouched in their original locations

**Example:**

Before:
```
/Videos/Summer2019/        ← 15 videos of Actor A
/Videos/Random/            ← 3 videos of Actor A
/Backup/OldStuff/          ← 2 videos of Actor A
```

After:
```
/Videos/Summer2019/        ← 15 videos (unchanged)
  └─ Actor_042/            ← NEW: All 20 videos together!
/Videos/Random/            ← 3 videos (unchanged, also in cluster)
/Backup/OldStuff/          ← 2 videos (unchanged, also in cluster)
```

**Result:** Curated collection in `Actor_042/` folder without disrupting original organization!

## Advanced Usage

### Find Similar Videos to a Specific Video

```bash
# Find videos similar to a specific file
gdrive-dedup cluster find-similar <FILE_ID>

# More results
gdrive-dedup cluster find-similar <FILE_ID> --limit 20

# Lower threshold
gdrive-dedup cluster find-similar <FILE_ID> --min-similarity 0.5
```

### Reanalyze Specific Videos

```bash
# Reanalyze all videos (even if already analyzed)
gdrive-dedup analyze --reanalyze

# Analyze only new videos
gdrive-dedup analyze --skip-analyzed
```

### Performance Tuning

**For faster analysis (less accurate):**
```bash
gdrive-dedup analyze --fps 0.5 --max-frames 5
```

**For better accuracy (slower):**
```bash
gdrive-dedup analyze --fps 2.0 --scene-detection
```

**GPU Acceleration:**
- Automatically detected on Apple Silicon (MPS)
- NVIDIA GPUs supported (CUDA)
- Falls back to CPU if no GPU available

## File Locations

- **Embeddings Database:** `~/.gdrive-dedup/embeddings.db`
  - Stores all extracted features
  - Can be deleted to start fresh
  - ~1-5 MB per analyzed video

- **Clusters Output:** `clusters.json` (if using --output)
  - Human-readable JSON format
  - Can be edited manually if needed
  - Reusable with `organize --clusters`

## Tips & Best Practices

1. **Start Small:** Test with `--limit 10` first to verify it works
2. **Adjust Weights:** If faces are often obscured, increase `--body-weight`
3. **Tune Similarity:** Start with 0.7, adjust based on results
4. **Dry Run First:** Always use `--dry-run` before organizing
5. **Check Disk Space:** Organizing duplicates files, so ensure sufficient space
6. **Reversible:** Can delete cluster folders without losing original files

## Troubleshooting

**"No analyzed videos found"**
- Run `gdrive-dedup analyze` first

**Analysis is slow**
- Reduce `--fps` or add `--max-frames 10`
- Limit video types with `--mime-types`

**Not finding clusters**
- Lower `--min-similarity` threshold
- Check if videos were analyzed successfully
- Try different feature weights

**Out of memory**
- Analyze in batches with `--limit`
- Reduce `--max-frames`

**GPU not detected on Mac**
- Ensure PyTorch with MPS support is installed
- Check with: `python -c "import torch; print(torch.backends.mps.is_available())"`

## Example Workflows

### Basic: Organize by Actor

```bash
# 1. Analyze all videos
gdrive-dedup analyze

# 2. Find clusters
gdrive-dedup cluster --min-similarity 0.75

# 3. Preview organization
gdrive-dedup organize --dry-run

# 4. Execute
gdrive-dedup organize --yes
```

### Advanced: Scene-Based Organization

```bash
# 1. Analyze with emphasis on scenes
gdrive-dedup analyze --features scene,body,pose

# 2. Cluster by scene similarity
gdrive-dedup cluster \
  --face-weight 0.1 \
  --body-weight 0.2 \
  --pose-weight 0.2 \
  --scene-weight 0.5

# 3. Save clusters
gdrive-dedup cluster --output scenes.json

# 4. Organize
gdrive-dedup organize --clusters scenes.json --prefix "Scene"
```

### Testing: Small Sample

```bash
# Test on 5 videos
gdrive-dedup analyze --limit 5 --fps 1 --max-frames 5

# Quick cluster
gdrive-dedup cluster --min-similarity 0.6

# See what would happen
gdrive-dedup organize --dry-run
```

## Technical Details

**Feature Dimensions:**
- Face embeddings: 512-dimensional vectors
- Body embeddings: 512-dimensional (CLIP)
- Pose keypoints: 132-dimensional (33 points × 4 coords)
- Scene embeddings: 768-dimensional (CLIP-Large)

**Similarity Computation:**
- Cosine similarity for embeddings
- Maximum similarity across all face pairs
- Weighted combination of all modalities
- Normalized to 0-1 range

**Storage:**
- SQLite database with efficient indexing
- Embeddings stored as binary blobs
- Supports thousands of videos
- Fast retrieval and querying
