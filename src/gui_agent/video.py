"""Video recording utilities for browser automation."""

from __future__ import annotations

import logging
import subprocess
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
