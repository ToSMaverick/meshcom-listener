# forwarder.py

import logging
import json
import requests # Synchrone HTTP-Bibliothek verwenden
from types import SimpleNamespace
import os
import time # für Test-Block

log = logging.getLogger(__name__)

# Helper zum Escapen von Zeichen für MarkdownV2 (bleibt gleich)
def escape_markdown_v2(text: str | None) -> str:
    """Escapes characters for Telegram MarkdownV2 parsing."""
    if text is None:
        return ''
    text = text.replace('\\', '\\\\')
    escape_chars = r'_*[]()~`>#+=-|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

class TelegramForwarder:
    """
    Handles formatting and sending messages to a Telegram Bot using the 'requests' library.
    """
    def __init__(self, telegram_config: SimpleNamespace):
        """
        Initialisiert den Telegram Bot forwarder.

        :param telegram_config: Configuration object containing 'bot_token' and 'chat_id'.
        :raises ValueError: If token or chat ID are missing or placeholders.
        """
        self.bot_token = telegram_config.bot_token
        self.chat_id = telegram_config.chat_id
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}/"

        # Validate config
        if not self.bot_token or "YOUR_BOT_TOKEN_HERE" in self.bot_token:
            log.error("Telegram Bot Token ist ungültig oder nicht in der Konfiguration gesetzt.")
            raise ValueError("Ungültiger Telegram Bot Token.")
        if not self.chat_id or "YOUR_TARGET_CHAT_ID_HERE" in self.chat_id:
            log.error("Telegram Chat ID ist ungültig oder nicht in der Konfiguration gesetzt.")
            raise ValueError("Ungültige Telegram Chat ID.")

        log.info("Telegram Forwarder (requests) initialisiert für Chat ID %s.", self.chat_id)
        # Optional: Test connection by calling getMe API endpoint
        try:
            self.test_connection()
        except ValueError as e:
            log.warning("Telegram Verbindungstest bei Initialisierung fehlgeschlagen: %s", e)
            # We allow initialization to continue, sending might still work later


    def test_connection(self):
        """Tests the bot token by calling the getMe endpoint."""
        test_url = f"{self.api_base_url}getMe"
        log.debug("Teste Telegram Verbindung mit %s", test_url)
        try:
            response = requests.get(test_url, timeout=10) # Add timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            bot_info = response.json()
            if bot_info.get("ok"):
                log.info("Telegram Bot Verbindung erfolgreich getestet: Bot Name = %s", bot_info.get("result", {}).get("username"))
            else:
                 log.error("Telegram API meldet Fehler bei getMe: %s", bot_info.get("description"))
                 raise ValueError(f"Telegram API Fehler: {bot_info.get('description')}")
        except requests.exceptions.RequestException as e:
            log.error("Fehler beim Testen der Telegram Bot Verbindung (requests): %s", e)
            raise ValueError(f"Telegram Verbindungstest fehlgeschlagen: {e}")
        except Exception as e:
            log.error("Unerwarteter Fehler beim Telegram Verbindungstest.", exc_info=True)
            raise

    def _format_message_markdown(self, message_dict: dict) -> str:
        """Formatiert das Nachrichten-Dictionary in einen MarkdownV2-String."""
        lines = []
        # Sicher extrahieren und für Markdown escapen (NUR für Text außerhalb von Code-Blöcken nötig)
        msg_type_raw = message_dict.get('type', 'N/A')
        msg_type = escape_markdown_v2(msg_type_raw) # Typ wird direkt verwendet
        src = escape_markdown_v2(message_dict.get('src', 'N/A'))
        dst = escape_markdown_v2(message_dict.get('dst'))
        msg_id = escape_markdown_v2(message_dict.get('msg_id'))

        # Titelzeile basierend auf Typ
        title = f"📡 Neue `{msg_type_raw}` Nachricht" # Verwende rohen Typ in Backticks
        lines.append(f"*{escape_markdown_v2(title)}*") # Escape den gesamten Titel

        lines.append(f"*Von:* `{src}`") # Src ist schon escaped, ok in Backticks

        if dst and dst != '\*':
            lines.append(f"*An:* `{dst}`") # Dst ist schon escaped, ok in Backticks

        if msg_id:
            lines.append(f"*ID:* `{msg_id}`") # ID ist schon escaped, ok in Backticks

        # Typ-spezifische Formatierung
        if msg_type_raw == 'msg' and 'msg' in message_dict:
            message_text = message_dict['msg']
            # Escaping innerhalb von ``` ist nicht nötig/erwünscht
            message_text = message_text.replace('```', '`\u200b`\u200b`')
            # Escape nur den Text VOR dem Code-Block
            lines.append(f"*{escape_markdown_v2('Nachricht:')}* \n```\n{message_text}\n```")
        elif msg_type_raw == 'pos' and 'lat' in message_dict and 'long' in message_dict:
            lat = message_dict.get('lat', '?')
            lon = message_dict.get('long', '?')
            alt = message_dict.get('alt')
            # Zeige Lat/Lon direkt in Backticks an, OHNE sie vorher zu escapen
            lines.append(f"*{escape_markdown_v2('Position:')}* `{lat}, {lon}`")
            if alt is not None:
                 # Zeige Höhe direkt in Backticks an, OHNE sie vorher zu escapen
                 lines.append(f"*{escape_markdown_v2('Höhe:')}* `{alt}m`")

            # URL für den Link NICHT escapen
            map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}"
            # Link-Text enthält keine Sonderzeichen, braucht kein Escaping
            # Die Link-Syntax selbst braucht kein Escaping
            lines.append(f"[📍 Auf Karte anzeigen]({map_link})")
        elif msg_type_raw == 'ack' and 'ack_id' in message_dict:
             # ack_id wird escaped und in Backticks gesetzt, ok
             ack_id_escaped = escape_markdown_v2(message_dict['ack_id'])
             lines.append(f"*{escape_markdown_v2('Ack ID:')}* `{ack_id_escaped}`")
        elif msg_type_raw == 'status' and 'msg' in message_dict:
            # Status-Text wird normal escaped (keine Backticks/Code-Blocks)
            status_text = escape_markdown_v2(message_dict['msg'])
            lines.append(f"*{escape_markdown_v2('Status:')}* {status_text}")
        elif msg_type_raw == 'bulletin' and 'msg' in message_dict:
             # Bulletin-Text wird normal escaped
             bulletin_text = escape_markdown_v2(message_dict['msg'])
             lines.append(f"*{escape_markdown_v2('Bulletin:')}* {bulletin_text}")

        # Fallback für unbekannte Typen
        if len(lines) <= 4: # Wenn nur die Standard-Header drin sind
             raw_json = json.dumps(message_dict, ensure_ascii=False, separators=(',', ':'))
             # Zeige Rohdaten in Backticks OHNE Escaping des Inhalts
             raw_json_display = f"{raw_json[:200]}{'...' if len(raw_json) > 200 else ''}"
             lines.append(f"*{escape_markdown_v2('Rohdaten:')}* `{raw_json_display}`")

        return "\n".join(lines)

    # NEUE Funktion: Sendet einen beliebigen Textstring
    def send_text(self, text: str, parse_mode: str | None = None):
        """
        Sends a given text string to the configured Telegram chat.

        :param text: The text message to send.
        :param parse_mode: Optional parse mode (e.g., 'MarkdownV2', 'HTML'). Defaults to None (plain text).
        """
        payload = {
            'chat_id': self.chat_id,
            'text': text,
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode

        url = f"{self.api_base_url}sendMessage"
        log.debug("Sende Text an Telegram API URL: %s", url)
        try:
            response = requests.post(url, json=payload, timeout=15) # Timeout hinzufügen
            response.raise_for_status() # Fehler werfen für 4xx/5xx Status Codes

            # Erfolgreiches Senden nur noch auf DEBUG loggen
            log.debug("Text erfolgreich an Telegram gesendet (Status: %s)", response.status_code)
            return True # Signalisiert Erfolg

        except requests.exceptions.Timeout:
            log.error("Timeout beim Senden der Nachricht an Telegram API.")
            return False
        except requests.exceptions.HTTPError as e:
            log.error("HTTP Fehler von Telegram API: %s - %s", e.response.status_code, e.response.text)
            return False
        except requests.exceptions.RequestException as e:
            log.error("Fehler beim Senden der Nachricht an Telegram (requests): %s", e)
            return False
        except Exception as e:
            log.error("Unerwarteter Fehler beim Senden an Telegram.", exc_info=True)
            return False

    # Angepasste Funktion: Formatiert und ruft send_text auf
    def send_message(self, message_dict: dict):
        """
        Formats a message dictionary using Markdown and sends it via send_text.

        :param message_dict: The parsed message dictionary.
        :return: True if sending was apparently successful, False otherwise.
        """
        log.debug("Formatiere und sende Nachrichten-Dictionary...")
        formatted_message = self._format_message_markdown(message_dict)
        # Rufe die neue send_text Methode auf
        return self.send_text(text=formatted_message, parse_mode='MarkdownV2')


# Example usage
if __name__ == "__main__":
    # --- Minimal Setup ---
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')

    test_bot_token = os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    test_chat_id = os.environ.get("TELEGRAM_TEST_CHAT_ID", "YOUR_TARGET_CHAT_ID_HERE")

    if "YOUR_" in test_bot_token or "YOUR_" in test_chat_id:
        log.error(">>> ECHTE Zugangsdaten benötigt zum Testen! <<<")
        # sys.exit(1) # Auskommentiert

    mock_tg_config = SimpleNamespace(bot_token=test_bot_token, chat_id=test_chat_id)

    sample_msg = {"src_type":"lora","type":"msg","src":"OE1TEST-1","dst":"ADMIN","msg":"Test via requests! _ * [ ] ( ) ~ ` > # + - = | { } . ! \\","msg_id":"REQ001"}
    sample_pos = {"src_type":"lora","type":"pos","src":"OE3TEST-2","msg":"","lat":48.2082,"long":16.3738, "alt": 156}
    plain_text_message = "Dies ist eine einfache Textnachricht ohne Formatierung."
    markdown_text_message = "Dies ist *fetter* und _kursiver_ Text\\." # Schon escaped!

    log.info("--- Teste forwarder.py (mit send_text) ---")

    try:
        forwarder = TelegramForwarder(mock_tg_config) # Init testet jetzt auch Verbindung

        log.info("Sende formatierte Nachricht (msg)...")
        success1 = forwarder.send_message(sample_msg)
        log.info("send_message erfolgreich: %s", success1)
        time.sleep(2)

        log.info("Sende formatiere Nachricht (pos)...")
        success2 = forwarder.send_message(sample_pos)
        log.info("send_message erfolgreich: %s", success2)
        time.sleep(2)

        log.info("Sende einfachen Text...")
        success3 = forwarder.send_text(plain_text_message)
        log.info("send_text (plain) erfolgreich: %s", success3)
        time.sleep(2)

        log.info("Sende Text mit MarkdownV2...")
        success4 = forwarder.send_text(markdown_text_message, parse_mode='MarkdownV2')
        log.info("send_text (MarkdownV2) erfolgreich: %s", success4)


        log.info(">>> Test-Nachrichten wurden versucht zu senden. Überprüfe deinen Telegram-Chat! <<<")

    except ValueError as e:
         log.error("Fehler bei der Initialisierung des Forwarders (ungültige Config?): %s", e)
    except Exception as e:
        log.error("Unerwarteter Fehler im Forwarder-Test.", exc_info=True)