#!/bin/bash
# Setup script for headed mode on Mac with XQuartz
#
# This script configures XQuartz to allow Docker containers to display
# browser windows on your Mac desktop.

set -e

echo "=================================================="
echo "Setting up Headed Mode for Mac (XQuartz)"
echo "=================================================="
echo ""

# Check if XQuartz is installed
if ! command -v xquartz &> /dev/null; then
    echo "❌ XQuartz is not installed!"
    echo ""
    echo "Install it with:"
    echo "  brew install --cask xquartz"
    echo ""
    echo "Then log out and log back in (XQuartz requires a session restart)"
    exit 1
fi

echo "✅ XQuartz is installed at: $(command -v xquartz)"
echo ""

# Check if XQuartz is running
if ! pgrep -x "XQuartz" > /dev/null; then
    echo "⚠️  XQuartz is not running. Starting it now..."
    open -a XQuartz
    echo "   Waiting for XQuartz to start..."
    sleep 5
else
    echo "✅ XQuartz is running"
fi
echo ""

# Wait for XQuartz to be fully ready
echo "Waiting for XQuartz display server to be ready..."
RETRY_COUNT=0
MAX_RETRIES=10
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Try to use DISPLAY=:0 which is more reliable than the socket path
    if DISPLAY=:0 xhost > /dev/null 2>&1; then
        echo "✅ XQuartz display server is ready"
        break
    fi
    echo "   Attempt $((RETRY_COUNT + 1))/$MAX_RETRIES - waiting..."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "⚠️  XQuartz may not be fully started. Proceeding anyway..."
fi
echo ""

# Allow localhost connections (use DISPLAY=:0 explicitly)
echo "Configuring xhost to allow localhost connections..."
if DISPLAY=:0 xhost +localhost > /dev/null 2>&1; then
    echo "✅ localhost access granted"
else
    echo "⚠️  Could not configure xhost automatically."
    echo ""
    echo "   Please run this command manually in a terminal:"
    echo "   DISPLAY=:0 xhost +localhost"
    echo ""
fi
echo ""

# Check XQuartz preferences
echo "=================================================="
echo "XQuartz Configuration Check"
echo "=================================================="
echo ""
echo "Please verify these XQuartz settings:"
echo ""
echo "1. Open XQuartz Preferences (XQuartz → Settings)"
echo "2. Go to the 'Security' tab"
echo "3. Ensure these are CHECKED:"
echo "   ✓ Allow connections from network clients"
echo ""
echo "If you made changes, you'll need to restart XQuartz:"
echo "   1. Quit XQuartz completely"
echo "   2. Run: open -a XQuartz"
echo "   3. Run this script again"
echo ""

# Display current DISPLAY value
echo "=================================================="
echo "Environment Check"
echo "=================================================="
echo ""
echo "System DISPLAY: ${DISPLAY:-not set}"
echo "Docker will use: host.docker.internal:0"
echo "Recommended DISPLAY for XQuartz: :0 or localhost:0"
echo ""

# Check if xhost shows localhost (use DISPLAY=:0)
echo "Checking xhost access control..."
if DISPLAY=:0 xhost 2>/dev/null | grep -q "localhost"; then
    echo "✅ xhost configuration looks good:"
    DISPLAY=:0 xhost | grep localhost
elif DISPLAY=:0 xhost 2>/dev/null | grep -q "access control disabled"; then
    echo "✅ xhost access control is disabled (permissive mode)"
    echo "   This will allow Docker to connect"
else
    echo "⚠️  Could not verify xhost configuration"
    echo ""
    echo "   If headed mode doesn't work, try running:"
    echo "   DISPLAY=:0 xhost +localhost"
fi
echo ""

echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "To start services in headed mode:"
echo "  make start-services-headed"
echo ""
echo "Then run your agent with:"
echo "  make run-headed"
echo ""
echo "You should see a Firefox window open on your desktop!"
echo ""
