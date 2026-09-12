.PHONY: help build up down dev test test-critical test-unit test-integration test-sumo test-backend test-frontend test-e2e lint format migrate smoke check-phase0 verify-determinism verify-full-chain clean

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

test: test-critical test-frontend

test-critical:
	@if [ -f .venv/bin/pytest ]; then .venv/bin/pytest tests/critical/ -v; else pytest tests/critical/ -v; fi

test-unit:
	@if [ -f .venv/bin/pytest ]; then .venv/bin/pytest tests/critical/test_04_telemetry_ingest.py tests/critical/test_07_safety_envelope.py tests/critical/test_13_provenance.py tests/critical/test_15_ab_reproducibility.py -v; else pytest tests/critical/test_04_telemetry_ingest.py tests/critical/test_07_safety_envelope.py tests/critical/test_13_provenance.py tests/critical/test_15_ab_reproducibility.py -v; fi

test-integration:
	@if [ -f .venv/bin/pytest ]; then .venv/bin/pytest tests/critical/test_01_auth.py tests/critical/test_02_rbac.py tests/critical/test_03_public_exposure.py tests/critical/test_08_emergency_corridor.py tests/critical/test_10_citizen_advisory.py tests/critical/test_12_incident_gate.py tests/critical/test_13_incident_system.py tests/critical/test_14_audit.py -v; else pytest tests/critical/test_01_auth.py tests/critical/test_02_rbac.py tests/critical/test_03_public_exposure.py tests/critical/test_08_emergency_corridor.py tests/critical/test_10_citizen_advisory.py tests/critical/test_12_incident_gate.py tests/critical/test_13_incident_system.py tests/critical/test_14_audit.py -v; fi

test-sumo:
	@if [ -f .venv/bin/pytest ]; then .venv/bin/pytest tests/critical/ -m sumo -v; else pytest tests/critical/ -m sumo -v; fi

test-backend:
	@if docker ps --format '{{.Names}}' | grep -q '^surakshanet-backend$$'; then \
		docker exec surakshanet-backend pytest tests/test_alerts.py tests/test_antigravity.py tests/test_auth.py tests/test_marl.py tests/test_ml.py tests/test_pcu_engine.py tests/test_routing.py tests/test_rtsp_worker.py tests/test_signal_bridge.py tests/test_signals.py tests/test_spatial.py tests/test_traffic.py -v; \
	elif [ -f .venv/bin/pytest ]; then \
		.venv/bin/pytest backend/tests/ -v; \
	else \
		pytest backend/tests/ -v; \
	fi

test-frontend:
	npm --prefix frontend/dashboard test

test-e2e:
	docker exec -e PYTHONPATH=/app -e PROJECT_ROOT=/app -e E2E_BACKEND_URL=http://127.0.0.1:8000 surakshanet-backend python tests/e2e/run_e2e_tests.py --tier all

check-phase0:
	./scripts/check_phase0_regressions.sh

verify-determinism:
	@if [ -f .venv/bin/python3 ]; then .venv/bin/python3 scripts/verify_determinism.py; else python3 scripts/verify_determinism.py; fi

verify-full-chain:
	@if [ -f .venv/bin/python3 ]; then .venv/bin/python3 scripts/verify_full_chain.py; else python3 scripts/verify_full_chain.py; fi

lint:
	@if docker ps --format '{{.Names}}' | grep -q '^surakshanet-backend$$'; then \
		docker exec surakshanet-backend ruff check app/; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check backend/app/; \
	elif [ -x /home/alok/.local/bin/ruff ]; then \
		/home/alok/.local/bin/ruff check backend/app/; \
	fi
	npm --prefix frontend/dashboard run build

format:
	docker exec surakshanet-backend ruff format app/

migrate:
	docker exec surakshanet-backend alembic upgrade head

smoke:
	docker exec surakshanet-backend /app/scripts/smoke_check.sh http://127.0.0.1:8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/dashboard/dist
