#!/usr/bin/env python3
"""Quick test script to verify video module functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gui_agent.config import get_settings
from gui_agent.video import VideoManager


def test_video_manager():
    """Test VideoManager basic functionality."""
    print("=" * 60)
    print("Testing Video Manager")
    print("=" * 60)

    # Load settings
    print("\n1. Loading settings...")
    settings = get_settings()
    print(f"   Video enabled: {settings.video_recording_enabled}")
    print(f"   Video dir: {settings.video_recording_dir}")
    print(f"   Video size: {settings.video_size}")
    print(f"   Keep on success: {settings.video_keep_on_success}")
    print(f"   Retention days: {settings.video_retention_days}")

    # Create VideoManager
    print("\n2. Creating VideoManager...")
    vm = VideoManager(settings)
    print(f"   Recordings dir: {vm.recordings_dir}")
    print(f"   Directory exists: {vm.recordings_dir.exists()}")

    # Test video path generation
    print("\n3. Testing video path generation...")
    test_session_id = "test_session_123"
    video_path = vm.get_video_path(test_session_id)
    print(f"   Generated path: {video_path}")
    print(f"   Filename pattern: session_{test_session_id}_YYYYMMDD_HHMMSS.webm")

    # Get statistics
    print("\n4. Getting recording statistics...")
    stats = vm.get_recording_stats()
    print(f"   Count: {stats['count']}")
    print(f"   Total size: {stats['total_size_mb']} MB")
    print(f"   Oldest: {stats['oldest']}")
    print(f"   Newest: {stats['newest']}")

    # Test video config
    print("\n5. Testing Playwright video config...")
    video_config = settings.get_video_config()
    if video_config:
        print(f"   Video config: {video_config}")
    else:
        print(f"   Video config: None (disabled)")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_video_manager()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
