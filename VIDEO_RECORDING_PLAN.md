# Video Recording Implementation Plan

> **Goal:** Add video recording capability to adk-gui-agent for debugging and demos when running in GCP Cloud Shell.

**Last Updated:** 2026-02-01

---

## Executive Summary

This document outlines a comprehensive plan to add video recording capabilities to the browser automation agent. The solution uses **Playwright's built-in video recording** combined with **FFmpeg** for video processing, all running in the existing Docker container environment.

**Key Benefits:**
- 🎥 Record full browser sessions for debugging
- 📊 Share videos with business partners for demos
- 🔍 Debug visual issues that logs can't capture
- 💾 Minimal storage overhead with on-demand recording

---

## Architecture Overview

### Option 1: Playwright Native Video Recording (RECOMMENDED)

**Approach:** Use Playwright's built-in video recording API, which is the most reliable and officially supported method.

```
┌─────────────────────────────────────────┐
│   Python Agent (gui_agent.cli)          │
│   - Passes video config to MCP          │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│   Playwright MCP Server (Docker)        │
│   - Launches browser with video={}      │
│   - Records to /recordings volume       │
│   - Returns video path on completion    │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│   Shared Volume: ./recordings           │
│   - Accessible from host & container    │
│   - Videos: session_<id>_<timestamp>.webm │
└─────────────────────────────────────────┘
```

**Advantages:**
- ✅ Built into Playwright, no extra dependencies
- ✅ Automatically synced with browser lifecycle
- ✅ Works perfectly in headless mode
- ✅ Minimal configuration required
- ✅ No performance overhead when disabled

**Limitations:**
- ⚠️ Requires Playwright MCP to support video context parameter
- ⚠️ Output format is WebM only (widely supported)

---

### Option 2: FFmpeg with Xvfb (Fallback)

**Approach:** Use virtual framebuffer (Xvfb) + FFmpeg to record the virtual display.

```
┌─────────────────────────────────────────┐
│   Playwright MCP Container              │
│   ├── Xvfb (virtual display :99)        │
│   ├── FFmpeg (screen capture)           │
│   └── Chrome (renders to :99)           │
└─────────────────────────────────────────┘
```

**Advantages:**
- ✅ Works regardless of Playwright MCP API support
- ✅ Can capture anything on the display
- ✅ Highly flexible (can add overlays, timestamps, etc.)

**Limitations:**
- ⚠️ More complex setup
- ⚠️ Higher resource usage (CPU/memory)
- ⚠️ Requires manual start/stop coordination
- ⚠️ Larger file sizes

---

## Recommended Implementation: Playwright Native

### Phase 1: Docker Configuration

#### 1.1 Update `docker-compose.yml`

Add a shared volume for recordings and install FFmpeg for video processing:

```yaml
services:
  playwright-mcp:
    image: mcr.microsoft.com/playwright:v1.49.0-noble
    container_name: gui-agent-playwright
    working_dir: /app
    ports:
      - "8931:8931"
    environment:
      - DISPLAY=:99
      - PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
      - PLAYWRIGHT_CHROMIUM_ARGS=--no-sandbox --disable-setuid-sandbox
      # Video recording configuration
      - VIDEO_RECORDING_ENABLED=false  # Default: off
      - VIDEO_RECORDING_DIR=/recordings
      - VIDEO_SIZE=1280x720
    volumes:
      - ./playwright-mcp:/app
      - playwright_cache:/root/.cache
      - ./recordings:/recordings  # NEW: Shared recordings volume
    command: >
      bash -c "
        # Install FFmpeg for video processing
        apt-get update && apt-get install -y ffmpeg &&
        npm install -g @playwright/mcp@latest &&
        npx playwright install chrome --with-deps &&
        # Create recordings directory
        mkdir -p /recordings &&
        npx @playwright/mcp@latest --port 8931 --host 0.0.0.0 --headless --no-sandbox
      "
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8931/sse"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped
    depends_on:
      - phoenix

volumes:
  phoenix_data:
  playwright_cache:
  # No need to declare recordings - it's a bind mount
```

