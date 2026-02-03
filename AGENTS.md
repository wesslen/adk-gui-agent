# AGENTS.md - Project Context

> This file helps Agents understand the project state, architecture, and development patterns. Last updated: 2026-02-01

## Project Overview

**adk-gui-agent** is a browser automation agent built with Google ADK (Agent Development Kit) and Playwright MCP. It enables LLM-powered form filling and web navigation tasks in headless environments like GCP Cloud Shell.

**Tech Stack:**
- Python 3.12+ with `uv` package manager
- Google Gemini 2.5 Flash via Vertex AI
- Playwright MCP (@playwright/mcp) for browser control
- Docker for service orchestration
- Arize Phoenix for observability/tracing

---

## Quick Start

```bash
# Setup
cd ~/adk-gui-agent
make install          # Install dependencies with uv
make setup-env        # Create .env file (edit with your GCP project)

# Run services
make start-services   # Start Phoenix + Playwright MCP
make start-mock-server  # Optional: start test form server

# Run agent
make run-headless     # Headless mode (for Cloud Shell)
make run-headed       # Headed mode (local dev with display)
```

---

## Current Status: ✅ FULLY WORKING

**Last tested:** 2026-02-01 23:30 UTC

### What's Working
- ✅ Browser automation with external sites (espn.com, etc.)
- ✅ Browser automation with mock server forms
- ✅ Headless Chrome in Docker with `--no-sandbox`
- ✅ MCP server connection and tool execution
- ✅ Vertex AI authentication and LLM calls
- ✅ Observability traces in Arize Phoenix
- ✅ Form filling with structured data
- ✅ `uv` package management throughout
- ✅ All code synced: Local ↔ GCP Cloud Shell ↔ GitHub

### Known Limitations
- Running in GCP Cloud Shell (no display for headed mode)
- Mock server must use container name (`http://mock-server:8080`) not `localhost` when accessed from browser container
- Docker containers need `--no-sandbox` for Chrome (security trade-off in containerized env)
- Video recording requires Playwright MCP to support video context parameters (may need custom implementation)

---

## Architecture

```
┌─────────────────┐
│  Python Agent   │ (gui_agent.cli)
│  (uv managed)   │
└────────┬────────┘
         │
         ├─→ Google Gemini 2.5 Flash (via Vertex AI)
         │   - Model: gemini-2.5-flash
         │   - Auth: Vertex AI service account
         │
         ├─→ Playwright MCP Server (Docker)
         │   - Port: 8931
         │   - Browser: Chrome (headless, no-sandbox)
         │   - Tools: browser_navigate, browser_screenshot, etc.
         │
         └─→ Arize Phoenix (Docker)
             - Port: 6006
             - Observability: traces, spans, tool calls
```

**Docker Network:** All containers run on `gui-agent-network` bridge network
- Containers can reach each other by container name (e.g., `mock-server:8080`)
- Host services on `localhost` not accessible from containers

---

## Key Files & Their Purpose

### Configuration
- `.env` - Environment variables (GCP project, model, ports)
- `.env.example` - Template with all settings documented
- `pyproject.toml` - Python dependencies (managed by uv)
- `docker-compose.yml` - Service orchestration

### Source Code
- `src/gui_agent/agent.py` - Core agent logic, MCP tool integration
- `src/gui_agent/cli.py` - Interactive CLI interface
- `src/gui_agent/config.py` - Settings management (Pydantic)
- `src/gui_agent/prompts.py` - System prompts for the agent
- `src/gui_agent/observability.py` - Phoenix tracing setup

### Docker
- `Dockerfile.mock` - Mock form server (FastAPI + uvicorn)
- `docker-compose.yml` - Phoenix + Playwright MCP + Mock server

### Infrastructure
- `Makefile` - Common commands (all use `uv run`)
- `scripts/run_headless.sh` - Headless mode startup script

---

## Development Patterns

### Package Management
**Always use `uv` for consistency:**
```bash
uv sync                    # Install dependencies
uv sync --extra dev        # Include dev deps
uv run python -m gui_agent.cli  # Run with uv
```

All Makefile targets use `uv run` to ensure correct environment.

### Agent Code Structure
```python
# Message format for ADK Runner
from google.genai import types

user_message = types.Content(
    role="user",
    parts=[types.Part(text=task)]
)

# Session creation (async)
session = await session_service.create_session(...)

# Runner execution (async generator)
async for event in runner.run_async(
    user_id=user_id,
    session_id=session_id,
    new_message=user_message,  # Must be types.Content, not str
):
    # Process events
```

