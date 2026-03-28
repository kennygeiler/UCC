# Bootstrap Context — Iteration 2

## Rakim (codebase state)
Current milestone: M1 Foundation, Database, and CI/CD. 7/14 deliverables complete from iteration 1. Remaining: service entry points, health checks, Procfile/railway.toml, CI workflow, Sentry init, tests, .env.example. Key existing files: pyproject.toml, app/config.py, app/db.py, app/logging.py, app/models/ (13 tables), app/services/job_queue.py, alembic.ini, migrations/, tests/conftest.py, tests/unit/ (5 test files).

## Sentinel (patterns/pitfalls)
Key patterns for this iteration: P-013 watchdog zero-import isolation (C-07), P-016 Sentry init before app code, P-018 health check endpoints on all services, P-001 function length <50 lines. Key pitfall: PF-003 watchdog importing from app/ silently breaks independence guarantee.
