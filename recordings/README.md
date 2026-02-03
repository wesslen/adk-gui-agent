# Video Recordings Directory

This directory stores video recordings of browser automation sessions.

## File Format

Videos are saved as:
```
session_<session_id>_<timestamp>.webm
```

Example: `session_abc123def_20260201_143022.webm`

## Configuration

Video recording is controlled by environment variables in `.env`:

```bash
VIDEO_RECORDING_ENABLED=false        # Enable/disable recording
VIDEO_RECORDING_DIR=./recordings     # This directory
VIDEO_SIZE=1280x720                  # Video dimensions
VIDEO_KEEP_ON_SUCCESS=false          # Keep videos after successful runs
VIDEO_RETENTION_DAYS=7               # Auto-cleanup after N days
```

## Management

### CLI Commands (Interactive Mode)

```bash
/video on       # Enable recording for next task
/video off      # Disable recording for next task
/video stats    # Show recording statistics
/video clean    # Clean up old recordings
```

### Makefile Commands

```bash
make video-stats      # Show statistics
make video-clean      # Delete old recordings
make video-convert    # Convert WebM to MP4
```

## Storage

- **WebM format:** 1-2 MB per minute at 1280x720
- **Automatic cleanup:** Files older than `VIDEO_RETENTION_DAYS` are deleted
- **Smart deletion:** Successful runs auto-deleted if `VIDEO_KEEP_ON_SUCCESS=false`

## Conversion to MP4

To convert recordings to MP4 for better compatibility:

```bash
# Convert all WebM files
make video-convert

# Or manually convert a specific file
ffmpeg -i session_abc123_20260201_143022.webm \
       -c:v libx264 -preset fast -crf 23 \
       -c:a aac -b:a 128k \
       session_abc123_20260201_143022.mp4
```

## Use Cases

- **Debugging:** Visual inspection of failed automation runs
- **Demos:** Share with business partners and stakeholders
- **Development:** Verify form filling behavior
- **Compliance:** Audit trail of automation actions

## Git Ignore

This directory is tracked in Git, but video files are ignored:
- `*.webm` - Ignored
- `*.mp4` - Ignored
- `.gitkeep` - Tracked (preserves empty directory)
- `.gitignore` - Tracked (ignore rules)

---

For more information, see `VIDEO_RECORDING_PLAN.md` in the project root.
