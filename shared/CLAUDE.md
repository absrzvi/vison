# CLAUDE.md — shared

Python package (`oebb-shared`) containing cross-service primitives: Pydantic v2 event schemas, structured logging setup, retry helpers, and WebSocket/HTTP adapters consumed by cloud-backend and event-store.

## Stack

- Python 3.11+, strict mypy
- Pydantic v2 for all schemas (no v1 compat shims)
- structlog for structured logging
- tenacity for retry logic
- No FastAPI dependency — this package must remain framework-agnostic

## Commands

```bash
cd shared
pip install -e ".[dev]"   # install with dev extras
python -m pytest          # all tests
python -m pytest -m unit  # unit only (fast, no I/O)
python -m ruff check src/ # lint
python -m mypy src/        # type check
```

Coverage threshold: 80% (`fail_under = 80` in pyproject.toml).

## Module Layout

```
src/oebb_shared/
  adapters/   — HTTP + WebSocket client adapters
  events/     — Pydantic event schema definitions (canonical source of truth)
  http/       — shared HTTP helpers
  ws/         — WebSocket helpers
```

## File Conventions

- One module per concern — no "utils.py" catch-alls
- All public types exported from `oebb_shared/__init__.py`
- Test markers: `unit` (no I/O), `integration` (real adapters), `contract` (schema compat)

## What NOT to Touch

- Do not add FastAPI, SQLAlchemy, or any service-specific dependency
- Do not change event schema field names without a contract test update — cloud-backend and event-store both deserialise these
- `src/oebb_shared.egg-info/` — generated; never edit

## Key Patterns

Schema changes must be backwards-compatible or versioned. Add a `contract` test any time a field is renamed, removed, or its type changes. The `contract` marker runs in CI to catch breaking changes before they propagate to dependent services.
