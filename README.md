# GUI Agent Prototype

A form-filling GUI agent built with Google's Agent Development Kit (ADK), using Playwright MCP tools and Arize Phoenix for observability.

## Features

- **ADK Framework**: Built on Google's Agent Development Kit for structured agent development
- **Gemini LLM**: Uses Gemini 2.5 Flash via Vertex AI or Google AI Studio
- **Playwright MCP**: Browser automation through Model Context Protocol
- **Headless/Headed**: Works in GCP Cloud Shell (headless) or local dev (headed)
- **Arize Phoenix**: OpenTelemetry-based observability and tracing
- **Pytest Integration**: ADK evaluation format adapted for pytest regression tests

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for Phoenix and optional Playwright MCP container)
- Node.js 18+ (for Playwright MCP)
- GCP account with Vertex AI enabled (or Google AI Studio API key)

### Installation

```bash
# Clone and enter the project
cd gui-agent

# Install dependencies
pip install -e ".[dev,mock-server]"

# Copy and configure environment
cp .env.example .env
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

1. **Start Playwright MCP server**:
   ```bash
   npx @anthropic-ai/mcp-server-playwright --port 3000
   ```

2. **Start Phoenix (optional, for tracing)**:
   ```bash
   docker compose up -d phoenix
   # View traces at http://localhost:6006
   ```

3. **Run the agent**:
   ```bash
   # Interactive mode
   ./scripts/run_headless.sh

   # Single task
   ./scripts/run_headless.sh "Navigate to example.com and take a screenshot"

   # Or use make
   make run-headless
   ```

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
gui-agent/
├── src/gui_agent/
│   ├── agent.py          # ADK agent definition
│   ├── config.py         # Pydantic settings with auth fallback
│   ├── observability.py  # Phoenix/OTEL tracing setup
│   ├── cli.py            # Command-line interface
│   └── prompts/          # System prompts
├── tests/
│   ├── conftest.py       # Pytest fixtures
│   ├── evalsets/         # ADK evaluation datasets
│   └── test_*.py         # Test files
├── mock_sites/           # Test form websites
│   ├── server.py         # FastAPI server
│   └── templates/        # HTML forms
├── scripts/              # Runner scripts
├── docker-compose.yml    # Phoenix + Playwright services
└── Makefile             # Common commands
```

## Mock Test Forms

The project includes mock forms for testing:

| Form | URL | Difficulty | Description |
|------|-----|------------|-------------|
| Simple Contact | `/simple` | Easy | 6 fields, basic validation |
| Employee Onboarding | `/complex` | Hard | 15+ fields, multi-step, conditional |

Start the mock server:
```bash
make mock-server
# Access at http://localhost:8080
```

### Recommended Public Test Site

For "in-the-wild" testing, consider:
- **httpbin.org/forms/post** - Simple form for testing
- **the-internet.herokuapp.com/login** - Login form testing
- **automationexercise.com** - E-commerce site with registration/checkout flows

## Testing

```bash
# Run fast tests (no external services)
make test-fast

# Run all tests
make test

# Run integration tests (requires services)
make test-integration

# Run ADK evaluation tests
make test-evalset

# With coverage
make test-cov
```

### Evaluation Format

Tests use ADK's evaluation format adapted for pytest. See `tests/evalsets/` for examples:

```json
{
  "eval_set_id": "form_filling_basic_v1",
  "eval_cases": [
    {
      "eval_case_id": "simple_form_complete",
      "conversation": [{"role": "user", "content": "..."}],
      "expected_tool_calls": [
        {"tool_name": "browser_navigate", "arguments": {...}},
        {"tool_name": "browser_type", "arguments": {...}}
      ]
    }
  ]
}
```

## Observability

Traces are sent to Arize Phoenix via OpenTelemetry:

1. Start Phoenix: `docker compose up -d phoenix`
2. Run agent with tracing: `ENABLE_TRACING=true ./scripts/run_headless.sh`
3. View traces: http://localhost:6006

Traces include:
- Gemini API calls (input/output tokens, latency)
- Tool calls (Playwright actions)
- Agent reasoning steps

## Roadmap

### MVP0 (Current)
- [x] ADK agent with Gemini
- [x] Playwright MCP integration
- [x] Simple form filling
- [x] Phoenix observability
- [x] Basic pytest regression tests
- [x] Headless mode for GCP

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
# Check if server is running
curl http://localhost:3000/health

# Restart the server
npx @anthropic-ai/mcp-server-playwright --port 3000
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

# Verify endpoint in .env
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run `make lint` and `make test`
5. Submit a pull request
