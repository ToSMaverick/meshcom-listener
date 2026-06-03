# MeshCom Listener

A small Go UDP listener for MeshCom nodes. It receives JSON packets, stores them in SQLite, keeps a compact node table, and can forward selected messages through an Apprise API service.

## Features

- UDP listener for MeshCom JSON packets on port `1799/udp`.
- SQLite default backend for low-memory hosts.
- Store interface prepared for future backends; SurrealDB is currently a stub in the Go port.
- Apprise forwarding with message, position, and raw fallback templates.
- Environment-variable configuration with optional `.env` file loading.
- Mise-based local tooling.
- Docker Compose deployment with persistent SQLite data in `./data`.

## Quick Start

Create `.env` from `.env.example`, then start the stack:

```bash
docker compose up -d
```

The listener stores SQLite data at `./data/meshcom.db` by default.

## Configuration

Important environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `LISTENER_HOST` | `0.0.0.0` | UDP bind address |
| `LISTENER_PORT` | `1799` | UDP bind port |
| `STORE_TYPES` | `msg,pos,tele` | Message types stored in the database; `*` stores all |
| `DB_BACKEND` | `sqlite` | `sqlite` is implemented; `surrealdb` is reserved |
| `DB_SQLITE_PATH` | `/data/meshcom.db` | SQLite database path |
| `DB_RETENTION_DAYS` | `7` | Retention period for stored messages |
| `NOTIFY_ENABLED` | `false` | Enables Apprise forwarding |
| `APPRISE_URL` | `http://apprise:8000/notify` | Apprise API endpoint |
| `NOTIFY_TARGETS` | empty | Comma-separated Apprise target URLs |
| `FORWARD_TYPES` | `msg,pos` | Message types forwarded to Apprise |
| `FORWARD_INCLUDE_DST` | empty | Optional destination allow-list for `msg` packets |
| `FORWARD_EXCLUDE_DST` | `*` | Destination block-list for `msg` packets |
| `FORWARD_EXCLUDE_SRC` | empty | Source block-list for `msg` packets |

## CLI

```bash
meshcom-listener serve
meshcom-listener test config
meshcom-listener test db
meshcom-listener test notify
meshcom-listener db init
meshcom-listener db reset
meshcom-listener version
```

For local development:

```bash
mise run fmt
mise run lint
mise run test
mise run build
```

With Nix:

```bash
nix develop
mise trust
mise install
mise run ci

nix build
nix run . -- version
```

## Data Model

SQLite uses two tables:

- `message`: full packet history with metadata (`src`, `via`, `src_type`, `msg_type`) and raw JSON.
- `node`: last-seen state per source, including the latest position for `pos` packets.

## Go Port Status

The Go port replaces the previous Python/SurrealDB runtime on this branch. SQLite is production-ready for this first Go version. The SurrealDB backend remains behind the store interface and returns a clear unsupported error until implemented.

73 de OE3MIF
