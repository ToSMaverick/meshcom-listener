# Project Architecture & Plan: MeshCom Listener (Surreal Edition)

## 🎯 Vision
A high-performance, 12-factor compliant UDP listener for MeshCom nodes, utilizing SurrealDB for advanced data analysis and Apprise for decoupled notifications. Designed for easy "one-click" deployment for radio amateurs.

## 🏗 Architecture (12-Factor & Decoupled)

### 1. Codebase (I)
- Single repository, tracked in Git.

### 2. Config (III)
- **Tool:** `environs`.
- All configuration is stored in environment variables. No hardcoded secrets or environment-specific config files in the container.
- `config.json` will be deprecated in favor of `.env` or Docker environment variables.

### 3. Backing Services (IV)
- **Database:** SurrealDB (accessed via WebSockets/RPC).
- **Notifications:** Apprise API (accessed via HTTP).
- Services are attached via URLs and credentials defined in the environment.

### 4. Concurrency (VIII) & Processes (VI)
- **Core:** Python `asyncio`.
- **CLI:** `typer`.
- The application runs as a stateless, asynchronous process handling concurrent UDP packets and upstream API calls.

### 5. Logs (XI)
- Logs are treated as event streams sent to `stdout`/`stderr`. No local file rotation within the container (delegated to Docker/Systemd).

## 🛠 Tech Stack
- **Language:** Python 3.13+ (Asyncio)
- **CLI Framework:** `typer`
- **Env Management:** `environs`
- **Database:** `surrealdb` (Python Async SDK)
- **HTTP Client:** `httpx` (for Apprise API)
- **Deployment:** Docker Multi-stage (uv-based)

## 📋 Implementation Plan

### Phase 1: Environment & CLI
- [ ] Implement `config.py` using `environs`.
- [ ] Refactor `main.py` with `typer`.

### Phase 2: Async Core
- [ ] Convert `listener.py` to `asyncio` (DatagramProtocol).
- [ ] Implement `database.py` with SurrealDB Async SDK.
- [ ] Implement `forwarder.py` using `httpx` for Apprise API.

### Phase 3: Infrastructure
- [ ] Create `docker-compose.yaml` with SurrealDB, Apprise, and Listener.
- [ ] Implement a "Schema-on-Startup" logic to apply SurrealQL.

### Phase 4: Refinement
- [ ] Add graceful shutdown (SIGTERM handling).
- [ ] Multi-stage Dockerfile optimization.
