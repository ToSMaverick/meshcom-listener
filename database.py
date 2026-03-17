import logging
import os
from surrealdb import AsyncSurreal
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
        self.db = AsyncSurreal(self.url)
        await self.db.connect()
        
        log.debug(f"Signing in as user '{self.user}'...")
        await self.db.signin({"username": self.user, "password": self.password})
        
        log.debug(f"Using namespace '{self.namespace}' and database '{self.database}'...")
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
        """Save a message to SurrealDB using a hybrid schema."""
        if not self.db:
            log.error("Database not connected. Cannot save message.")
            return

        try:
            # Parse 'src' to separate sender from routing path (via)
            raw_src = message_dict.get("src", "")
            src_parts = [s.strip() for s in raw_src.split(",") if s.strip()]
            
            sender = src_parts[0] if src_parts else None
            via_path = src_parts[1:] if len(src_parts) > 1 else []

            # Preparing the hybrid structure: Fixed metadata + Raw payload
            data = {
                "src": sender,
                "via": via_path,
                "src_type": message_dict.get("src_type"),
                "msg_type": message_dict.get("type"),
                "raw": message_dict  # The full original JSON
            }
            
            # Ensure sender and msg_type are present (required by schema)
            if not data["src"] or not data["msg_type"]:
                log.warning(f"Message missing required fields 'src' or 'type': {message_dict}")
                return

            result = await self.db.create("message", data)
            
            # Robust logging of the ID
            record_id = "???"
            if result and isinstance(result, list):
                first = result[0]
                record_id = first.get("id") if isinstance(first, dict) else first
            elif isinstance(result, dict):
                record_id = result.get("id", "???")
            
            log.debug(f"Saved {data['msg_type']} from {data['src']} (via: {data['via']}) to SurrealDB. ID: {record_id}")
        except Exception as e:
            log.error(f"Error saving message to SurrealDB: {e}")

    async def close(self):
        """Close connection."""
        if self.db:
            await self.db.close()
            self.db = None
            log.info("SurrealDB connection closed.")
