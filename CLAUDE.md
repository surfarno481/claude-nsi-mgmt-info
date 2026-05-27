# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NSI-AuRA (ultimate Requester Agent) — a FastAPI + FastUI web application for managing NSI network connections in the ANA consortium. Being replaced by nsi-dds-proxy, nsi-aggregator-proxy, and nsi-orchestrator.

## Commands

```bash
# Run all tests (matches CI)
uv run --group dev pytest tests/ -v

# Run a single test file
uv run --group dev pytest tests/test_vlan.py -v

# Run a specific test
uv run --group dev pytest tests/ -k "test_free_vlan_ranges"

# Type checking
uv run --group dev mypy aura/

# Linting
uv run --group dev ruff check aura/

# Build wheel
uv build --wheel

# Run locally (requires aura.env with certificate paths and NSI URLs)
nsi-aura
```

## Architecture

**App initialization** (`aura/__init__.py`): Creates the FastAPI app, mounts static files at `/static`, registers all routers, starts APScheduler, and defines a catch-all `/{path:path}` route that serves FastUI's prebuilt React SPA HTML.

**Frontend** (`aura/frontend/`): FastAPI routers return FastUI JSON component trees, not HTML. The React SPA (served by `prebuilt_html()`) fetches these JSON responses and renders them client-side. Routes: reservations CRUD, STP/SDP listings, NSI provider info, healthcheck.

**State machine** (`aura/fsm.py`): `ConnectionStateMachine` (python-statemachine) with 16 states tracking the NSI connection lifecycle from `ConnectionNew` through reserve/commit/provision/active/release/terminate to `ConnectionDeleted`. State values are stored in the `Reservation.state` database column.

**Background jobs** (`aura/job.py`): APScheduler with ThreadPoolExecutor (10 workers). `nsi_poll_dds_job` runs every minute to fetch topology from DDS and update STPs/SDPs. NSI workflow jobs (reserve, commit, provision, release, terminate) are scheduled on-demand per reservation.

**NSI integration** (`aura/nsi.py`, `aura/dds.py`): SOAP/XML over HTTP with mutual TLS client certificates. `nsi.py` sends NSI commands to the provider. `dds.py` fetches and parses NML topology documents from the Document Distribution Service.

**Database** (`aura/db.py`, `aura/model.py`): SQLModel ORM. SQLite by default (`sqlite:///db/aura.db`), PostgreSQL via `DATABASE_URI`. Models: `STP` (network endpoints), `SDP` (demarcation points connecting two STPs), `Reservation` (connection requests with state machine), `Log` (audit trail).

**Static files packaging**: `pyproject.toml` uses `[tool.setuptools.data-files]` to install static assets to `share/aura/static/` in the wheel. The Dockerfile sets `STATIC_DIRECTORY=/usr/local/share/aura/static` to point to the installed location.

## ROOT_PATH design decision

When deployed behind the portal (nsi-mgmt-info), the app is served at path prefix `/aura`. The portal's nginx ingress strips this prefix before forwarding requests.

**Do NOT set `FastAPI(root_path=...)`**. Starlette's `get_route_path()` assumes `scope["path"]` contains `root_path` as a prefix. When the proxy already stripped the prefix, this causes StaticFiles to double-count the mount path (looking up `static/static/file.png`), resulting in 404s.

Instead, `settings.ROOT_PATH` is used only for URL prefixing in templates and forms:
- `prebuilt_html(api_root_url=..., api_path_strip=...)` in the catch-all route
- Image `src` attributes via `aura/frontend/util.py`
- Form submit and search URLs in `aura/frontend/reservations.py`

## Testing

The test setup in `conftest.py` has important ordering constraints:
- `DATABASE_URI` is set to `sqlite://` (in-memory) **before any aura imports** because `Settings` validates `FilePath` fields at import time
- Dummy PEM files (`aura-certificate.pem`, `aura-private-key.pem`) are created before imports for the same reason
- `DatabaseLogHandler` is removed from all loggers to prevent DB writes during tests
- Each test gets its own DB session with automatic rollback via a transaction wrapper

## Code style

- Line length: 120 (black, isort, ruff all configured consistently)
- Python target: 3.13
- mypy with `pydantic.mypy` plugin, `disallow_untyped_defs = true`
- ruff rules: ANN, ARG, B, C, D, E, F, I, N, PGH, PTH, Q, RET, RUF, S, T, W
