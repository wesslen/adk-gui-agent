#!/bin/bash
# Run the GUI agent in headless mode (for GCP Cloud Shell or CI)
#
# This script:
# 1. Ensures Docker services are running
# 2. Waits for services to be healthy
# 3. Runs the agent in headless mode
#
# Usage:
#   ./scripts/run_headless.sh
#   ./scripts/run_headless.sh "Navigate to example.com and take a screenshot"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 GUI Agent - Headless Mode${NC}"
echo "================================"

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

# Override for headless mode
export BROWSER_HEADLESS=true

# Function to wait for a service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30

    echo -n "Waiting for $service_name ($host:$port)..."
    for i in $(seq 1 $max_attempts); do
        if nc -z "$host" "$port" 2>/dev/null; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    echo -e " ${RED}✗${NC}"
    return 1
}

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo -e "\n${GREEN}🐳 Starting Docker services...${NC}"

    # Start services if not running
    if ! docker compose ps --status running | grep -q "phoenix"; then
        docker compose up -d phoenix
    fi

    # Wait for Phoenix
    wait_for_service localhost 6006 "Phoenix"

    echo -e "\n📊 Phoenix UI: http://localhost:6006"
else
    echo -e "${YELLOW}⚠️  Docker not available. Skipping Phoenix startup.${NC}"
    echo "   Tracing will be disabled."
    export ENABLE_TRACING=false
fi

# Check for Playwright MCP
if ! nc -z localhost 3000 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Playwright MCP not running on port 3000${NC}"
    echo "   Start it with: npx @anthropic-ai/mcp-server-playwright --port 3000"
    echo "   Or use Docker: docker compose up -d playwright-mcp"
fi

# Run the agent
echo -e "\n${GREEN}🤖 Starting GUI Agent...${NC}"
echo "================================"

if [ -n "$1" ]; then
    # Run single task if provided
    python -m gui_agent.cli --task "$1"
else
    # Interactive mode
    python -m gui_agent.cli
fi
