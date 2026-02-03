.PHONY: help install install-dev install-uv setup-env start-services stop-services \
        run run-headless run-headed test test-fast test-integration \
        lint format typecheck mock-server clean video-stats video-clean video-convert

# Default target
help:
	@echo "GUI Agent - Available Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup:"
	@echo "  make install-uv     Install uv package manager (recommended)"
	@echo "  make install        Install production dependencies (with uv)"
	@echo "  make install-dev    Install development dependencies (with uv)"
	@echo "  make setup-env      Copy .env.example to .env"
	@echo ""
	@echo "Services:"
	@echo "  make start-services Start Phoenix + Playwright MCP (Docker)"
	@echo "  make stop-services  Stop all Docker services"
	@echo "  make mock-server    Start the mock form website"
	@echo ""
	@echo "Run Agent:"
	@echo "  make run            Run agent (uses BROWSER_HEADLESS from .env)"
	@echo "  make run-headless   Run agent in headless mode (GCP Cloud Shell)"
	@echo "  make run-headed     Run agent in headed mode (local dev)"
	@echo "  make adk-web        Start ADK web interface"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-fast      Run fast tests only (skip slow/integration)"
	@echo "  make test-integration  Run integration tests"
	@echo "  make test-evalset   Run ADK evaluation tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linter (ruff)"
	@echo "  make format         Format code (ruff)"
	@echo "  make typecheck      Run type checker (mypy)"
	@echo ""
	@echo "Video Recording:"
	@echo "  make video-stats    Show video recording statistics"
	@echo "  make video-clean    Clean up old recordings"
	@echo "  make video-convert  Convert all WebM recordings to MP4"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove build artifacts and caches"

# =============================================================================
# Setup
# =============================================================================

install-uv:
	@command -v uv >/dev/null 2>&1 || { \
		echo "Installing uv..."; \
		pip install uv; \
	}
	@echo "uv is installed"

install: install-uv
	uv sync

install-dev: install-uv
	uv sync --extra dev --extra mock-server

setup-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example - please edit with your values"; \
	else \
		echo ".env already exists"; \
	fi

# =============================================================================
# Docker Services
# =============================================================================

start-services:
	docker compose up -d
	@echo "Services starting..."
	@echo "  Phoenix UI: http://localhost:6006"
	@echo "  Playwright MCP: http://localhost:8931"

start-mock-server:
	docker compose --profile testing up -d mock-server
	@echo "Starting mock server..."
	@echo "  Mock server: http://mockserver:8080"

stop-services:
	docker compose down

logs:
	docker compose logs -f

# =============================================================================
# Run Agent
# =============================================================================

run:
	uv run python -m gui_agent.cli

run-headless:
	BROWSER_HEADLESS=true uv run python -m gui_agent.cli

run-headed:
	BROWSER_HEADLESS=false uv run python -m gui_agent.cli

adk-web:
	uv run adk web src/gui_agent

# =============================================================================
# Mock Server
# =============================================================================

mock-server: install-uv
	@command -v uvicorn >/dev/null 2>&1 || { \
		echo "Installing mock-server dependencies..."; \
		uv sync --extra mock-server; \
	}
	uv run uvicorn mock_sites.server:app --host 0.0.0.0 --port 8080 --reload

# =============================================================================
# Testing
# =============================================================================

test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -v -m "not slow and not integration"

test-integration:
	uv run pytest tests/ -v -m "integration"

test-evalset:
	uv run pytest tests/ -v -m "evalset"

test-cov:
	uv run pytest tests/ -v --cov=src/gui_agent --cov-report=html --cov-report=term

# =============================================================================
# Code Quality
# =============================================================================

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	uv run mypy src/

# =============================================================================
# Video Recording
# =============================================================================

video-stats:
	@echo "📊 Video Recording Statistics"
	@if [ -d "recordings" ]; then \
		ls -lh recordings/ 2>/dev/null | grep "session_" || echo "No recordings found"; \
		echo ""; \
		uv run python -c "from gui_agent.video import VideoManager; from gui_agent.config import get_settings; stats = VideoManager(get_settings()).get_recording_stats(); print(f\"Total: {stats['count']} files, {stats['total_size_mb']} MB\")"; \
	else \
		echo "No recordings directory found"; \
	fi

video-clean:
	@echo "🗑️  Cleaning old recordings..."
	@uv run python -c "from gui_agent.video import VideoManager; from gui_agent.config import get_settings; deleted = VideoManager(get_settings()).cleanup_old_recordings(); print(f'Deleted {deleted} old recordings')"

video-convert:
	@echo "🎬 Converting WebM recordings to MP4..."
	@for file in recordings/*.webm 2>/dev/null; do \
		if [ -f "$$file" ]; then \
			echo "Converting $$file..."; \
			ffmpeg -i "$$file" -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k "$${file%.webm}.mp4" -y 2>/dev/null && \
			echo "✅ Created $${file%.webm}.mp4"; \
		fi \
	done || echo "No WebM files found or ffmpeg not available"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
