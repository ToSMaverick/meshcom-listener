import asyncio
import logging
import json
from config import config

log = logging.getLogger("meshcom.listener")

class MeshComProtocol(asyncio.DatagramProtocol):
    """Asynchronous UDP Protocol for receiving and processing MeshCom packets."""
    def __init__(self, db_handler, forwarder):
        self.db = db_handler
        self.forwarder = forwarder

    def connection_made(self, transport):
        self.transport = transport
        log.info(f"UDP Listener ready on {config.LISTENER_HOST}:{config.LISTENER_PORT}")

    def datagram_received(self, data, addr):
        """Called when a UDP datagram is received."""
        try:
            message_str = data.decode('utf-8')
            message_dict = json.loads(message_str)
            
            # Use asyncio.create_task to process message without blocking the listener
            asyncio.create_task(self._process_message(message_dict, addr))
            
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            log.warning(f"Malformed packet from {addr}: {e}")
        except Exception as e:
            log.error(f"Unexpected error processing packet from {addr}: {e}", exc_info=True)

    async def _process_message(self, message_dict, addr):
        """Handle storing and forwarding of a message."""
        msg_type = message_dict.get("type")
        src = message_dict.get("src")
        
        log.info(f"Received {msg_type} from {src} ({addr})")

        # 1. Save to Database (if type is in STORE_TYPES)
        if msg_type in config.STORE_TYPES or "*" in config.STORE_TYPES:
            await self.db.save_message(message_dict)

        # 2. Forward to Notifications (only if enabled and type is 'msg')
        # Here you can implement more complex rules if needed
        if config.NOTIFY_ENABLED and msg_type == "msg":
             await self.forwarder.send_notification(message_dict)
