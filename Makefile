# ─────────────────────────────────────────────────────────────────────────────
# ShopSignal Makefile
# Provides short, memorable commands for common development tasks.
# Usage:  make <target>
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
PYTHON        := python
PIP           := pip
RUFF          := ruff
PYTEST        := pytest
DOCKER        := docker
IMAGE_NAME    := shopsignal-api
IMAGE_TAG     := local

.PHONY: help install install-dev lint format format-check test test-unit test-smoke \
        docker-build docker-run clean

help:           ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Environment ──────────────────────────────────────────────────────────────
install:        ## Install runtime dependencies
	$(PIP) install -r requirements.txt

install-dev:    ## Install runtime + dev dependencies
	$(PIP) install -r requirements.txt -e ".[dev]"

# ── Code quality ─────────────────────────────────────────────────────────────
lint:           ## Run Ruff linter (errors only)
	$(RUFF) check src tests pipelines

format:         ## Auto-format code with Ruff
	$(RUFF) format src tests pipelines

format-check:   ## Check formatting without modifying files (used in CI)
	$(RUFF) format --check src tests pipelines

# ── Tests ─────────────────────────────────────────────────────────────────────
test:           ## Run all tests with coverage
	$(PYTEST) tests/ -v --cov=src --cov-report=term-missing

test-unit:      ## Run only unit tests
	$(PYTEST) tests/unit/ -v -m unit

test-smoke:     ## Run API smoke tests (requires running server or TestClient)
	$(PYTEST) tests/smoke/ -v -m smoke

# ── Docker ───────────────────────────────────────────────────────────────────
docker-build:   ## Build the Docker image locally
	$(DOCKER) build -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-run:     ## Run the API container locally on port 8080
	$(DOCKER) run --rm -p 8080:8080 \
	  --env-file .env \
	  $(IMAGE_NAME):$(IMAGE_TAG)

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:          ## Remove Python caches and build artefacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov .coverage coverage.xml dist build *.egg-info
	@echo "Clean complete."
