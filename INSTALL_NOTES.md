# Installation Notes

## Quick Install

The core video analysis features work without face recognition:

```bash
pip install -e .
```

This gives you:
- ✅ Body appearance matching (CLIP)
- ✅ Pose detection (MediaPipe)
- ✅ Scene understanding (CLIP)
- ❌ Face recognition (requires additional setup)

## Face Recognition (Optional)

Face recognition requires InsightFace, which needs compilation. If you want face features:

### Option 1: Try automatic installation

```bash
pip install insightface
```

### Option 2: Manual installation (if Option 1 fails)

1. Install system dependencies (macOS):
```bash
# Install Xcode Command Line Tools if not already installed
xcode-select --install

# Install build tools
brew install cmake
```

2. Install InsightFace:
```bash
pip install cython
pip install insightface
```

### Option 3: Skip face recognition

The tool works great without face recognition! Body features + pose + scene are often sufficient for clustering adult content.

Just use the analyze command without `face` in features:

```bash
gdrive-dedup analyze --features body,pose,scene
```

## Verifying Installation

Test if everything works:

```bash
# Should work without errors
gdrive-dedup --help

# Test analyze command
gdrive-dedup analyze --help
```

## Troubleshooting

**"No module named 'insightface'"** when using `--features face`
- This is expected if you haven't installed InsightFace
- Either install it (see above) or remove `face` from your features list

**Import errors for other libraries**
- Make sure you're using Python 3.10+
- Try: `pip install --upgrade pip` then reinstall

**Apple Silicon (M1/M2/M3) specific**
- PyTorch should automatically detect MPS (Metal Performance Shaders)
- Verify with: `python -c "import torch; print(torch.backends.mps.is_available())"`
- Should print `True` on Apple Silicon Macs

## Performance Notes

**Without face recognition:**
- ~15-40 videos/minute on Apple Silicon
- Uses GPU acceleration for CLIP models
- Lower memory usage

**With face recognition:**
- ~10-30 videos/minute
- More accurate actor matching
- Higher memory usage (2-3 GB)
