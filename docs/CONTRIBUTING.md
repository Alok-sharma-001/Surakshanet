# Contributing to Surakshanet

Thank you for contributing to Surakshanet Intelligent Transportation System (ITS). This document details guidelines for local setup, development workflows, and pull request procedures.

---

## Code of Conduct & Security Hygiene

1. **Never Commit Secrets:** Do not commit private keys (`*.pem`, `*.key`), certificates (`*.crt`), or production passwords. Pre-commit hooks will reject any commits containing target secret patterns.
2. **Deterministic Reproducibility:** Any ML training algorithms, simulation runs, or benchmarks must support deterministic seeding.
3. **Strict Type Safety:** Avoid unbounded `any` types in TypeScript and enforce strict Pydantic v2 schemas on Python endpoints.

---

## Local Development Setup

### Prerequisites
- Docker & Docker Compose (v2.20+)
- Python 3.11+
- Node.js 18+ (Node 20 recommended)
- `make` utility

### Initializing the Workspace

```bash
# 1. Clone the repository
git clone https://github.com/Alok-sharma-001/Surakshanet.git
cd Surakshanet

# 2. Configure local environment
cp .env.example .env

# 3. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 4. Start infrastructure services (TimescaleDB, Redis, Mosquitto, Backend)
make up

# 5. Apply Alembic database migrations
make migrate

# 6. Verify stack health
make smoke
```

---

## Development Workflow & Verification

Before submitting a pull request, ensure all test suites and linters pass:

```bash
# Run full automated test suite (backend pytest + frontend unit tests)
make test

# Run backend unit tests
make test-backend

# Run frontend unit tests
make test-frontend

# Run unified 4-tier E2E integration harness
make test-e2e

# Run code formatters and linters
make lint
make format
```

---

## Pull Request Guidelines

1. **Branch Naming:** Use descriptive branch prefixes: `feat/*`, `fix/*`, `refactor/*`, `docs/*`.
2. **Commit Messages:** Follow Conventional Commits format:
   - `feat(traffic): implement PostGIS spatial bounding box query`
   - `fix(auth): enforce operator role upon user self-registration`
3. **Automated CI:** All PRs must pass the GitHub Actions CI pipeline, including linting (`ruff`), type-checking (`mypy`, `tsc`), Alembic migrations, and 100% test pass rate.
