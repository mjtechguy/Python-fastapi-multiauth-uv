.PHONY: help install dev-install test lint format security run docker-up docker-down migrate revision clean

help:
	@echo "Available commands:"
	@echo "  install       - Install production dependencies with UV"
	@echo "  dev-install   - Install all dependencies including dev with UV"
	@echo "  test          - Run tests with pytest"
	@echo "  lint          - Run linting with ruff"
	@echo "  format        - Format code with black and ruff"
	@echo "  security      - Run security checks with bandit and safety"
	@echo "  run           - Run the FastAPI application"
	@echo "  docker-up     - Start all services with docker-compose"
	@echo "  docker-down   - Stop all services"
	@echo "  migrate       - Run database migrations"
	@echo "  revision      - Create new migration revision"
	@echo "  clean         - Clean up generated files"

install:
	uv pip install -r pyproject.toml

dev-install:
	uv pip install -r pyproject.toml --extra dev

test:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing

lint:
	ruff check app/ tests/
	mypy app/

format:
	black app/ tests/
	ruff check --fix app/ tests/

security:
	bandit -r app/ -ll
	safety check

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(message)"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov/ .ruff_cache .mypy_cache
