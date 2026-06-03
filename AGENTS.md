# Project Architecture: MeshCom Listener Go Port

## Vision

A lightweight UDP listener for MeshCom LoRa nodes, optimized for small hosts. The Go port keeps the existing listener and Apprise forwarding behavior while replacing the SurrealDB-first runtime with a SQLite default backend.

## Architecture

### Runtime

- Language: Go 1.26.3
- Entry point: `cmd/meshcom-listener`
- CLI: Cobra
- Configuration: environment variables with optional `.env` loading
- Listener: UDP JSON packet processing
- Notifications: Apprise API over HTTP
- Default database: SQLite via pure-Go `modernc.org/sqlite`

### Backing Services

- `DB_BACKEND=sqlite` is the production default.
- `DB_SQLITE_PATH=/data/meshcom.db` is the Docker default.
- SurrealDB is reserved behind the store interface but is not implemented in the first Go port.
- Apprise remains optional and is enabled with `NOTIFY_ENABLED=true` plus `NOTIFY_TARGETS`.

### Store Interface

All database backends implement:

- `Connect`
- `Init`
- `SaveMessage`
- `PruneOldMessages`
- `Ping`
- `Reset`
- `Close`

SQLite stores full raw packets in `message.raw`, structured metadata in dedicated columns, and last-seen node state in `node`.

### CLI

- `meshcom-listener serve`
- `meshcom-listener test config`
- `meshcom-listener test db`
- `meshcom-listener test notify`
- `meshcom-listener db init`
- `meshcom-listener db reset`
- `meshcom-listener version`

## Tooling

Mise is the project task runner and pins Go:

- `mise run fmt`
- `mise run lint`
- `mise run test`
- `mise run build`
- `mise run ci`
- `mise run docker-build`

GitHub Actions runs `mise run ci` before the Docker Buildx publish job.

## Deployment

The default Docker Compose stack contains:

- `listener`
- `apprise`

SQLite data is persisted through `./data:/data`. SurrealDB is intentionally not part of the default compose file.
