# MeshCom Listener (Surreal Edition)

A high-performance, asynchronous Python application designed to listen for UDP packets broadcast by MeshCom nodes. It utilizes **SurrealDB** for advanced data analysis and **Apprise** for flexible notifications.

## 🚀 Key Features

*   **Async Core:** Built with Python `asyncio` for high-throughput UDP handling.
*   **SurrealDB Integration:** Stores messages in a hybrid schema (fixed metadata + full raw payload).
*   **Smart Node Tracking:** Automatically maintains a "Last Seen" list of all MeshCom nodes, including their last known positions.
*   **Apprise Notifications:** Forward messages to over 100+ platforms (Telegram, Discord, Email, etc.) via a decoupled Apprise API.
*   **12-Factor Ready:** Fully configurable via environment variables.
*   **One-Click Deployment:** Docker Compose stack with pre-built images from GitHub Container Registry (GHCR).

## 🛠 Tech Stack

*   **Language:** Python 3.14+
*   **Database:** [SurrealDB](https://surrealdb.com/) (Graph/Document hybrid)
*   **Notification Gateway:** [Apprise API](https://github.com/caronc/apprise-api)
*   **Dependency Management:** `uv`
*   **Containerization:** Docker & GHCR

## 📦 Quick Start (Docker Compose)

The easiest way to run the listener is using the pre-built image from GHCR.

1.  **Create a `docker-compose.yaml`:**
    ```yaml
    version: "3.9"
    services:
      listener:
        image: ghcr.io/tosmaverick/meshcom-listener:latest
        container_name: meshcom-listener
        restart: unless-stopped
        ports:
          - "1799:1799/udp"
        environment:
          - DB_URL=ws://surrealdb:8000
          - APPRISE_URL=http://apprise:8000/notify
          # - NOTIFY_ENABLED=true
          # - NOTIFY_TARGETS=tgram://bottoken/chatid
        depends_on:
          - surrealdb
          - apprise

      surrealdb:
        image: surrealdb/surrealdb:latest
        container_name: meshcom-db
        command: start --user root --pass root --log info file:/mydata/meshcom.db
        ports:
          - "8000:8000"
        volumes:
          - ./db:/mydata
        restart: unless-stopped

      apprise:
        image: caronc/apprise
        container_name: meshcom-apprise
        restart: unless-stopped
    ```

2.  **Start the Stack:**
    ```bash
    docker-compose up -d
    ```

3.  **Explore your Data:**
    Open `http://localhost:8000` in your browser to access the **Surrealist** dashboard. You can query your data with:
    ```sql
    SELECT * FROM message ORDER BY time DESC;
    SELECT * FROM node;
    ```

## ⌨️ CLI Commands

If you want to run or test the listener locally (using `uv`):

*   `uv run main.py serve`: Start the listener.
*   `uv run main.py test db`: Test connection to SurrealDB.
*   `uv run main.py test notify`: Send a test notification.
*   `uv run main.py db init`: Apply the database schema (idempotent).
*   `uv run main.py db reset`: **Wipe all data** and re-initialize the schema.

## 📡 Developer Info

The database uses a hybrid schema in the `message` table:
*   `src`: The original sender (Callsign).
*   `via`: An array of routing nodes.
*   `msg_type`: The message type (pos, msg, tele, etc.).
*   `raw`: The complete original JSON packet for future-proof analysis.

---
73 de OE3MIF