### Docker Container Networking
```bash
# ❌ WRONG: From container to host service
curl http://localhost:8080  # Won't work

# ✅ CORRECT: From container to container
curl http://mock-server:8080  # Works

# ✅ CORRECT: From host to any container
curl http://localhost:8080  # Works if port is mapped
```

---

## Common Issues & Solutions

### Issue: "Chromium distribution 'chrome' is not found"
**Solution:** Install `chrome` (not `chromium`) with `--with-deps`
```yaml
npx playwright install chrome --with-deps
```

### Issue: "Running as root without --no-sandbox is not supported"
**Solution:** Add `--no-sandbox` flag to Playwright MCP
```yaml
npx @playwright/mcp@latest --port 8931 --host 0.0.0.0 --headless --no-sandbox
```

### Issue: "Form data requires python-multipart"
**Solution:** Install in Dockerfile.mock
```dockerfile
RUN pip install --no-cache-dir fastapi uvicorn python-multipart
```

### Issue: "object async_generator can't be used in 'await' expression"
**Solution:** Use `async for` not `await` on `runner.run_async()`
```python
# ❌ WRONG
response = await runner.run_async(...)

# ✅ CORRECT
async for event in runner.run_async(...):
    # Process event
```

### Issue: "'str' object has no attribute 'role'"
**Solution:** Pass `types.Content` object, not raw string
```python
# ❌ WRONG
runner.run_async(new_message="Navigate to...")

# ✅ CORRECT
message = types.Content(role="user", parts=[types.Part(text="Navigate to...")])
runner.run_async(new_message=message)
```

---

## Testing

### Mock Server Forms
```bash
# Start mock server
make start-mock-server

# Access forms (from host)
http://localhost:8080/simple       # Simple contact form
http://localhost:8080/complex      # Multi-step form

# Access forms (from agent/container)
http://mock-server:8080/simple
http://mock-server:8080/complex
```

### Example Tasks
```python
# External site
"Go to espn.com and take a screenshot"

# Mock server form
"Navigate to http://mock-server:8080/simple and fill out the contact form with:
- First Name: John
- Last Name: Doe
- Email: john.doe@example.com
- Phone: 555-123-4567
- Subject: General Inquiry"
```

### Observability
```bash
# View traces in Phoenix
open http://localhost:6006

# Watch logs
docker logs -f gui-agent-playwright
docker logs -f gui-agent-phoenix
```

---

## Environment Variables

Key settings in `.env`:
```bash
# GCP / Vertex AI
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Model
MODEL_NAME=gemini-2.5-flash

# Playwright MCP
PLAYWRIGHT_MCP_URL=http://localhost:8931/sse  # Port 8931, not 3000!
BROWSER_HEADLESS=true

# Phoenix
ENABLE_TRACING=true
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

---

## Video Recording

**NEW:** The agent now supports video recording for debugging and demo purposes!

### Quick Start

```bash
# Enable in .env
VIDEO_RECORDING_ENABLED=true

# Or enable for single task in CLI
/video on

