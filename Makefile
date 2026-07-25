# Makefile — Sierra Chart Trade Optimization Platform
# Usage: make <target>
# Requires: Python 3.11+, Node 18+, Docker

.PHONY: dev backend frontend test test-unit test-integration lint \
        migrate migrate-rollback migrate-create \
        docker-up docker-down docker-prod \
        import walkforward permutation-test oos promote \
        clean generate-types

# ── Development ──────────────────────────────────────────────────────────────

dev:
	@echo "Starting backend + frontend..."
	@start cmd /k "make backend"
	@start cmd /k "make frontend"

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v --cov=backend --cov-report=term-missing --cov-fail-under=70

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -x

# ── Linting ───────────────────────────────────────────────────────────────────

lint:
	cd backend && python -m ruff check . && python -m mypy . --ignore-missing-imports
	cd frontend && npm run lint

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	cd backend && alembic upgrade head

migrate-rollback:
	cd backend && alembic downgrade -1

migrate-create:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# ── Pipeline Operations ───────────────────────────────────────────────────────

import:
	python scripts/run_full_import.py

walkforward:
	python scripts/run_walk_forward_test.py

permutation-test:
	python scripts/run_permutation_test.py

oos:
	python scripts/run_out_of_sample_audit.py

promote:
	python scripts/promote_clean_data_to_production.py

ingest:
	curl -X POST http://localhost:8000/api/v1/ingest -H "Content-Type: application/json" \
	  -d "{\"data_dir\": \"$(DIR)\"}"

# ── Frontend Tooling ──────────────────────────────────────────────────────────

generate-types:
	cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker-compose -f infra/docker-compose.yml up --build

docker-down:
	docker-compose -f infra/docker-compose.yml down

docker-prod:
	docker-compose -f infra/docker-compose.prod.yml up -d

# -- Cleanup ------------------------------------------------------------------

clean:
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	if exist .pytest_cache rd /s /q .pytest_cache
	if exist backend\.mypy_cache rd /s /q backend\.mypy_cache
