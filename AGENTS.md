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

# Run ADK evals (requires google-adk[eval])
uv add "google-adk[eval]"                                        # One-time setup
uv run adk eval gui_agent_v1 gui_agent_v1/evals/simple.evalset.json   # Run simple evals
uv run adk eval gui_agent_v1 gui_agent_v1/evals/complex.evalset.json  # Run complex evals
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

---

## Architecture

```
┌─────────────────┐
│  Python Agent   │ (gui_agent_v1.cli)
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
         │   - Tools: browser_navigate, browser_take_screenshot, etc.
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
- `gui_agent_v1/agent.py` - Core agent logic, MCP tool integration
- `gui_agent_v1/cli.py` - Interactive CLI interface
- `gui_agent_v1/config.py` - Settings management (Pydantic)
- `gui_agent_v1/prompts.py` - System prompts for the agent
- `gui_agent_v1/observability.py` - Phoenix tracing setup
- `gui_agent_v1/evals/` - ADK evaluation sets (co-located with agent)
  - `basic.evalset.json` - Legacy baseline (4 cases, simple form)
  - `simple.evalset.json` - Simple form: 2 happy paths + 6 failure modes
  - `complex.evalset.json` - Complex form: 2 happy paths + 8 failure modes

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
uv run python -m gui_agent_v1.cli  # Run with uv
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

### ADK Evaluation Sets

Eval sets live alongside the agent source at `gui_agent_v1/evals/` (following ADK convention).

| File | Target | Cases | Description |
|------|--------|-------|-------------|
| `basic.evalset.json` | `/simple` | 4 | Legacy baseline cases |
| `simple.evalset.json` | `/simple` | 8 | 2 happy paths + 6 failure modes |
| `complex.evalset.json` | `/complex` | 10 | 2 happy paths + 8 failure modes |

**Simple form failure modes tested:**

| Failure Mode | Eval Case ID | Criterion |
|---|---|---|
| Snapshot before interact | `simple_fail_snapshot_before_interact` | `browser_snapshot` precedes any `browser_type`/`browser_click` |
| Stale ref after select | `simple_fail_stale_ref_after_select` | Re-snapshot after `browser_select_option` |
| Dropdown must use select_option | `simple_fail_dropdown_must_use_select` | `browser_select_option` (not `browser_type`) for `<select>` |
| Required field coverage | `simple_fail_required_field_coverage` | All 5 required fields filled |
| No premature submit | `simple_fail_no_premature_submit` | No `browser_click` on Submit when told not to |
| Field-data mapping | `simple_fail_field_data_mapping` | Data maps to correct fields regardless of input order |

**Complex form failure modes tested:**

| Failure Mode | Eval Case ID | Criterion |
|---|---|---|
| Step navigation | `complex_fail_step_navigation` | `browser_click` (Next) before Step 2 fields |
| Radio uses click | `complex_fail_radio_must_use_click` | `browser_click` (not `browser_type`) for radios |
| Conditional fields | `complex_fail_conditional_field_blindness` | Equipment checkboxes filled after Remote/Hybrid |
| Checkbox uses click | `complex_fail_checkbox_must_use_click` | `browser_click` for checkboxes |
| Date format | `complex_fail_date_format` | YYYY-MM-DD for `<input type="date">` |
| Cross-step stale refs | `complex_fail_cross_step_stale_refs` | Re-snapshot after clicking Next |
| Validation gate | `complex_fail_validation_gate` | Fill required fields before Next |
| Select value vs label | `complex_fail_select_value_not_label` | Option `value` attr, not display text |

```bash
# Run eval tests
make test                          # All tests
make test-fast                     # Skip slow/integration
pytest -m evalset                  # Eval set tests only
pytest tests/test_agent.py -k "Simple"   # Simple form evals
pytest tests/test_agent.py -k "Complex"  # Complex form evals
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
- Subject: General Inquiry
- Message: What days are the office open?
Take a screenshot image confirming the completion of the task"
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

## Recent Changes

### 2026-02-10: Project Restructure — Remove src/, Rename to gui_agent_v1
1. **Moved `src/gui_agent/` → `gui_agent_v1/`** at project root (supports multi-version agents)
2. **Renamed all imports** from `gui_agent` to `gui_agent_v1` across source, tests, and scripts
3. **Updated `pyproject.toml`**: packages, entry point, pythonpath all reference `gui_agent_v1`
4. **Updated Makefile**: all `src/` paths replaced with `gui_agent_v1/`
5. **Updated shell scripts**: `python -m gui_agent_v1.cli`

### 2026-02-10: ADK Eval Test Coverage Overhaul
1. **Moved eval sets to `gui_agent_v1/evals/`** (co-located with agent per ADK convention)
2. **Created `simple.evalset.json`** — 8 cases (2 happy paths + 6 failure modes)
3. **Created `complex.evalset.json`** — 10 cases (2 happy paths + 8 failure modes)
4. **Rewrote `test_agent.py` eval validation:**
   - Parametrized loader tests across all 3 evalsets
   - Added structural validation (unique IDs, known tools, required fields)
   - Added per-form test classes (`TestSimpleFormEvalCases`, `TestComplexFormEvalCases`)
   - Validates trajectory ordering, criteria flags, and ISO date formats
5. **Updated `conftest.py`** — `load_evalset` now takes flat name, points to `gui_agent_v1/evals/`
6. **Fixed `root_agent` export for ADK CLI** — replaced broken `property()` descriptor with
   eager module-level `LlmAgent` instance (ADK requires a real instance, not a descriptor)
7. **Added `from . import agent` to `__init__.py`** — needed for ADK CLI path resolution
   (`gui_agent_v1.agent.root_agent`)
8. **Added `google-adk[eval]` dependency** — required for `adk eval` CLI. Install via
   `uv add "google-adk[eval]"`

### 2026-02-01: Initial Working Agent
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
- `google-adk[eval]>=0.5.0` - Agent framework (includes eval CLI: `uv add "google-adk[eval]"`)
- `google-genai>=1.0.0` - Gemini API client

### Observability
- `arize-phoenix>=8.0.0` - Tracing/observability
- `openinference-instrumentation-google-adk>=0.1.0` - ADK-level auto-instrumentation

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
2. Run a task via `adk web`, `adk run`, or the CLI
3. Tracing is initialized at module level in `agent.py` — it works
   automatically for all entry points (no extra flags needed)
4. Check traces for:
   - Agent execution steps and decisions
   - LLM requests/responses (input/output tokens)
   - Tool calls (browser_navigate, browser_snapshot, etc.)
   - Errors, latency, and span hierarchy

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

- [x] Add comprehensive eval test coverage (simple + complex forms)
- [x] Document complex form filling scenarios and failure modes
- [ ] Wire eval cases to live integration tests (run agent against mock server)
- [ ] Add ADK user simulation eval cases (multi-turn ConversationScenario format)
- [ ] Implement programmatic evaluation of custom criteria (field_data_mapping, must_not_include_actions)
- [ ] Add retry logic for flaky network requests
- [ ] Consider alternatives to `--no-sandbox` for production
- [ ] Add more mock forms (multi-step, file uploads, etc.)
- [ ] Improve error messages and recovery
- [ ] Add session persistence across runs
- [ ] Consider adding video recording for debugging

---

## Contact & Resources

- **Playwright MCP:** https://github.com/microsoft/playwright-mcp
- **Google ADK:** https://github.com/google/adk
- **GCP Cloud Shell:** https://cloud.google.com/shell/docs

---

*This file is maintained for Agents to understand the project context. Update when making significant changes.*