**Key Changes:**
1. Added `./recordings:/recordings` volume mount
2. Added environment variables for video configuration
3. Added FFmpeg installation (for video processing/conversion)
4. Create `/recordings` directory on container startup

---

### Phase 2: Environment Configuration

#### 2.1 Update `.env.example`

Add video recording configuration:

```bash
# =============================================================================
# Video Recording (for debugging and demos)
# =============================================================================
# Enable video recording for browser sessions
VIDEO_RECORDING_ENABLED=false

# Directory to save recordings (relative to project root)
VIDEO_RECORDING_DIR=./recordings

# Video dimensions (width x height)
VIDEO_SIZE=1280x720

# Video quality (1-100, higher = better quality but larger files)
VIDEO_QUALITY=50

# Keep recordings after task completion (true/false)
VIDEO_KEEP_ON_SUCCESS=false

# Max video retention days (0 = keep forever)
VIDEO_RETENTION_DAYS=7
```

---

### Phase 3: Python Agent Code

#### 3.1 Update `src/gui_agent/config.py`

Add video configuration settings:

```python
"""Configuration management for GUI agent."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, Enum):
    """Authentication mode for Google Gemini."""

    API_KEY = "api_key"
    VERTEX_AI = "vertex_ai"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ... existing settings ...

    # Video Recording
    video_recording_enabled: bool = Field(
        default=False,
        description="Enable video recording for browser sessions"
    )
    video_recording_dir: str = Field(
        default="./recordings",
        description="Directory to save recordings"
    )
    video_size: str = Field(
        default="1280x720",
        description="Video dimensions (widthxheight)"
    )
    video_quality: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Video quality (1-100)"
    )
    video_keep_on_success: bool = Field(
        default=False,
        description="Keep recordings after successful completion"
    )
    video_retention_days: int = Field(
        default=7,
        ge=0,
        description="Max days to retain recordings (0=forever)"
    )

    @property
    def video_recording_path(self) -> Path:
        """Get the absolute path to the recordings directory."""
        return Path(self.video_recording_dir).resolve()

    def get_video_config(self) -> dict | None:
        """Get Playwright video configuration.

        Returns:
            Video config dict for Playwright, or None if disabled.
        """
        if not self.video_recording_enabled:
            return None

        width, height = self.video_size.split("x")

        return {
            "dir": "/recordings",  # Container path
            "size": {"width": int(width), "height": int(height)},
        }
```

#### 3.2 Create `src/gui_agent/video.py`

New module for video management utilities:

```python
"""Video recording utilities for browser automation."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui_agent.config import Settings

logger = logging.getLogger(__name__)


class VideoManager:
    """Manages video recordings for browser sessions."""

    def __init__(self, settings: Settings) -> None:
        """Initialize video manager.

        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.recordings_dir = settings.video_recording_path
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def get_video_path(self, session_id: str) -> Path:
        """Get the path for a session's video recording.

        Args:
            session_id: Unique session identifier.

        Returns:
            Path to the video file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session_id}_{timestamp}.webm"
        return self.recordings_dir / filename

    def cleanup_old_recordings(self) -> int:
        """Remove recordings older than retention period.

        Returns:
            Number of files deleted.
        """
        if self.settings.video_retention_days == 0:
            logger.info("Video retention is disabled (retention_days=0)")
            return 0

        cutoff_date = datetime.now() - timedelta(
            days=self.settings.video_retention_days
        )
        deleted_count = 0

        for video_file in self.recordings_dir.glob("session_*.webm"):
            if video_file.stat().st_mtime < cutoff_date.timestamp():
                try:
                    video_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old recording: {video_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {video_file.name}: {e}")

        logger.info(f"Cleaned up {deleted_count} old recordings")
        return deleted_count

    def delete_recording(self, video_path: Path) -> bool:
        """Delete a specific recording.

        Args:
            video_path: Path to the video file.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            if video_path.exists():
                video_path.unlink()
                logger.info(f"Deleted recording: {video_path.name}")
                return True
        except Exception as e:
            logger.warning(f"Failed to delete {video_path.name}: {e}")
        return False

    def get_recording_stats(self) -> dict:
        """Get statistics about recordings.

        Returns:
            Dict with count, total size, oldest, and newest recordings.
        """
        recordings = list(self.recordings_dir.glob("session_*.webm"))

        if not recordings:
            return {
                "count": 0,
                "total_size_mb": 0.0,
                "oldest": None,
                "newest": None,
            }

        total_size = sum(f.stat().st_size for f in recordings)
        recordings_by_time = sorted(recordings, key=lambda f: f.stat().st_mtime)

        return {
            "count": len(recordings),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest": recordings_by_time[0].name,
            "newest": recordings_by_time[-1].name,
        }

    def convert_to_mp4(self, webm_path: Path) -> Path | None:
        """Convert WebM recording to MP4 for better compatibility.

        Args:
            webm_path: Path to the WebM file.

        Returns:
            Path to the MP4 file, or None if conversion failed.
        """
        mp4_path = webm_path.with_suffix(".mp4")

        try:
            import subprocess

            subprocess.run(
                [
                    "ffmpeg",
                    "-i", str(webm_path),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    str(mp4_path),
                ],
                check=True,
                capture_output=True,
            )
            logger.info(f"Converted {webm_path.name} to MP4")
            return mp4_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
            return None
        except FileNotFoundError:
            logger.error("FFmpeg not found. Install it to enable MP4 conversion.")
            return None
```

