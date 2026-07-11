PYTHON ?= python3
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip
URP := $(VENV)/bin/urp

.PHONY: setup quick-check check test lint readiness sdk rust docs docs-serve whitepaper demo impact metadata release-verify dev-env compose-up compose-down clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

quick-check: lint test readiness

check: quick-check sdk rust docs release-verify

test:
	$(PY) -m pytest -W error::ResourceWarning --cov=urp --cov-report=term-missing --cov-fail-under=70

lint:
	$(PY) -m ruff check python tests

readiness:
	$(URP) admin readiness
	$(URP) platform validate --target all

sdk:
	npm ci --prefix typescript
	npm test --prefix typescript
	cd go && go test -race ./...

rust:
	cargo fmt --all -- --check
	cargo clippy --workspace --all-targets -- -D warnings
	cargo test --workspace

docs:
	$(PIP) install -r requirements-docs.txt
	$(PY) -m mkdocs build --strict

docs-serve:
	$(PIP) install -r requirements-docs.txt
	$(PY) -m mkdocs serve --dev-addr 127.0.0.1:8000

whitepaper:
	$(PIP) install -r requirements-publication.txt
	$(PY) scripts/render_whitepaper.py

demo:
	$(PY) examples/live/run_live_examples.py --reset

impact:
	$(URP) report impact --scenario examples/impact/illustrative-portfolio.json

metadata:
	$(URP) release metadata --root .
	$(URP) release sign --output PACKAGE_SHA256.json

release-verify:
	$(URP) release verify --manifest PACKAGE_SHA256.json --root .

dev-env:
	./scripts/generate-dev-env.sh

compose-up:
	docker compose -f deployments/docker-compose/docker-compose.yaml up --build

compose-down:
	docker compose -f deployments/docker-compose/docker-compose.yaml down

clean:
	rm -rf build dist site htmlcov .coverage .pytest_cache .ruff_cache