# Run task (video will be saved to ./recordings/)
make run-headless
```

### Configuration

Add to `.env`:
```bash
VIDEO_RECORDING_ENABLED=false        # Enable/disable video recording
VIDEO_RECORDING_DIR=./recordings     # Directory for video files
VIDEO_SIZE=1280x720                  # Video dimensions
VIDEO_KEEP_ON_SUCCESS=false          # Keep videos after successful runs
VIDEO_RETENTION_DAYS=7               # Auto-cleanup after N days (0=never)
```

### CLI Commands

Interactive mode supports video commands:
- `/video on` - Enable recording for next task
- `/video off` - Disable recording for next task
- `/video stats` - Show recording statistics
- `/video clean` - Clean up old recordings

### Makefile Targets

```bash
make video-stats      # Show statistics
make video-clean      # Delete old recordings
make video-convert    # Convert WebM to MP4
```

### File Locations

Videos are saved to `./recordings/` with format:
```
session_<session_id>_<timestamp>.webm
```

Example: `session_abc123_20260201_143022.webm`

### Storage & Performance

- **Format:** WebM (1-2 MB per minute at 1280x720)
- **Auto-cleanup:** Configurable retention period (default 7 days)
- **Smart deletion:** Auto-delete successful runs if `VIDEO_KEEP_ON_SUCCESS=false`
- **Conversion:** Use `make video-convert` to create MP4 files for better compatibility

### Use Cases

🎯 **Debugging:** Record full sessions to see what went wrong visually
🎯 **Demos:** Share videos with business partners
🎯 **Development:** Verify form filling behavior step-by-step
🎯 **Compliance:** Keep audit trail of automation actions

### Implementation Notes

- FFmpeg is installed in the Playwright MCP container for video processing
- Videos are stored in a shared Docker volume (`./recordings:/recordings`)
- The `VideoManager` class handles cleanup, stats, and conversion
- Actual Playwright video recording depends on MCP API support (see VIDEO_RECORDING_PLAN.md for details)

---

## Recent Changes

### 2026-02-01 (Video Recording)

1. **Added video recording support:**
   - New `src/gui_agent/video.py` module with `VideoManager` class
   - Video configuration in `.env` (enabled, directory, size, retention)
   - CLI commands: `/video on`, `/video off`, `/video stats`, `/video clean`
   - Makefile targets: `make video-stats`, `make video-clean`, `make video-convert`
   - Docker: FFmpeg installed in Playwright container, shared volume for recordings
   - Auto-cleanup based on retention period
   - Smart deletion for successful runs (configurable)

2. **Updated configuration:**
   - Added video settings to `config.py`
   - New `.env` variables for video recording
   - Updated `docker-compose.yml` with recordings volume

### 2026-02-01 (Initial Release)

1. **Fixed async/await issues in `agent.py`:**
   - Added `await` to `session_service.create_session()`
   - Changed `runner.run_async()` from `await` to `async for`
   - Fixed message format to use `types.Content` object

2. **Fixed Chrome installation:**
   - Changed from `chromium` to `chrome`
   - Added `--no-sandbox` flag to Playwright MCP
   - Added `--with-deps` for system dependencies

3. **Fixed mock server:**
   - Added `python-multipart` to Dockerfile.mock

4. **Switched to `uv` package manager:**
   - Updated all Makefile targets to use `uv run`
   - Added `install-uv` target
   - Better dependency management and environment isolation

---

## Dependencies

### Core
- `google-adk>=0.5.0` - Agent framework
- `google-genai>=1.0.0` - Gemini API client

### Observability
- `arize-phoenix>=8.0.0` - Tracing/observability
- `openinference-instrumentation-google-genai>=0.1.0`

### Configuration
- `pydantic-settings>=2.0.0`
- `python-dotenv>=1.0.0`

### Dev (optional)
- `pytest>=8.0.0`
- `pytest-asyncio>=0.24.0`
- `ruff>=0.4.0` - Linting/formatting
- `mypy>=1.10.0` - Type checking

### Mock Server (optional)
- `fastapi>=0.115.0`
- `uvicorn>=0.30.0`
- `python-multipart` - For form handling

---

## Debugging Tips

### Check Service Health
```bash
# Playwright MCP
curl http://localhost:8931/sse
docker logs gui-agent-playwright --tail 30

# Phoenix
curl http://localhost:6006/health
docker logs gui-agent-phoenix --tail 30

# Mock server
curl http://localhost:8080/simple
docker logs gui-agent-mock --tail 30
```

### View Traces
1. Open Phoenix UI: http://localhost:6006
2. Run a task in the agent
3. Check traces for:
   - LLM requests/responses
   - Tool calls (browser_navigate, etc.)
   - Errors and latency

### Interactive Debugging
```bash
# Enter container
docker exec -it gui-agent-playwright bash

# Check browsers
ls -la /ms-playwright/
npx playwright --version

# Test browser launch
npx playwright open --browser chrome --headless https://example.com
```

---

## Next Steps / Roadmap

- [ ] Add more comprehensive tests (unit, integration)
- [ ] Document complex form filling scenarios
- [ ] Add retry logic for flaky network requests
- [ ] Consider alternatives to `--no-sandbox` for production
- [ ] Add more mock forms (multi-step, file uploads, etc.)
- [ ] Improve error messages and recovery
- [ ] Add session persistence across runs
- [x] ~~Consider adding video recording for debugging~~ **DONE** (2026-02-01)
- [ ] Implement actual Playwright video recording at MCP level
- [ ] Add video thumbnails and preview generation
- [ ] Cloud storage integration for recordings (GCS)

---

## Contact & Resources

- **Playwright MCP:** https://github.com/microsoft/playwright-mcp
- **Google ADK:** https://github.com/google/adk
- **GCP Cloud Shell:** https://cloud.google.com/shell/docs

---

*This file is maintained for Agents to understand the project context. Update when making significant changes.*
