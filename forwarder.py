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
        """Send formatted message to Apprise API targets."""
        if not self.enabled or not self.targets:
            return

        # Simple formatting for the notification body
        msg_type = message_dict.get("type", "unknown")
        src = message_dict.get("src", "???")
        dst = message_dict.get("dst", "???")
        msg_text = message_dict.get("msg", "")

        title = f"MeshCom: {msg_type.upper()} from {src}"
        body = f"To: {dst}\n\n{msg_text}" if msg_text else f"Packet from {src} to {dst}"

        payload = {
            "urls": ",".join(self.targets),
            "title": title,
            "body": body,
            "format": "markdown",
            "type": "info"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                log.info(f"Notification successfully sent to {len(self.targets)} targets.")
        except httpx.HTTPStatusError as e:
            log.error(f"Apprise API returned error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            log.error(f"Error sending notification to Apprise: {e}")