#### 3.3 Update `src/gui_agent/agent.py`

Integrate video recording into the agent workflow:

```python
# Add to imports
from gui_agent.video import VideoManager

async def run_agent_task(
    task: str,
    user_id: str = "default_user",
    session_id: str | None = None,
    enable_video: bool | None = None,  # NEW: Optional override
) -> str:
    """Run the agent on a specific task.

    Args:
        task: The task description (e.g., "Fill the contact form with...")
        user_id: User identifier for session tracking.
        session_id: Optional session ID for conversation continuity.
        enable_video: Override video recording setting for this task.

    Returns:
        The agent's final response.
    """
    settings = get_settings()
    settings.configure_environment()

    # Determine if video recording is enabled
    video_enabled = (
        enable_video
        if enable_video is not None
        else settings.video_recording_enabled
    )

    # Initialize video manager
    video_manager = VideoManager(settings) if video_enabled else None
    video_path = None

    # Create session service
    session_service = InMemorySessionService()

    # Generate session ID if not provided
    if session_id is None:
        import uuid
        session_id = str(uuid.uuid4())

    # Get video path for this session
    if video_manager:
        video_path = video_manager.get_video_path(session_id)
        logger.info(f"Video recording enabled: {video_path}")
        # NOTE: Actual video configuration would need to be passed to
        # Playwright MCP through context creation or tool parameters.
        # This depends on @playwright/mcp API capabilities.

    # Create session (async in newer ADK versions)
    await session_service.create_session(
        app_name="gui-agent",
        user_id=user_id,
        session_id=session_id,
    )

    # Create agent and runner
    agent = create_form_filling_agent()
    runner = Runner(
        agent=agent,
        app_name="gui-agent",
        session_service=session_service,
    )

    logger.info(f"Starting task: {task[:100]}...")

    # Run with tracing
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=task)]
    )

    task_successful = False
    with TracingContext(settings):
        final_response = ""
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                # Extract text from various event types
                if hasattr(event, "content") and event.content:
                    if hasattr(event.content, "parts"):
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                final_response = part.text
                    elif hasattr(event.content, "text"):
                        final_response = event.content.text

            task_successful = True
        finally:
            # Clean up video if task succeeded and keep_on_success=False
            if video_manager and video_path:
                if task_successful and not settings.video_keep_on_success:
                    video_manager.delete_recording(video_path)
                    logger.info("Task succeeded, video deleted (keep_on_success=False)")
                elif video_path.exists():
                    logger.info(f"Video saved: {video_path}")

    logger.info(f"Task completed. Response length: {len(final_response)}")
    return final_response
```

#### 3.4 Update `src/gui_agent/cli.py`

Add CLI options for video recording:

