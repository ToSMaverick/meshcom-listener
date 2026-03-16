from environs import Env
from typing import List

env = Env()
env.read_env()  # Versucht automatisch eine .env Datei zu laden

class Config:
    # --- Project Metadata ---
    VERSION: str = "0.2.0"

    # --- Listener ---
    LISTENER_HOST: str = env.str("LISTENER_HOST", default="0.0.0.0")
    LISTENER_PORT: int = env.int("LISTENER_PORT", default=1799)
    LISTENER_BUFFER: int = env.int("LISTENER_BUFFER", default=2048)
    STORE_TYPES: List[str] = env.list("STORE_TYPES", default=["msg"])

    # --- SurrealDB ---
    DB_URL: str = env.str("DB_URL", default="ws://localhost:8000/rpc")
    DB_USER: str = env.str("DB_USER", default="root")
    DB_PASS: str = env.str("DB_PASS", default="root")
    DB_NS: str = env.str("DB_NS", default="meshcom")
    DB_DB: str = env.str("DB_DB", default="listener")

    # --- Notifications (Apprise API) ---
    NOTIFY_ENABLED: bool = env.bool("NOTIFY_ENABLED", default=False)
    APPRISE_URL: str = env.str("APPRISE_URL", default="http://localhost:8000/notify")
    # Liste von Apprise-Targets, z.B. tgram://...
    NOTIFY_TARGETS: List[str] = env.list("NOTIFY_TARGETS", default=[])

    # --- Logging ---
    LOG_LEVEL: str = env.str("LOG_LEVEL", default="INFO")

# Singleton Instanz
config = Config()
