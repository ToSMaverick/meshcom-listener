import httpx
import logging
import json
from config import config

log = logging.getLogger("meshcom.forwarder")

class AppriseForwarder:
    """Handles forwarding messages to Apprise API with templates."""
    def __init__(self):
        self.api_url = config.APPRISE_URL
        self.targets = config.NOTIFY_TARGETS
        self.enabled = config.NOTIFY_ENABLED

    async def send_notification(self, message_dict: dict):
        """Send formatted message to Apprise API targets based on type."""
        if not self.enabled or not self.targets:
            return False

        msg_type = message_dict.get("type", "unknown")
        src = message_dict.get("src", "???")
        dst = message_dict.get("dst", "???")
        
        # --- Template Logic ---
        if msg_type == "msg":
            msg_text = message_dict.get("msg", "")
            title = f"✉️ from {src}"
            body = f"To: {dst}\n\n{msg_text}"
        
        elif msg_type == "pos":
            lat = message_dict.get("lat", "?")
            long = message_dict.get("long", "?")
            alt = message_dict.get("alt", "?")
            title = f"📍 from {src}"
            body = f"Lat: {lat}, Lon: {long}\nAlt: {alt}ft"
            if lat != "?" and long != "?":
                body += f"\n[OSM Map](https://www.openstreetmap.org/?mlat={lat}&mlon={long}#map=15/{lat}/{long})"
        
        else:
            # Fallback for tele, status, ack, etc.
            title = f"📡 {msg_type.upper()} from {src}"
            # Send the filtered raw dict (excluding bulky fields if any)
            clean_raw = {k: v for k, v in message_dict.items() if k not in ["raw"]}
            body = f"```json\n{json.dumps(clean_raw, indent=2)}\n```"

        payload = {
            "urls": ",".join(self.targets),
            "title": title,
            "body": body,
            "format": "markdown",
            "type": "info"
        }

        try:
            log.debug(f"Sending {msg_type} notification from {src}...")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                log.info(f"Notification successfully sent to {len(self.targets)} targets.")
                return True
        except httpx.HTTPStatusError as e:
            log.error(f"Apprise API returned error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            log.error(f"Error sending notification to Apprise: {e}")
            return False