```python
"""Interactive CLI for the GUI automation agent."""

import logging
import sys
from pathlib import Path

from gui_agent.agent import run_task_sync
from gui_agent.config import get_settings
from gui_agent.video import VideoManager

logger = logging.getLogger(__name__)


def main() -> None:
    """Main CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    settings = get_settings()
    video_manager = VideoManager(settings)

    print("=" * 80)
    print("GUI Automation Agent (ADK + Playwright MCP)")
    print("=" * 80)
    print()
    print(f"Model: {settings.model_name}")
    print(f"Auth: {settings.auth_mode}")
    print(f"Headless: {settings.browser_headless}")
    print(f"Video Recording: {'ENABLED' if settings.video_recording_enabled else 'DISABLED'}")

    if settings.video_recording_enabled:
        stats = video_manager.get_recording_stats()
        print(f"Recordings: {stats['count']} files, {stats['total_size_mb']} MB")

    print()
    print("Commands:")
    print("  - Type your task and press Enter")
    print("  - Type '/video on' to enable recording for next task")
    print("  - Type '/video off' to disable recording")
    print("  - Type '/video stats' to see recording statistics")
    print("  - Type '/video clean' to clean up old recordings")
    print("  - Type '/quit' or '/exit' to quit")
    print("=" * 80)
    print()

    video_override = None  # None = use settings, True/False = override

    while True:
        try:
            task = input("📝 Task: ").strip()

            if not task:
                continue

            # Handle commands
            if task.lower() in ["/quit", "/exit"]:
                print("\n👋 Goodbye!")
                sys.exit(0)

            elif task.lower() == "/video on":
                video_override = True
                print("✅ Video recording enabled for next task")
                continue

            elif task.lower() == "/video off":
                video_override = False
                print("❌ Video recording disabled for next task")
                continue

            elif task.lower() == "/video stats":
                stats = video_manager.get_recording_stats()
                print(f"\n📊 Recording Statistics:")
                print(f"  Count: {stats['count']}")
                print(f"  Total Size: {stats['total_size_mb']} MB")
                print(f"  Oldest: {stats['oldest']}")
                print(f"  Newest: {stats['newest']}\n")
                continue

            elif task.lower() == "/video clean":
                deleted = video_manager.cleanup_old_recordings()
                print(f"🗑️  Deleted {deleted} old recordings\n")
                continue

            # Run the task
            print(f"\n🤖 Running task...")
            result = run_task_sync(task, enable_video=video_override)
            print(f"\n✅ Result:\n{result}\n")

            # Reset override after use
            video_override = None

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            logger.exception("Error running task")
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
```

---

### Phase 4: Makefile Updates

Add video management commands:

```makefile
# Video Recording
.PHONY: video-stats
video-stats:
	@echo "📊 Video Recording Statistics"
	@ls -lh recordings/ 2>/dev/null || echo "No recordings found"

.PHONY: video-clean
video-clean:
	@echo "🗑️  Cleaning old recordings..."
	uv run python -c "from gui_agent.video import VideoManager; from gui_agent.config import get_settings; VideoManager(get_settings()).cleanup_old_recordings()"

.PHONY: video-convert
video-convert:
	@echo "🎬 Converting recordings to MP4..."
	@for file in recordings/*.webm; do \
		if [ -f "$$file" ]; then \
			ffmpeg -i "$$file" -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k "$${file%.webm}.mp4"; \
		fi \
	done
```

---

## Integration with Playwright MCP

### Challenge: Passing Video Config to MCP

The @playwright/mcp server may not expose video configuration through its SSE API. We have three options:

### Option A: Fork Playwright MCP (Most Control)

Fork the @playwright/mcp package and add video support:

```typescript
// In forked @playwright/mcp
async function createBrowserContext(args: any) {
  const context = await browser.newContext({
    ...args,
    recordVideo: process.env.VIDEO_RECORDING_ENABLED === 'true' ? {
      dir: process.env.VIDEO_RECORDING_DIR || '/recordings',
      size: {
        width: parseInt(process.env.VIDEO_WIDTH || '1280'),
        height: parseInt(process.env.VIDEO_HEIGHT || '720'),
      }
    } : undefined,
  });
  return context;
}
```

