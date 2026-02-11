# GUI Agent Prototype

A form-filling GUI agent built with Google's Agent Development Kit (ADK), using the official Microsoft `@playwright/mcp` for browser automation and Arize Phoenix for observability.

## Features

- **ADK Framework**: Built on Google's Agent Development Kit for structured agent development
- **Gemini LLM**: Uses Gemini 2.5 Flash via Vertex AI or Google AI Studio
- **@playwright/mcp**: Official Microsoft Playwright MCP with ref-based element interaction
- **Docker Services**: Containerized Phoenix and Playwright MCP for easy setup
- **uv Package Manager**: Fast, reliable Python dependency management
- **Headless/Headed**: Works in GCP Cloud Shell (headless) or local dev (headed)
- **Arize Phoenix**: OpenTelemetry-based observability and tracing
- **Pytest Integration**: ADK evaluation format adapted for pytest regression tests

## Quick Start

### Prerequisites

- Python 3.12+
- `uv` package manager (recommended, auto-installed via Makefile)
- Docker (for Phoenix and Playwright MCP container)
- Node.js 18+ (for Playwright MCP, installed in Docker container)
- GCP account with Vertex AI enabled (or Google AI Studio API key)

### Installation

```bash
# Clone and enter the project
cd gui-agent

# Install dependencies with uv (recommended)
make install-dev

# Or install uv and dependencies manually
pip install uv
uv sync --extra dev --extra mock-server

# Copy and configure environment
make setup-env
# Edit .env with your credentials
```

### GCP Cloud Shell Setup

For GCP Cloud Shell, run the setup script:

```bash
./scripts/setup_gcp.sh
```

This will:
- Verify Python version
- Install dependencies
- Configure gcloud authentication
- Enable Vertex AI API
- Create `.env` with your project settings

### Running the Agent

1. **Start all services** (Phoenix + Playwright MCP):
   ```bash
   make start-services
   # View Phoenix traces at http://localhost:6006
   # Playwright MCP available at http://localhost:8931
   ```

   Or start services individually:
   ```bash
   # Start only Phoenix
   docker compose up -d phoenix

   # Start Playwright MCP
   docker compose up -d playwright-mcp
   ```

2. **Run the agent**:
   ```bash
   # Interactive mode (headless)
   make run-headless

   # Interactive mode (headed - local dev only)
   make run-headed

   # Or use scripts directly
   ./scripts/run_headless.sh "Navigate to example.com and take a screenshot"
   ```

## @playwright/mcp Ref-Based Workflow

The official `@playwright/mcp` uses a **ref-based** approach for element interaction:

1. **Get Snapshot**: Call `browser_snapshot` to get the accessibility tree with element refs
2. **Find Refs**: Elements have refs like `[ref=e1]`, `[ref=e2]`, etc.
3. **Use Refs**: Pass the ref to interaction tools like `browser_click`, `browser_type`

### Example Workflow
```
1. browser_navigate(url="https://example.com/form")
2. browser_snapshot()
   # Returns: "- textbox 'First Name' [ref=e3]..."
3. browser_type(ref="e3", text="John")
4. browser_snapshot()  # Get updated refs
5. browser_click(ref="e5")  # Submit button
```

### Available Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `browser_navigate` | `url` | Navigate to URL |
| `browser_snapshot` | - | Get accessibility tree with refs |
| `browser_take_screenshot` | `type`, `filename?`, `element?`, `ref?`, `fullPage?` | Take screenshot |
| `browser_click` | `ref`, `button?`, `double_click?` | Click element |
| `browser_type` | `ref`, `text`, `submit?` | Type into element |
| `browser_hover` | `ref` | Hover over element |
| `browser_select_option` | `ref`, `values[]` | Select dropdown option(s) |
| `browser_press_key` | `key` | Press keyboard key |
| `browser_wait_for` | `selector`, `state?` | Wait for element |
| `browser_go_back` | - | Navigate back |
| `browser_go_forward` | - | Navigate forward |

## Authentication

The agent supports two authentication methods:

### Option 1: Google AI Studio (Development)

Set `GOOGLE_API_KEY` in your `.env`:

```bash
GOOGLE_API_KEY=your-api-key-here
```

### Option 2: Vertex AI (Production)

Configure these variables (used when `GOOGLE_API_KEY` is not set):

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

Authenticate with gcloud:
```bash
gcloud auth application-default login
```

## Project Structure

