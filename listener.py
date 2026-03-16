# listener.py
import asyncio
import logging
import json
from config import config

log = logging.getLogger("meshcom.listener")

class MeshComProtocol(asyncio.DatagramProtocol):
    """Asynchronous UDP Protocol for receiving MeshCom packets."""
    def __init__(self, db_handler, forwarder):
        self.db = db_handler
        self.forwarder = forwarder

    def connection_made(self, transport):
        self.transport = transport
        log.info(f"UDP Listener transport ready on {config.LISTENER_HOST}:{config.LISTENER_PORT}")

    def datagram_received(self, data, addr):
        """Called when a UDP datagram is received."""
        try:
            message_str = data.decode('utf-8')
            message_dict = json.loads(message_str)
            log.info(f"Received from {addr}: {message_dict.get('type')} from {message_dict.get('src')}")
            
            # Scheduling async tasks to process data
            asyncio.create_task(self._process_message(message_dict))
            
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            log.warning(f"Malformed packet from {addr}: {e}")
        except Exception as e:
            log.error(f"Error processing packet from {addr}: {e}", exc_info=True)

    async def _process_message(self, message_dict):
        """Store and forward the message asynchronously."""
        # 1. Save to DB (if type in config.STORE_TYPES)
        if message_dict.get("type") in config.STORE_TYPES:
            await self.db.save_message(message_dict)

        # 2. Forward (if rules match)
        # Implementation of rule matching in Phase 2
        await self.forwarder.send_notification(message_dict)
