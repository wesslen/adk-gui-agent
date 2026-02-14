#!/bin/bash
# XQuartz troubleshooting script
# Fixes common XQuartz crash issues on Mac

set -e

echo "=================================================="
echo "XQuartz Crash Fix"
echo "=================================================="
echo ""

# Step 1: Kill any existing processes
echo "1. Checking for running X11/XQuartz processes..."
if pgrep -x "XQuartz" > /dev/null || pgrep -x "X11" > /dev/null; then
    echo "   Killing existing processes..."
    pkill -x "XQuartz" 2>/dev/null || true
    pkill -x "X11" 2>/dev/null || true
    sleep 2
else
    echo "   ✅ No running processes found"
fi
echo ""

# Step 2: Clear XQuartz preferences
echo "2. Backing up and clearing XQuartz preferences..."
PREFS_DIR=~/Library/Preferences
BACKUP_DIR=~/Library/Preferences/xquartz_backup_$(date +%Y%m%d_%H%M%S)

if [ -f "$PREFS_DIR/org.xquartz.X11.plist" ] || [ -f "$PREFS_DIR/org.macosforge.xquartz.X11.plist" ]; then
    mkdir -p "$BACKUP_DIR"
    mv "$PREFS_DIR/org.xquartz.X11.plist" "$BACKUP_DIR/" 2>/dev/null || true
    mv "$PREFS_DIR/org.macosforge.xquartz.X11.plist" "$BACKUP_DIR/" 2>/dev/null || true
    echo "   ✅ Preferences backed up to: $BACKUP_DIR"
else
    echo "   ℹ️  No existing preferences found"
fi
echo ""

# Step 3: Clear XQuartz cache
echo "3. Clearing XQuartz caches..."
rm -rf ~/Library/Caches/org.xquartz.X11 2>/dev/null || true
rm -rf ~/Library/Saved\ Application\ State/org.xquartz.X11.savedState 2>/dev/null || true
echo "   ✅ Caches cleared"
echo ""

# Step 4: Check XQuartz installation
echo "4. Checking XQuartz installation..."
if [ -d "/Applications/Utilities/XQuartz.app" ]; then
    XQUARTZ_VERSION=$(/Applications/Utilities/XQuartz.app/Contents/MacOS/X11 -version 2>&1 | grep "XQuartz" | head -1 || echo "Unknown")
    echo "   ✅ XQuartz is installed: $XQUARTZ_VERSION"
else
    echo "   ❌ XQuartz is not installed!"
    echo ""
    echo "   Install it with:"
    echo "     brew install --cask xquartz"
    echo ""
    echo "   Or download from: https://www.xquartz.org"
    exit 1
fi
echo ""

# Step 5: Try to start XQuartz
echo "5. Attempting to start XQuartz..."
echo "   This may take a few seconds..."
open -a XQuartz 2>&1 &
OPEN_PID=$!

# Wait and check
sleep 5

if pgrep -x "XQuartz" > /dev/null; then
    echo "   ✅ XQuartz started successfully!"
    echo ""
    echo "=================================================="
    echo "Success!"
    echo "=================================================="
    echo ""
    echo "XQuartz is now running. You should see the XQuartz icon in your menu bar."
    echo ""
    echo "Next steps:"
    echo "  1. Configure XQuartz security settings:"
    echo "     - Open XQuartz → Settings → Security"
    echo "     - Check: ✓ Allow connections from network clients"
    echo "     - Restart XQuartz after changing settings"
    echo ""
    echo "  2. Run the headed mode setup:"
    echo "     make setup-headed-mode"
    echo ""
else
    echo "   ❌ XQuartz failed to start"
    echo ""
    echo "=================================================="
    echo "XQuartz Still Crashing"
    echo "=================================================="
    echo ""
    echo "If XQuartz still crashes, try these steps:"
    echo ""
    echo "Option 1: Reinstall XQuartz"
    echo "  brew uninstall --cask xquartz"
    echo "  brew install --cask xquartz"
    echo "  Log out and log back in (required for XQuartz)"
    echo ""
    echo "Option 2: Manual cleanup"
    echo "  1. Completely remove XQuartz:"
    echo "     sudo rm -rf /Applications/Utilities/XQuartz.app"
    echo "     sudo rm -rf /opt/X11"
    echo "     rm -rf ~/Library/Preferences/org.xquartz.X11.plist"
    echo "     rm -rf ~/Library/Preferences/org.macosforge.xquartz.X11.plist"
    echo "  2. Reinstall with Homebrew:"
    echo "     brew install --cask xquartz"
    echo "  3. Log out and log back in"
    echo ""
    echo "Option 3: Check crash logs"
    echo "  View detailed crash info in Console.app:"
    echo "  - Open Console.app"
    echo "  - Search for 'XQuartz' or 'X11'"
    echo "  - Look for crash reports"
    echo ""
    exit 1
fi
