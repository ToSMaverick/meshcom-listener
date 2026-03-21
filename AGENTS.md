# Project Architecture & Plan: MeshCom Listener (Surreal Edition)

## 🎯 Vision
A high-performance, 12-factor compliant UDP listener for MeshCom nodes, utilizing SurrealDB for advanced data analysis and Apprise for decoupled notifications. Designed for easy "one-click" deployment for radio amateurs.

## 🏗 Architecture (12-Factor & Decoupled)

### 1. Codebase (I)
- Single repository, tracked in Git.

### 2. Config (III)
- **Tool:** `environs`.
- All configuration is stored in environment variables.
- `config.json` is deprecated. Overrides via `.env` or environment.

### 3. Backing Services (IV)
- **Database:** SurrealDB (Async WebSocket/RPC).
- **Notifications:** Apprise API (HTTP/POST).
- **Auto-Init:** The application checks and initializes the SurrealDB schema on startup (`serve`).

### 4. CLI Interface (Typer)
- `meshcom-listener serve`: Starts the async UDP listener (main entry point).
- `meshcom-listener test config`: Displays current configuration (masked secrets).
- `meshcom-listener test db`: Validates SurrealDB connection and schema.
- `meshcom-listener test notify`: Validates Apprise connection and sends a test notification.
- `meshcom-listener db init`: Manually triggers schema initialization (also runs automatically on `serve`).
- `meshcom-listener db reset`: Wipe all data and re-initialize the schema.
- `meshcom-listener version`: Shows application version and service status.

## 🛠 Tech Stack
- **Language:** Python 3.13+ (Asyncio)
- **Dependency Management:** `uv` (using `pyproject.toml` and `uv.lock`)
- **CLI Framework:** `typer`
- **Env Management:** `environs`
- **Database:** `surrealdb` (Python Async SDK)
- **HTTP Client:** `httpx` (for Apprise API)
- **Deployment:** Docker Multi-stage (uv-based)
- **CI/CD:** GitHub Actions -> GitHub Container Registry (GHCR)

## 📋 Implementation Plan

### Phase 1: Modern Tooling & Config (12-Factor Foundation)
- [x] Initialize `uv` project and create `pyproject.toml`.
- [x] Implement `config.py` using `environs` (Mapping env vars to a clean object).
- [x] Create `main.py` with `typer` structure and command stubs.
- [x] Cleanup: Remove old `requirements.txt` and `if __name__ == "__main__":` blocks.

### Phase 2: Async Core & Backing Services
- [x] Implement `database.py`: Async SurrealDB client with auto-init logic.
- [x] Implement `forwarder.py`: Async Apprise client using `httpx`.
- [x] Refactor `listener.py`: Convert to `asyncio.DatagramProtocol`.

### Phase 3: Infrastructure & Deployment
- [x] Create `docker-compose.yaml` (SurrealDB + Apprise + Listener).
- [x] Optimize `Dockerfile` (Multi-stage with `uv` for minimal image size).

### Phase 4: CI/CD & Release
- [x] Create GitHub Action for automated build and push to GHCR.
- [x] Add `README.md` instructions for the new "one-click" deployment.

### Phase 5: Refinement & Production Readiness
- [x] **5.1 Config & Architecture:** Update OOTB defaults (e.g., `ws://surrealdb:8000`). Move data parsing (`src` splitting) from `database.py` to `listener.py`.
- [x] **5.2 Advanced Forwarding:** Implement message templates (✉️ msg, 📍 pos, 📡 raw). Add config filters: `FORWARD_TYPES`, `INCLUDE_DST`, `EXCLUDE_DST`, `EXCLUDE_SRC`.
- [x] **5.3 Housekeeping:** Implement async background task to prune `message` records older than `DB_RETENTION_DAYS` (default 7).
- [x] **5.4 CI/CD & Docs:** Change GitHub Actions to trigger on tags only. Add Plug & Play `docker-compose.yaml` to Readme. Created detailed `CHANGELOG.md`.

---
**Status:** ✅ Project successfully modernized, refined and production-ready.
