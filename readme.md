# MeshCom Listener

A Python application designed to listen for UDP packets broadcast by MeshCom nodes (typically on UDP port 1799), primarily used in amateur radio networks in Austria (OE) and Germany (DL).

It parses incoming JSON messages, stores selected message types in an SQLite database for later analysis, logs traffic, and can forward specific messages to a Telegram chat based on configurable rules.

## Features

* Listens for MeshCom UDP packets on a configurable port (default: 1799).
* Parses JSON messages received from MeshCom nodes.
* Stores messages persistently in an SQLite database.
* Allows filtering which message types (`msg`, `pos`, etc.) are stored via the `store_types` configuration option.
* Forwards messages to a Telegram chat based on configurable rules (filtering by message `type` and `dst`).
* Configuration managed via `config.json` file.
* Handles sensitive Telegram credentials (Bot Token, Chat ID) securely via environment variables (recommended) with fallback to `config.json`.
* Detailed logging to console and rotating log files (`logs/MeshComListener.log`).
* Easy deployment using Docker and Docker Compose (recommended setup).

## Requirements

* Python 3.9+
* Git (for cloning the repository)
* For Docker setup: Docker and Docker Compose installed.

## Installation & Setup

Two setup methods are described: Docker (recommended for stable deployment) and Local (for development or specific use cases).

### Docker Setup (Recommended)

This method uses Docker Compose to build and run the listener in an isolated container. It's the preferred way for running the service reliably.

1. **Clone the Repository:**

    ```bash
    git clone <link-to-git-repository>
    cd meshcom-listener
    ```

2. **Prepare Configuration:**
    * Copy the example configuration:

        ```bash
        cp config-example.json config.json
        ```

    * Edit `config.json` to adjust settings like database path (`db/meshcom_messages.db` is default), listener port if needed, `store_types` (to select which message types you want to save), and forwarding rules. **Do not put your Telegram Bot Token or Chat ID directly into `config.json` if using Docker Compose.**

        ```json
        // Example snippet from config.json
        "listener": {
            "host": "0.0.0.0",
            "port": 1799,
            "buffer_size": 2048,
            "store_types": [
                "msg",
                "pos"
            ]
        },
        "forwarding": {
            "enabled": true, // Set to true to enable forwarding
            "provider": "telegram",
            "rules": [
                {"type": "msg", "dst": "*"},  // Forward messages everyone
                {"type": "msg", "dst": "232"} // Forward messages to group 232
            ],
            "telegram": {
                // Keep placeholders here if using .env file
                "bot_token": "SET_VIA_ENV_OR_CONFIG",
                "chat_id": "SET_VIA_ENV_OR_CONFIG"
            }
        }
        ```

3. **Create `.env` File for Secrets:**
    * Create a file named `.env` in the `meshcom-listener` directory. **Important:** Add `.env` to your `.gitignore` file to prevent committing secrets!
    * Add your Telegram Bot Token and Chat ID to this file:

        ```dotenv
        # .env (This file should NOT be committed to Git)
        TELEGRAM_BOT_TOKEN=123456:ABCDEFGabcdefghijklmnop
        TELEGRAM_CHAT_ID=-1001234567890 # Example for a group/channel ID
        # Or use your personal Chat ID (can get it from @userinfobot on Telegram)
        ```

    * The application will prioritize these environment variables over values in `config.json` for the token and chat ID.

4. **Build and Run with Docker Compose:**

    ```bash
    docker-compose up -d --build
    ```

    * `--build` forces Docker Compose to build the image based on the `Dockerfile` if it doesn't exist or if changes were made.
    * `-d` runs the container in detached mode (in the background).

### Local Setup (Alternative / Development)

Use this method if you prefer not to use Docker or for development purposes.

1. **Clone the Repository:**

    ```bash
    git clone <link-to-your-git-repository>
    cd meshcom-listener
    ```

2. **Set up Python Virtual Environment:**

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    ```

3. **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4. **Prepare Configuration:**
    * Copy the example configuration:

        ```bash
        cp config-example.json config.json
        ```

    * Edit `config.json`. For local setup, you *can* put your Telegram token and chat ID here directly, or you can set the environment variables `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in your shell before running the script. Using environment variables is still recommended for better security practices.

        ```bash
        export TELEGRAM_BOT_TOKEN="your_token"
        export TELEGRAM_CHAT_ID="your_chat_id"
        # Or edit config.json directly
        nano config.json
        ```