Then update `docker-compose.yml` to use the fork.

### Option B: Environment-Based (Simplest)

Configure video recording through environment variables that the MCP server reads:

```yaml
# docker-compose.yml
environment:
  - VIDEO_RECORDING_ENABLED=true
  - VIDEO_RECORDING_DIR=/recordings
  - VIDEO_WIDTH=1280
  - VIDEO_HEIGHT=720
```

This requires either:
1. Forking @playwright/mcp to read these env vars
2. Creating a wrapper script that modifies MCP behavior

### Option C: Separate Playwright Script (Most Flexible)

Instead of relying on MCP, create a separate Playwright script that the agent invokes:

```python
# src/gui_agent/recorder.py
import asyncio
from playwright.async_api import async_playwright

async def record_task(task_func, video_path: str):
    """Run a task with video recording."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            record_video={
                'dir': str(video_path.parent),
                'size': {'width': 1280, 'height': 720}
            }
        )
        page = await context.new_page()

        # Run the task
        await task_func(page)

        # Close context to save video
        await context.close()
        await browser.close()
```

---

## Alternative: FFmpeg Screen Recording

If Playwright video API is not accessible, use FFmpeg to record Xvfb:

### Modified Docker Command

```yaml
command: >
  bash -c "
    # Install FFmpeg
    apt-get update && apt-get install -y ffmpeg xvfb &&

    # Start Xvfb
    Xvfb :99 -screen 0 1280x720x24 &

    # Install Playwright MCP
    npm install -g @playwright/mcp@latest &&
    npx playwright install chrome --with-deps &&

    # Start MCP
    npx @playwright/mcp@latest --port 8931 --host 0.0.0.0 --headless --no-sandbox
  "
```

### Recording Script

```bash
#!/bin/bash
# scripts/record_session.sh

SESSION_ID=$1
OUTPUT_DIR="/recordings"
OUTPUT_FILE="$OUTPUT_DIR/session_${SESSION_ID}_$(date +%Y%m%d_%H%M%S).mp4"

# Start recording
ffmpeg -video_size 1280x720 \
       -framerate 25 \
       -f x11grab \
       -i :99 \
       -c:v libx264 \
       -preset ultrafast \
       -crf 23 \
       "$OUTPUT_FILE" &

FFMPEG_PID=$!
echo $FFMPEG_PID > "/tmp/recording_${SESSION_ID}.pid"

echo "Recording started: $OUTPUT_FILE"
```

### Stop Recording

```bash
#!/bin/bash
# scripts/stop_recording.sh

SESSION_ID=$1
PID_FILE="/tmp/recording_${SESSION_ID}.pid"

if [ -f "$PID_FILE" ]; then
    FFMPEG_PID=$(cat "$PID_FILE")
    kill -INT $FFMPEG_PID
    rm "$PID_FILE"
    echo "Recording stopped"
fi
```

---

## Testing Plan

### Test 1: Basic Recording

```bash
# Enable video in .env
VIDEO_RECORDING_ENABLED=true

# Run a simple task
make run-headless

# Task: "Navigate to example.com and take a screenshot"

# Verify video was created
ls -lh recordings/
```

### Test 2: Video Retention

```bash
# Set retention to 1 day
VIDEO_RETENTION_DAYS=1

# Create some old recordings (manually set mtime)
touch -t 202601010000 recordings/old_session.webm

# Run cleanup
make video-clean

# Verify old file was deleted
```

### Test 3: Video Conversion

```bash
# Record a session
make run-headless

# Convert to MP4
make video-convert

# Verify MP4 was created
ls -lh recordings/*.mp4
```

### Test 4: Selective Recording

```bash
# Disable by default
VIDEO_RECORDING_ENABLED=false

# In CLI, enable for one task
/video on
Task: "Fill form on example.com"

# Verify video was created only for that task
```

---

## Performance Considerations

### Storage

- **WebM format:** ~1-2 MB per minute (1280x720, default quality)
- **MP4 format:** ~2-3 MB per minute (after conversion)
- **Typical session:** 5-10 minutes = 5-20 MB per video