```
adk-gui-agent/
├── gui_agent_v1/           # Agent v1 (future versions: gui_agent_v2/, etc.)
│   ├── agent.py            # ADK agent definition + root_agent export
│   ├── config.py           # Pydantic settings with auth fallback
│   ├── observability.py    # Phoenix/OTEL tracing setup
│   ├── cli.py              # Command-line interface
│   ├── evals/              # ADK evaluation sets (co-located with agent)
│   │   ├── basic.evalset.json
│   │   ├── simple.evalset.json
│   │   └── complex.evalset.json
│   ├── screenshots/        # Auto-saved screenshots (timestamped)
│   └── prompts/
│       └── system.py       # System prompts (ref-based workflow)
├── tests/
│   ├── conftest.py         # Pytest fixtures
│   ├── test_agent.py       # Agent + eval set tests
│   └── test_config.py      # Config tests
├── mock_sites/             # Test form websites
│   ├── server.py           # FastAPI server
│   └── templates/          # HTML forms
├── scripts/                # Runner scripts
│   ├── run_headless.sh
│   ├── run_headed.sh
│   └── setup_gcp.sh
├── docker-compose.yml      # Phoenix + Playwright MCP + Mock server
├── Makefile                # Common commands (uses uv)
├── pyproject.toml          # Python dependencies
├── README.md               # This file
└── AGENTS.md               # Project context for AI agents
```

## Mock Test Forms

The project includes mock forms for testing:

| Form | URL | Difficulty | Description |
|------|-----|------------|-------------|
| Simple Contact | `/simple` | Easy | 6 fields, basic validation |
| Employee Onboarding | `/complex` | Hard | 15+ fields, multi-step, conditional |

Start the mock server:
```bash
# Start mock server in Docker
make start-mock-server
# Access at http://localhost:8080

# Or run locally with uv
make mock-server
```

### Recommended Public Test Site

For "in-the-wild" testing, consider:
- **httpbin.org/forms/post** - Simple form for testing
- **the-internet.herokuapp.com/login** - Login form testing
- **automationexercise.com** - E-commerce site with registration/checkout flows

## Testing

All test commands use `uv` for dependency management:

```bash
# Run all tests
make test

# Run fast tests (no external services)
make test-fast

# Run integration tests (requires services)
make test-integration

# Run ADK evaluation tests
make test-evalset

# With coverage report
make test-cov

# Or run tests directly with uv
uv run pytest tests/ -v
```

### Evaluation Format

Tests use ADK's evaluation format adapted for pytest. See `gui_agent_v1/evals/simple.evalset.json` for examples:

```json
{
  "eval_set_id": "form_filling_basic_v1",
  "eval_cases": [
    {
      "eval_case_id": "simple_form_complete",
      "conversation": [{"role": "user", "content": "..."}],
      "expected_tool_calls": [
        {"tool_name": "browser_navigate", "arguments": {"url": "..."}},
        {"tool_name": "browser_snapshot"},
        {"tool_name": "browser_type", "arguments": {"ref": "DYNAMIC", "text": "John"}}
      ]
    }
  ]
}
```

Note: `ref` values are marked as `"DYNAMIC"` since they are assigned at runtime by `browser_snapshot`.

## Observability

Traces are sent to Arize Phoenix via OpenTelemetry:

1. Start services: `make start-services`
2. Run agent with tracing enabled (check `ENABLE_TRACING=true` in `.env`)
3. View traces: http://localhost:6006

Traces include:
- Gemini API calls (input/output tokens, latency)
- Tool calls (Playwright actions)
- Agent reasoning steps

## Roadmap

### MVP0 (Current)
- [x] ADK agent with Gemini 2.5 Flash
- [x] @playwright/mcp integration (ref-based)
- [x] Docker-based service orchestration
- [x] Simple form filling
- [x] Phoenix observability
- [x] Basic pytest regression tests
- [x] Headless mode for GCP Cloud Shell
- [x] uv package manager integration

### MVP1 (Planned)
- [ ] Complex multi-step forms
- [ ] Screenshot-based verification
- [ ] Error recovery strategies
- [ ] More comprehensive eval sets

### MVP2 (Future)
- [ ] Browser abstraction layer (Selenium/Puppeteer alternatives)
- [ ] Multi-agent orchestration
- [ ] Cloud deployment (Vertex AI Agent Engine)
- [ ] CI/CD pipeline with regression tests

## Troubleshooting

### Playwright MCP not connecting

```bash
# Check if server is running (default port is 8931)
curl http://localhost:8931/sse

# Restart the Docker service
docker compose restart playwright-mcp

# Check logs
docker logs gui-agent-playwright
```

### Vertex AI authentication errors

```bash
# Re-authenticate
gcloud auth application-default login

# Verify project
gcloud config get-value project

# Check API is enabled
gcloud services list --enabled | grep aiplatform
```

### Phoenix not receiving traces

```bash
# Check Phoenix is running
docker compose logs phoenix

# Check Phoenix health
curl http://localhost:6006/health

# Verify endpoint in .env
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
ENABLE_TRACING=true

# Restart Phoenix
docker compose restart phoenix
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run `make lint` and `make test`
5. Submit a pull request
