.PHONY: help build up down dev test test-backend test-frontend test-e2e lint format migrate smoke clean

help:
	@echo "Surakshanet ITS - Development & Operations Commands"
	@echo ""
	@echo "Targets:"
	@echo "  build         Build Docker images for all services"
	@echo "  up            Start all services in background via docker-compose"
	@echo "  down          Stop all running services"
	@echo "  dev           Alias for 'up'"
	@echo "  test          Run full test suite (backend + frontend)"
	@echo "  test-backend  Run backend pytest suite"
	@echo "  test-frontend Run frontend vitest suite"
	@echo "  test-e2e      Run unified E2E test suite"
	@echo "  lint          Run code linters (ruff, flake8, tsc)"
	@echo "  format        Format code using ruff"
	@echo "  migrate       Apply Alembic database migrations"
	@echo "  smoke         Run deployment smoke checks"
	@echo "  clean         Remove pycache, build artifacts, and caches"

build:
	docker compose -f infra/docker-compose.yml build

up:
	docker compose -f infra/docker-compose.yml up -d

dev: up

down:
	docker compose -f infra/docker-compose.yml down

test: test-backend test-frontend

test-backend:
	docker exec surakshanet-backend pytest tests/test_alerts.py tests/test_auth.py tests/test_marl.py tests/test_ml.py tests/test_pcu_engine.py tests/test_routing.py tests/test_rtsp_worker.py tests/test_signal_bridge.py tests/test_signals.py tests/test_spatial.py tests/test_traffic.py -v

test-frontend:
	npm --prefix frontend/dashboard test

test-e2e:
	docker exec -e PYTHONPATH=/app -e PROJECT_ROOT=/app -e E2E_BACKEND_URL=http://127.0.0.1:8000 surakshanet-backend python tests/e2e/run_e2e_tests.py --tier all

check-phase0:
	./scripts/check_phase0_regressions.sh

lint:
	docker exec surakshanet-backend ruff check app/
	npm --prefix frontend/dashboard run build

format:
	docker exec surakshanet-backend ruff format app/

migrate:
	docker exec surakshanet-backend alembic upgrade head

smoke:
	docker exec surakshanet-backend /app/scripts/smoke_check.sh http://127.0.0.1:8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf frontend/dashboard/dist