5. **Run the Listener:**

    ```bash
    python main.py
    ```

    * Press `Ctrl+C` to stop the listener.

## Configuration Details (`config.json`)

* **`database`**:
  * `db_file`: Path to the SQLite database file. Relative paths are interpreted from the application's root directory (`/app` inside Docker). Default: `db/meshcom_messages.db`.
  * `table_name`: Name of the table where messages are stored. Default: `messages`.
* **`listener`**:
  * `host`: IP address to listen on. `0.0.0.0` listens on all available network interfaces.
  * `port`: UDP port to listen on (MeshCom usually uses 1799).
  * `buffer_size`: Max size of UDP packets to receive.
  * `store_types`: A list of message `type` strings. Only messages with a type present in this list will be saved to the database. Example: `["msg", "pos"]`.
* **`logging`**:
  * `console.level`: Log level for console output (e.g., `INFO`, `DEBUG`, `WARNING`).
  * `file.path`: Path to the log file. Default: `logs/MeshComListener.log`.
  * `file.level`: Log level for file output.
  * `file.rolling_interval`: How often the log file should rotate (`day`, `hour`, `minute`, `midnight`).
  * `file.retained_file_count_limit`: How many old log files to keep.
  * `file.output_template`: Log message format string.
* **`forwarding`**:
  * `enabled`: Set to `true` to enable forwarding, `false` to disable.
  * `provider`: Currently only `"telegram"` is supported.
  * `rules`: A list of dictionaries defining which messages to forward. A message is forwarded if it matches *any* rule.
    * Each rule is a dictionary specifying conditions. Example: `{"type": "msg", "dst": "232"}` forwards messages of type `msg` sent to `232`. `{"type": "pos"}` forwards all messages of type `pos` regardless of destination. Supported keys in rules: `type`, `dst`.
    * `telegram`:
      * `bot_token`: Your Telegram Bot Token. **Recommended:** Set via `TELEGRAM_BOT_TOKEN` environment variable. Falls back to this value if env var is not set. Default placeholder: `"SET_VIA_ENV_OR_CONFIG"`.
      * `chat_id`: The target Telegram Chat ID (user, group, or channel). **Recommended:** Set via `TELEGRAM_CHAT_ID` environment variable. Falls back to this value if env var is not set. Default placeholder: `"SET_VIA_ENV_OR_CONFIG"`.

## Usage

### Docker

* **Start:** `docker-compose up -d` (in the directory with `docker-compose.yaml`)
* **Stop & Remove:** `docker-compose down`
* **View Logs:** `docker-compose logs -f` (or `docker logs -f meshcom-listener`)
* **Restart:** `docker-compose restart`

### Local

* **Start:** `python main.py` (ensure virtual environment is active)
* **Stop:** Press `Ctrl+C` in the terminal where it's running.

Logs will appear on the console and/or in the file specified in `config.json` (`logs/MeshComListener.log` by default). The SQLite database will be created/updated at the path specified in `config.json` (`db/meshcom_messages.db` by default).

## Troubleshooting

* **Port in use:** If the listener fails to start with a "socket error" or "address already in use", check if another application is using the configured UDP port (default 1799).
* **Permission Denied (Logs/DB):** If running with Docker and using mounted volumes (`./db`, `./logs`), ensure the user running the Docker daemon has write permissions to these directories on the host machine, or manage permissions appropriately.
* **Configuration Errors:** Check the application logs upon startup for `ValueError` messages indicating problems found during configuration validation (e.g., missing fields, incorrect types). Check `config.json` syntax carefully.
* **Telegram Errors:** If forwarding is enabled but messages don't arrive:
  * Check application logs for errors from the `forwarder` module.
  * Verify `TELEGRAM_BOT_TOKEN` is correct.
  * Verify `TELEGRAM_CHAT_ID` is correct (use a leading `-` for group/channel IDs).
  * Ensure the bot has been added to the target chat and has permission to send messages.