**Recommendations:**
- Enable `VIDEO_KEEP_ON_SUCCESS=false` to auto-delete successful runs
- Set `VIDEO_RETENTION_DAYS=7` for automatic cleanup
- Use WebM for storage efficiency (convert to MP4 only when sharing)

### CPU/Memory

- **Playwright video:** Minimal overhead (<5% CPU)
- **FFmpeg recording:** Moderate overhead (10-15% CPU)
- **Video conversion:** High CPU usage (1-2 minutes per video)

**Recommendations:**
- Use Playwright native recording when possible
- Run video conversion as background job
- Consider disabling video for production workloads

---

## Deployment Checklist

### Local Testing

- [ ] Update `docker-compose.yml` with video volume
- [ ] Update `.env` with video settings
- [ ] Test video recording with simple task
- [ ] Verify video file is accessible on host
- [ ] Test video cleanup

### GCP Cloud Shell

- [ ] Ensure recordings directory has sufficient space
- [ ] Test video download from Cloud Shell
- [ ] Verify FFmpeg is available for conversions
- [ ] Test retention cleanup (avoid filling disk)

### Documentation

- [ ] Update README.md with video recording section
- [ ] Update AGENTS.md with video configuration
- [ ] Add troubleshooting guide for common issues
- [ ] Create demo video showing the feature

---

## Troubleshooting

### Issue: Videos are empty or corrupted

**Causes:**
- Browser context closed before video finishes writing
- Insufficient disk space
- Permission issues on recordings directory

**Solutions:**
```bash
# Check disk space
df -h

# Fix permissions
chmod 777 recordings/

# Verify FFmpeg works
docker exec gui-agent-playwright ffmpeg -version
```

### Issue: Videos are too large

**Solutions:**
```bash
# Reduce video quality in .env
VIDEO_QUALITY=30

# Reduce video size
VIDEO_SIZE=1024x576

# Use aggressive compression for conversion
ffmpeg -i input.webm -c:v libx264 -preset slow -crf 28 output.mp4
```

### Issue: Recording not starting

**Debug steps:**
```bash
# Check if video is enabled
docker exec gui-agent-playwright env | grep VIDEO

# Check recordings directory
docker exec gui-agent-playwright ls -la /recordings

# Check Playwright logs
docker logs gui-agent-playwright | grep -i video
```

---

## Future Enhancements

### Phase 5: Advanced Features

1. **Timestamped Overlays:**
   - Add timestamp, task name, and session ID to videos
   - Use FFmpeg filters: `drawtext` filter

2. **Action Annotations:**
   - Highlight clicks and form inputs in the video
   - Record cursor movements and interactions

3. **Video Thumbnails:**
   - Generate preview thumbnails for easier browsing
   - Use FFmpeg: `ffmpeg -i video.webm -ss 00:00:03 -vframes 1 thumb.jpg`

4. **Cloud Storage Integration:**
   - Upload recordings to Google Cloud Storage
   - Generate shareable links for business partners

5. **Video Analytics:**
   - Track which tasks are recorded most often
   - Analyze video file sizes and retention patterns

6. **GIF Generation:**
   - Create short GIF clips for quick sharing
   - Use FFmpeg: `ffmpeg -i video.webm -vf "fps=10,scale=640:-1" output.gif`

---

## Summary

This plan provides two implementation paths:

1. **Playwright Native (Recommended):** Cleanest integration, minimal overhead
2. **FFmpeg with Xvfb (Fallback):** More complex but guaranteed to work

**Next Steps:**
1. Choose implementation approach based on @playwright/mcp capabilities
2. Implement Phase 1 (Docker) and Phase 2 (Environment)
3. Test with simple recording scenarios
4. Iterate based on feedback and performance metrics

**Estimated Implementation Time:**
- Phase 1-2 (Infrastructure): 2-3 hours
- Phase 3 (Python code): 3-4 hours
- Phase 4 (Makefile/Testing): 1-2 hours
- **Total: 6-9 hours**

---

*This plan can be adapted based on actual @playwright/mcp API capabilities discovered during implementation.*
