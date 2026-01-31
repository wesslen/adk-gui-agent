#!/bin/bash
# Run the GUI agent in headed mode (for local development with visible browser)
#
# This script:
# 1. Starts services in headed mode
# 2. Opens the browser for visual feedback
# 3. Runs the agent
#
# Usage:
#   ./scripts/run_headed.sh
#   ./scripts/run_headed.sh "Fill the form at localhost:8080/simple"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🖥️  GUI Agent - Headed Mode (Development)${NC}"
echo "==========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   Please edit .env with your configuration${NC}"
fi

# Source environment variables
set -a
source .env
set +a

# Override for headed mode
export BROWSER_HEADLESS=false

# Function to check if a port is in use
port_in_use() {
    nc -z localhost "$1" 2>/dev/null
}

# Start mock server if not running
if ! port_in_use 8080; then
    echo -e "\n${BLUE}📝 Starting mock form server...${NC}"
    uvicorn mock_sites.server:app --host 0.0.0.0 --port 8080 &
    MOCK_PID=$!
    sleep 2
    echo -e "   Mock server: http://localhost:8080"
fi

# Start Phoenix if Docker available
if command -v docker &> /dev/null; then
    if ! port_in_use 6006; then
        echo -e "\n${BLUE}📊 Starting Phoenix...${NC}"
        docker compose up -d phoenix
        sleep 3
    fi
    echo -e "   Phoenix UI: http://localhost:6006"
fi

# Check Playwright MCP
if ! port_in_use 3000; then
    echo -e "\n${YELLOW}⚠️  Playwright MCP not detected on port 3000${NC}"
    echo -e "   For headed mode, run Playwright MCP locally:"
    echo -e "   ${BLUE}npx @anthropic-ai/mcp-server-playwright --port 3000${NC}"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to exit..."
fi

echo -e "\n${GREEN}🤖 Starting GUI Agent (Headed Mode)...${NC}"
echo "==========================================="
echo -e "${YELLOW}Note: Browser windows will be visible${NC}"
echo ""

if [ -n "$1" ]; then
    python -m gui_agent.cli --task "$1"
else
    python -m gui_agent.cli
fi

# Cleanup
if [ -n "$MOCK_PID" ]; then
    kill $MOCK_PID 2>/dev/null || true
fi
