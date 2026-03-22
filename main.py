import typer
import asyncio
import logging
import sys
import signal
from typing import Optional
from config import config
from database import SurrealHandler
from forwarder import AppriseForwarder
from listener import MeshComProtocol

# Logging initialisieren (StreamHandler for Docker/12-factor)
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

# Global instances
db_handler = SurrealHandler()
forwarder = AppriseForwarder()

async def shutdown(loop, signal=None):
    """Cleanup tasks on shutdown."""
    if signal:
        log.info(f"Received exit signal {signal.name}...")
    log.info("Closing database connections...")
    await db_handler.close()
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [t.cancel() for t in tasks]
    log.info(f"Cancelling {len(tasks)} outstanding tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

async def housekeeping_task():
    """Periodic task to prune old database records."""
    log.info(f"Housekeeping task started (Retention: {config.DB_RETENTION_DAYS} days).")
    while True:
        try:
            await db_handler.prune_old_messages(config.DB_RETENTION_DAYS)
        except Exception as e:
            log.error(f"Error in housekeeping loop: {e}")
        
        # Wait 4 hours before next run
        await asyncio.sleep(4 * 3600)

@app.command()
def serve():
    """Start the async UDP listener."""
    log.info(f"Starting MeshCom Listener v{config.VERSION}")
    
    async def main_loop():
        loop = asyncio.get_running_loop()
        
        # 1. Connect and Auto-Init DB
        await db_handler.connect()
        await db_handler.init_schema()
        
        # 2. Start Housekeeping Task
        asyncio.create_task(housekeeping_task())
        
        # 3. Start UDP Listener
        log.info(f"Listening for UDP packets on {config.LISTENER_HOST}:{config.LISTENER_PORT}")
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: MeshComProtocol(db_handler, forwarder),
            local_addr=(config.LISTENER_HOST, config.LISTENER_PORT)
        )
        
        try:
            # Keep the loop running
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            transport.close()

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass

@test_app.command("config")
def test_config():
    """Display current configuration (masked secrets)."""
    typer.echo(f"MeshCom Listener Version: {config.VERSION}")
    typer.echo(f"Listener: {config.LISTENER_HOST}:{config.LISTENER_PORT} (Buffer: {config.LISTENER_BUFFER})")
    typer.echo(f"Storing Types: {config.STORE_TYPES}")
    typer.echo(f"Database: {config.DB_URL} (User: {config.DB_USER}, NS: {config.DB_NS}, DB: {config.DB_DB})")
    typer.echo(f"Apprise URL: {config.APPRISE_URL}")
    typer.echo(f"Notifications: {'ENABLED' if config.NOTIFY_ENABLED else 'DISABLED'}")
    typer.echo(f"Notification Targets: {config.NOTIFY_TARGETS}")

@test_app.command("db")
def test_db():
    """Validate SurrealDB connection and schema."""
    async def _test():
        try:
            await db_handler.connect()
            await db_handler.db.query("SELECT * FROM node LIMIT 1")
            typer.echo("✅ Successfully connected to SurrealDB and queried 'node' table.")
            await db_handler.close()
        except Exception as e:
            typer.echo(f"❌ SurrealDB connection failed: {e}")
            raise typer.Exit(code=1)
    
    asyncio.run(_test())

@test_app.command("notify")
def test_notify():
    """Validate Apprise connection and send test notification."""
    async def _test():
        try:
            typer.echo(f"Sending test notification via {config.APPRISE_URL}...")
            # Use the new structured format: msg_type, src, via, raw
            test_data = {
                "msg_type": "msg",
                "src": "TEST-NODE",
                "via": ["GATEWAY-1", "GATEWAY-2"],
                "raw": {
                    "type": "msg",
                    "src": "TEST-NODE",
                    "dst": "ADMIN",
                    "msg": "Connection Test: MeshCom Listener Notify works! ✅"
                }
            }
            success = await forwarder.send_notification(test_data)
            if success:
                typer.echo("✅ Apprise API call completed. Check your notification targets.")
            else:
                typer.echo("❌ Apprise API call failed. Check logs for details.")
                raise typer.Exit(code=1)
        except Exception as e:
            typer.echo(f"❌ Apprise test failed: {e}")
            raise typer.Exit(code=1)
            
    asyncio.run(_test())

@db_app.command("init")
def db_init():
    """Apply SurrealDB schema (non-destructive)."""
    async def _init():
        await db_handler.connect()
        await db_handler.init_schema()
        await db_handler.close()
        typer.echo("✅ Database schema updated/applied.")
        
    asyncio.run(_init())

@db_app.command("reset")
def db_reset():
    """REMOVES all data and tables (Destructive!)."""
    confirm = typer.confirm("Are you sure you want to DELETE all MeshCom data and nodes?")
    if not confirm:
        raise typer.Abort()
        
    async def _reset():
        await db_handler.connect()
        await db_handler.db.query("REMOVE TABLE message; REMOVE TABLE node;")
        await db_handler.init_schema()
        await db_handler.close()
        typer.echo("💥 Database wiped and re-initialized.")

        
    asyncio.run(_reset())

@app.command()
def version():
    """Show application version."""
    typer.echo(f"MeshCom Listener v{config.VERSION}")

if __name__ == "__main__":
    app()
