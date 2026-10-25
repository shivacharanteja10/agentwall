.PHONY: help install dev test lint format build up down logs clean

# Default target
help:
	@echo "AgentWall - Zero-trust security gateway for AI agents"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install     Install all dependencies (Python + Node)"
	@echo "  dev         Start development environment with Docker Compose"
	@echo "  dev-local   Start services locally (requires Python, Node, PostgreSQL, Redis)"
	@echo "  test        Run all tests"
	@echo "  test-gateway Run gateway tests only"
	@echo "  test-dashboard Run dashboard tests only"
	@echo "  lint        Run linters (ruff, mypy, eslint)"
	@echo "  format      Format code (ruff, prettier)"
	@echo "  build       Build Docker images"
	@echo "  up          Start all services with Docker Compose"
	@echo "  down        Stop all services"
	@echo "  logs        View logs from all services"
	@echo "  clean       Clean up build artifacts and containers"
	@echo "  eval        Run red-team evaluation"
	@echo "  bench       Run load benchmarks"
	@echo "  demo        Run attack demo"

# Install dependencies
install:
	cd gateway && pip install -e ".[dev]"
	cd tool_servers/filesystem && pip install -r requirements.txt
	cd tool_servers/database && pip install -r requirements.txt
	cd tool_servers/web_fetch && pip install -r requirements.txt
	cd dashboard && npm ci

# Development with Docker Compose
dev:
	docker compose up --build

# Development locally (requires services running)
dev-local:
	@echo "Starting gateway on http://localhost:8000"
	cd gateway && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test: test-gateway test-dashboard

test-gateway:
	cd gateway && pytest -v --cov=app --cov-report=term-missing

test-dashboard:
	cd dashboard && npm run lint

# Linting
lint:
	cd gateway && ruff check app/
	cd gateway && mypy app/
	cd dashboard && npm run lint

# Formatting
format:
	cd gateway && ruff check --fix app/
	cd gateway && ruff format app/
	cd dashboard && npx prettier --write src/

# Docker
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# Cleanup
clean:
	docker compose down -v
	rm -rf gateway/.pytest_cache gateway/__pycache__ gateway/app/__pycache__
	rm -rf dashboard/node_modules dashboard/dist dashboard/.vite
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Red-team evaluation
eval:
	cd gateway && python -m evaluation.run_evaluation

# Load benchmark
bench:
	cd gateway && locust -f benchmarks/locustfile.py --headless -u 50 -r 10 -t 60s --host=http://localhost:8000

# Attack demo
demo:
	cd gateway && python -m demo.run_demo

# Database migrations
migrate:
	cd gateway && alembic upgrade head

migrate-create:
	@read -p "Migration message: " msg; \
	cd gateway && alembic revision --autogenerate -m "$$msg"

# Generate API key for admin
gen-key:
	@cd gateway && python -c "from app.core.security import generate_api_key; print(generate_api_key())"

# Verify audit chain
verify-audit:
	cd gateway && python -m scripts.verify_audit_chain