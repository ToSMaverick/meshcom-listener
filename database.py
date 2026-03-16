import logging
import os
from surrealdb import Surreal
from config import config

log = logging.getLogger("meshcom.db")

class SurrealHandler:
    """Handles async connection to SurrealDB."""
    def __init__(self):
        self.url = config.DB_URL
        self.user = config.DB_USER
        self.password = config.DB_PASS
        self.namespace = config.DB_NS
        self.database = config.DB_DB
        self.db = None

    async def connect(self):
        """Initialize connection to SurrealDB."""
        if self.db:
            return
            
        log.info(f"Connecting to SurrealDB at {self.url}...")
        self.db = Surreal(self.url)
        await self.db.connect()
        await self.db.signin({"user": self.user, "pass": self.password})
        await self.db.use(self.namespace, self.database)
        log.info(f"Connected to DB {self.database} in namespace {self.namespace}.")

    async def init_schema(self, schema_file: str = "schema.surql"):
        """Apply SurrealQL schema from file."""
        if not os.path.exists(schema_file):
            log.warning(f"Schema file {schema_file} not found. Skipping auto-init.")
            return

        log.info(f"Applying schema from {schema_file}...")
        with open(schema_file, "r") as f:
            surql = f.read()
            await self.db.query(surql)
        log.info("Schema successfully applied.")

    async def save_message(self, message_dict: dict):
        """Save a message to SurrealDB."""
        if not self.db:
            log.error("Database not connected. Cannot save message.")
            return

        try:
            # Preparing data for SurrealDB
            # We add 'raw' as the full original dict for future-proofing
            data = {
                "type": message_dict.get("type"),
                "src": message_dict.get("src"),
                "dst": message_dict.get("dst"),
                "msg": message_dict.get("msg"),
                "lat": message_dict.get("lat"),
                "long": message_dict.get("long"),
                "alt": message_dict.get("alt"),
                "raw": message_dict
            }
            # Remove None values to keep DB clean
            data = {k: v for k, v in data.items() if v is not None}
            
            await self.db.create("message", data)
            log.debug(f"Saved {data['type']} message from {data['src']} to SurrealDB.")
        except Exception as e:
            log.error(f"Error saving message to SurrealDB: {e}")

    async def close(self):
        """Close connection."""
        if self.db:
            await self.db.close()
            self.db = None
            log.info("SurrealDB connection closed.")
