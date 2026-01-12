# turbo-orm justfile

set shell := ["bash", "-c"]

# Unset conflicting VIRTUAL_ENV
export VIRTUAL_ENV := ""

# Default recipe - show available commands
default:
    @just --list

# Install the package in development mode
install:
    uv sync --all-groups

# Run all tests
test:
    uv run pytest tests/ -v

# Run tests with coverage
test-cov:
    uv run pytest tests/ --cov=src/turbo_orm --cov-report=html --cov-report=term

# Run a specific test file
test-file file:
    uv run pytest {{file}} -v

# Format code with ruff
fmt:
    uv run ruff format src tests

# Check formatting without modifying
fmt-check:
    uv run ruff format --check src tests

# Lint with ruff
lint:
    uv run ruff check src tests

# Lint and fix issues
lint-fix:
    uv run ruff check --fix src tests

# Run all checks (format + lint)
check: fmt-check lint

# Clean build artifacts
clean:
    rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov .ruff_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Build the package
build: clean
    uv build

# Start PostgreSQL for testing
db-up:
    docker run -d --name turbo-orm-postgres \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=turbo_orm_test \
        -p 5432:5432 \
        postgres:16
    @echo "Waiting for PostgreSQL..."
    @sleep 3

# Stop PostgreSQL
db-down:
    docker stop turbo-orm-postgres && docker rm turbo-orm-postgres || true

# Run sample project server
sample-run:
    cd ignore/sample_project && uv run python manage.py runserver

# CI simulation - run full CI locally
ci: check test

# Show package version
version:
    @uv run python -c "from turbo_orm import __version__; print(__version__)"

# Update all dependencies
update:
    uv sync --upgrade

# Lock dependencies
lock:
    uv lock
