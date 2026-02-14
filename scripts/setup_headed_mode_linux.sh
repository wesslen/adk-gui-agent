#!/bin/bash
# Setup script for headed mode on Linux with X11

set -e

echo "=================================================="
echo "Setting up Headed Mode for Linux (X11)"
echo "=================================================="
echo ""

# Check if X11 is running
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY environment variable is not set"
    echo ""
    echo "X11 does not appear to be running. Headed mode requires a display."
    echo ""
    echo "If you're on a remote server without a display, use headless mode instead:"
    echo "  make start-services"
    echo "  make run-headless"
    echo ""
    exit 1
fi

echo "✅ DISPLAY is set to: $DISPLAY"
echo ""

# Check if xhost is available
if ! command -v xhost &> /dev/null; then
    echo "⚠️  xhost command not found"
    echo ""
    echo "Install it with:"
    echo "  Ubuntu/Debian: sudo apt-get install x11-xserver-utils"
    echo "  Fedora/RHEL:   sudo dnf install xorg-x11-server-utils"
    echo "  Arch:          sudo pacman -S xorg-xhost"
    echo ""
    exit 1
fi

echo "✅ xhost is installed"
echo ""

# Allow Docker to connect to X11
echo "Configuring xhost to allow Docker connections..."
if xhost +local:docker > /dev/null 2>&1; then
    echo "✅ Docker access granted to X11 display"
else
    echo "⚠️  Could not configure xhost"
    echo ""
    echo "You may need to run this manually:"
    echo "  xhost +local:docker"
    echo ""
fi
echo ""

# Check if /tmp/.X11-unix exists
if [ -S "/tmp/.X11-unix/X${DISPLAY#*:}" ]; then
    echo "✅ X11 Unix socket exists: /tmp/.X11-unix/X${DISPLAY#*:}"
else
    echo "⚠️  X11 Unix socket not found at /tmp/.X11-unix/X${DISPLAY#*:}"
    echo ""
    echo "This may cause issues. Make sure X11 is running properly."
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
echo "You should see a Firefox window open on your display!"
echo ""
echo "Note: If you log out or restart, you'll need to run this setup again."
echo ""
