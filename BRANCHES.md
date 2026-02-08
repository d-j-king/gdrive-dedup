# Branch Guide

## Quick Reference

```bash
# Use stable version (recommended)
git checkout stable

# Try experimental AI features
git checkout video-clustering-experimental

# Return to latest development
git checkout main
```

## Branch Overview

### 🟢 `stable` (v1.0-stable)

**Production-Ready Features:**
- ✅ Full duplicate detection (size → MD5 → optional byte comparison)
- ✅ Intelligent name merging
  - Extracts dates, descriptive text
  - Discards junk (IMG_1234, "copy of", etc.)
  - Combines all meaningful information
- ✅ Smart deletion strategies
  - newest, oldest, shortest, longest, deepest, path
  - **merge-names** - Combines filenames intelligently
- ✅ Same-folder-only mode (keep cross-folder duplicates)
- ✅ Safe trash-only operations (30-day recovery)
- ✅ Dry-run mode
- ✅ Interactive review

**Use this for:**
- Production deduplication tasks
- Reliable, well-tested features
- No heavy dependencies (no ML libraries)
- Fast installation

**Example:**
```bash
git checkout stable
pip install -e .
gdrive-dedup scan
gdrive-dedup delete --strategy merge-names --same-folder-only --dry-run
```

---

### 🔬 `video-clustering-experimental`

**Experimental AI Features:**
- 🧪 Multi-modal video analysis
  - Face recognition (InsightFace - optional)
  - Body appearance (CLIP)
  - Pose detection (MediaPipe)
  - Scene understanding (CLIP)
- 🧪 Smart clustering algorithms
  - DBSCAN and Agglomerative clustering
  - Weighted similarity scoring
  - Vector search with FAISS
- 🧪 Intelligent organization
  - Creates clusters in primary folder location
  - Duplicates files (doesn't move them)
  - Minimal disruption strategy

**Dependencies:**
- Large ML libraries (~500 MB download)
- PyTorch, transformers, MediaPipe
- Optional: InsightFace (may require compilation)

**Use this for:**
- Adult content organization by actor/scene
- Experimental features
- Testing AI clustering
- If you have disk space and patience for installation

**Example:**
```bash
git checkout video-clustering-experimental
pip install -e .  # This will take a while!

# Analyze videos (without face recognition)
gdrive-dedup analyze --features body,pose,scene --limit 10

# Find clusters
gdrive-dedup cluster --min-similarity 0.7

# Organize (dry run first!)
gdrive-dedup organize --dry-run
```

**Known Issues:**
- InsightFace may fail to install (requires C++ compilation)
- Large dependency footprint
- Some features untested at scale

---

### 🚧 `main` (development)

**Latest Development:**
- Contains latest experimental features
- May have uncommitted changes
- Includes both stable and experimental code

**Use this for:**
- Contributing to development
- Testing unreleased features
- Active development work

---

## Version History

### v1.0-stable (Commit: 3d47fa6)

**Major Features:**
1. **Initial Implementation** (38310f2)
   - OAuth authentication
   - Drive scanning with pagination
   - SQLite file index
   - Multi-pass duplicate detection
   - Basic deletion strategies

2. **Comprehensive Usage Guide** (12b7709)
   - CLI documentation
   - Safety guidelines
   - Example workflows

3. **Project Reorganization** (f3d209f)
   - Moved to dedicated subdirectory
   - Clean project structure

4. **API Query Fixes** (580ddd0)
   - Fixed MIME type filtering
   - Client-side size filtering
   - Improved compatibility

5. **Name Merging + Smart Strategies** (3d47fa6)
   - Intelligent filename parsing
   - Date/text extraction
   - Same-folder-only deletion mode
   - Deepest path strategy

### Experimental Features (455b7f6, 8a74a90)

6. **Video Clustering** (455b7f6)
   - Multi-modal AI analysis
   - Feature extraction pipeline
   - Clustering algorithms
   - Smart organization strategy

7. **Installation Improvements** (8a74a90)
   - Made InsightFace optional
   - Added installation guide
   - Improved dependency management

---

## Switching Between Versions

### To use stable version:

```bash
git checkout stable
pip uninstall gdrive-dedup -y
pip install -e .
```

**Benefits:**
- Fast installation (~30 seconds)
- Small dependency footprint
- Well-tested features
- No ML libraries needed

### To try experimental features:

```bash
git checkout video-clustering-experimental
pip uninstall gdrive-dedup -y
pip install -e .  # Takes 5-10 minutes, downloads ~500 MB
```

**Benefits:**
- AI-powered video clustering
- Advanced content organization
- Cutting-edge features

**Caveats:**
- Large download
- May have installation issues
- Experimental/untested at scale

### To return to development:

```bash
git checkout main
```

---

## Recommendations

**For most users:** Use `stable` branch
- Reliable, fast, production-ready
- All core deduplication features
- Intelligent name merging
- Safe and well-tested

**For advanced users:** Try `video-clustering-experimental`
- Only if you need AI-powered video organization
- Have patience for installation
- Want cutting-edge features
- Can troubleshoot dependency issues

**For contributors:** Use `main` branch
- Active development
- Latest changes
- May be unstable

---

## Support

- **Stable branch issues:** Should work reliably, file bug reports
- **Experimental branch issues:** Expected, may need troubleshooting
- **Installation help:** See `INSTALL_NOTES.md`
- **Usage help:** See `VIDEO_CLUSTERING.md` (experimental) or main README
