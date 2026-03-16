# forwarder.py
import httpx
import logging
import json
from config import config

log = logging.getLogger("meshcom.forwarder")

class AppriseForwarder:
    """Handles forwarding messages to Apprise API via HTTP."""
    def __init__(self):
        self.api_url = config.APPRISE_URL
        self.targets = config.NOTIFY_TARGETS
        self.enabled = config.NOTIFY_ENABLED

    async def send_notification(self, message_dict: dict):
        """Send formatted message to Apprise API."""
        if not self.enabled or not self.targets:
            log.debug("Notification disabled or no targets configured.")
            return

        log.info(f"Forwarding message to {len(self.targets)} targets via {self.api_url}...")
        # Implementation in Phase 2 using httpx.AsyncClient
        pass
