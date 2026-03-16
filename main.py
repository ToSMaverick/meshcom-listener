import typer
import asyncio
import logging
import sys
from typing import Optional
from config import config

# Logging initialisieren
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="[%(asctime)s %(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("meshcom")

# Typer Apps initialisieren
app = typer.Typer(help="MeshCom Listener CLI")
test_app = typer.Typer(help="Test connection to services")
db_app = typer.Typer(help="Manage SurrealDB")

app.add_typer(test_app, name="test")
app.add_typer(db_app, name="db")

# --- Commands ---

@app.command()
def serve():
    """Start the async UDP listener."""
    log.info(f"Starting MeshCom Listener v{config.VERSION} on {config.LISTENER_HOST}:{config.LISTENER_PORT}")
    log.warning("Serve command logic not yet implemented. Waiting for Phase 2.")
    # In Phase 2: asyncio.run(main_loop())

@test_app.command("config")
def test_config():
    """Display current configuration."""
    typer.echo(f"MeshCom Listener Version: {config.VERSION}")
    typer.echo(f"Listener: {config.LISTENER_HOST}:{config.LISTENER_PORT}")
    typer.echo(f"Database: {config.DB_URL} (User: {config.DB_USER})")
    typer.echo(f"Apprise URL: {config.APPRISE_URL}")
    typer.echo(f"Notifications: {'ENABLED' if config.NOTIFY_ENABLED else 'DISABLED'}")
    typer.echo(f"Targets: {config.NOTIFY_TARGETS}")

@test_app.command("db")
def test_db():
    """Validate SurrealDB connection."""
    log.info(f"Checking connection to SurrealDB at {config.DB_URL}...")
    log.warning("DB test logic not yet implemented.")

@test_app.command("notify")
def test_notify():
    """Validate Apprise connection and send test notification."""
    log.info(f"Sending test notification via {config.APPRISE_URL}...")
    log.warning("Notify test logic not yet implemented.")

@db_app.command("init")
def db_init():
    """Initialize SurrealDB schema."""
    log.info("Initializing SurrealDB schema...")
    log.warning("DB init logic not yet implemented.")

@app.command()
def version():
    """Show application version."""
    typer.echo(f"MeshCom Listener v{config.VERSION}")

if __name__ == "__main__":
    app()
