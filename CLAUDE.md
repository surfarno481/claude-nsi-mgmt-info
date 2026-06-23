# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

The **NSI Management Information Service** — a FastAPI + FastUI web service that surfaces and visualizes the information ANA management needs for strategic and engineering decision-making, aggregating data from the NSI-Orchestrator and other ANA-NSI components into overviews and statistics. **`README.md` is the ground truth** for the project's purpose and configuration.

**Naming.** The product and UI brand is **AMISS** (the default `SITE_TITLE` in `amiss/settings.py`). The importable Python package is `amiss` (config file `amiss.env`, `NSI_AMISS_*` settings), while the distribution, console script, Helm chart, container image, GitHub repository, and requester-NSA URN all use **`nsi-mgmt-info`**. Config variable names follow `amiss/settings.py`. The codebase originated from the older **NSI-AuRA** (uRA — ultimate Requester Agent) application, since superseded by nsi-dds-proxy, nsi-aggregator-proxy, and nsi-orchestrator.

## Commands

```bash
# Run all tests (matches CI)
uv run --group dev pytest tests/ -v

# Run a single test file
uv run --group dev pytest tests/test_vlan.py -v

# Run a specific test
uv run --group dev pytest tests/ -k "test_free_vlan_ranges"

# Type checking
uv run --group dev mypy amiss/

# Linting
uv run --group dev ruff check amiss/

# Build wheel
uv build --wheel

# Run locally (requires amiss.env with certificate paths and NSI URLs)
nsi-mgmt-info
```

## Architecture

**App initialization** (`amiss/__init__.py`): Creates the FastAPI app, mounts static files at `/static`, registers all routers, starts APScheduler, and defines a catch-all `/{path:path}` route that serves FastUI's prebuilt React SPA HTML. When `SEED_DUMMY_SEGMENTS_DATA` is set, it idempotently seeds dummy `Reservation`/`Segment` rows at startup via `amiss/seed.py` (dev/demo only).

**Frontend** (`amiss/frontend/`): FastAPI routers return FastUI JSON component trees, not HTML. The React SPA (served by `prebuilt_html()`) fetches these JSON responses and renders them client-side. Routes are **read-only**: reservation views (list/detail/log), STP/SDP listings, spectrum, healthcheck. (AMISS can no longer create or modify reservations — there is no NSI control plane.)

**State machine** (`amiss/fsm.py`): `ConnectionStateMachine` (python-statemachine) with 16 states for the NSI connection lifecycle from `ConnectionNew` through reserve/commit/provision/active/release/terminate to `ConnectionDeleted`. State values are stored in the `Reservation.state` column. The machine is no longer instantiated/driven (AMISS sends no commands) — it is retained for its state `.value` constants and `active_state_values`, used to display and filter reservation state.

**Background jobs** (`amiss/job.py`): APScheduler with ThreadPoolExecutor (10 workers). `nsi_poll_sources` is scheduled every minute and calls `nsi_poll_dds_job` then `nsi_poll_agg_job` (DDS first, so STPs/SDPs exist before reservations resolve against them). `nsi_poll_dds_job` wipes the `STP`/`SDP` tables and repopulates them from the **DDS proxy** (`GET /service-termination-points` and `/service-demarcation-points`), setting `isSdpMember=True` on SDP-member STPs. `nsi_poll_agg_job` fetches reservations from the aggregator proxy; it **temporarily** rebuilds the `Reservation` table from them (`temp_pull_reservations_from_agg` — a stopgap until reservations are sourced from the WFO, the Source of Truth) and then upserts their `Segment`s into the DB.

**NSI integration** (`amiss/nsi.py`, `amiss/dds.py`): mutual-TLS HTTP to the proxies. `nsi.py` is now just the JSON `GET` helper (`nsi_util_get_json`) used by the proxy pollers — AMISS no longer sends NSI SOAP commands and has no inbound provider callback. `dds.py` fetches and parses STP/SDP data from the **nsi-dds-proxy** JSON API (`get_dds_proxy_stps`/`get_dds_proxy_sdps` + `dds_proxy_json_to_stps`/`dds_proxy_json_to_sdps`).

**Database** (`amiss/db.py`, `amiss/model.py`): SQLModel ORM. Defaults to a shared **in-memory** SQLite database (`sqlite:///file::memory:?cache=shared&uri=true`, ephemeral — no persistence; `db.py` uses a `StaticPool` + `check_same_thread=False` for in-memory SQLite so the DB survives across the APScheduler/FastAPI threads). File-based SQLite or PostgreSQL via `DATABASE_URI`. Table models: `STP` (network endpoints; `isSdpMember` marks those that are part of an SDP), `SDP` (demarcation points connecting two STPs via `stpA`/`stpZ`), `Reservation` (connection requests with state machine; references source/dest `STP` and links many-to-many to `SDP`), `ReservationSDPLink` (the Reservation↔SDP association table), `Segment` (a path segment of an NSI P2P circuit shaped after the nsi-aggregator-proxy API; child of a `Reservation` via the `reservation_id` FK, parsed and upserted in `amiss/agg.py`), `Log` (audit trail).

**Static files packaging**: `pyproject.toml` uses `[tool.setuptools.data-files]` to install static assets to `share/amiss/static/` in the wheel. The Dockerfile sets `STATIC_DIRECTORY=/usr/local/share/amiss/static` to point to the installed location.

## ROOT_PATH design decision

When deployed behind a reverse-proxy portal, the app is served at path prefix `/amiss`. The portal's nginx ingress strips this prefix before forwarding requests.

**Do NOT set `FastAPI(root_path=...)`**. Starlette's `get_route_path()` assumes `scope["path"]` contains `root_path` as a prefix. When the proxy already stripped the prefix, this causes StaticFiles to double-count the mount path (looking up `static/static/file.png`), resulting in 404s.

Instead, `settings.ROOT_PATH` is used only for URL prefixing in templates and forms:
- `prebuilt_html(api_root_url=..., api_path_strip=...)` in the catch-all route
- Image `src` attributes via `amiss/frontend/util.py`
- Form submit and search URLs in `amiss/frontend/reservations.py`

## Testing

The test setup in `conftest.py` has important ordering constraints:
- `DATABASE_URI` is set to `sqlite://` (in-memory) **before any amiss imports** because `Settings` validates `FilePath` fields at import time
- Dummy PEM files (`amiss-certificate.pem`, `amiss-private-key.pem`) are created before imports for the same reason
- `DatabaseLogHandler` is removed from all loggers to prevent DB writes during tests
- Each test gets its own DB session with automatic rollback via a transaction wrapper

## Code style

- Line length: 120 (black, isort, ruff all configured consistently)
- Python target: 3.13
- mypy with `pydantic.mypy` plugin, `disallow_untyped_defs = true`
- ruff rules: ANN, ARG, B, C, D, E, F, I, N, PGH, PTH, Q, RET, RUF, S, T, W
