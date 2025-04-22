# forwarder.py

import logging
import json
import requests # Synchrone HTTP-Bibliothek verwenden
from types import SimpleNamespace
import os
import time # für Test-Block
from collections import defaultdict # Für sicheres format_map

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
    Handles formatting (using configured templates) and sending messages
    to a Telegram Bot using the 'requests' library.
    """
    def __init__(self, telegram_config: SimpleNamespace):
        """
        Initialisiert den Telegram Bot forwarder.

        :param telegram_config: Configuration object containing 'bot_token', 'chat_id', and 'templates'.
        :raises ValueError: If token or chat ID are missing or placeholders.
        :raises AttributeError: If 'templates' attribute is missing.
        """
        self.bot_token = telegram_config.bot_token
        self.chat_id = telegram_config.chat_id
        # NEU: Templates aus der Config speichern
        if not hasattr(telegram_config, 'templates') or not isinstance(telegram_config.templates, dict):
             log.error("Konfigurationsobjekt fehlt das 'templates'-Dictionary.")
             raise ValueError("Fehlende oder ungültige Template-Konfiguration.")
        self.templates = telegram_config.templates
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}/"

        # Validate secrets config
        if not self.bot_token or "SET_VIA_ENV_OR_CONFIG" in self.bot_token:
            log.error("Telegram Bot Token ist ungültig oder nicht in der Konfiguration gesetzt.")
            raise ValueError("Ungültiger Telegram Bot Token.")
        if not self.chat_id or "SET_VIA_ENV_OR_CONFIG" in self.chat_id:
            log.error("Telegram Chat ID ist ungültig oder nicht in der Konfiguration gesetzt.")
            raise ValueError("Ungültige Telegram Chat ID.")
        # Validate default template existence
        if 'default' not in self.templates:
            log.error("Fehlendes 'default' Template in forwarding.telegram.templates Konfiguration.")
            raise ValueError("Default-Template fehlt in der Konfiguration.")


        log.info("Telegram Forwarder (requests) initialisiert für Chat ID %s.", self.chat_id)
        try:
            self.test_connection()
        except ValueError as e:
            log.warning("Telegram Verbindungstest bei Initialisierung fehlgeschlagen: %s", e)

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

    def _prepare_render_context(self, message_dict: dict) -> dict:
        """
        Prepares the context dictionary for template rendering.
        Applies Markdown escaping selectively and adds computed values.
        """
        context = {}
        # Helper for safe access and default value
        safe_get = lambda key, default='': message_dict.get(key, default) or default

        # --- Apply escaping to values used OUTSIDE code blocks/URLs ---
        context['type'] = escape_markdown_v2(safe_get('type', 'unknown'))
        context['src'] = escape_markdown_v2(safe_get('src'))
        context['dst'] = escape_markdown_v2(safe_get('dst'))
        context['msg'] = escape_markdown_v2(safe_get('msg'))
        context['msg_id'] = escape_markdown_v2(safe_get('msg_id'))
        context['ack_id'] = escape_markdown_v2(safe_get('ack_id'))

        # --- Add raw/unescaped values needed for code blocks or calculations ---
        context['lat'] = safe_get('lat', '?')
        context['long'] = safe_get('long', '?')
        context['alt'] = safe_get('alt') # Raw altitude (likely in ft)

        # --- Add computed/formatted values (don't escape these) ---
        # Altitude in meters
        alt_m_str = 'N/A'
        if context['alt'] not in [None, '', '?']:
            try:
                alt_meter = round(float(context['alt']) * 0.3048, 1)
                alt_m_str = str(alt_meter)
            except (ValueError, TypeError):
                alt_m_str = 'Ungültig'
        context['_alt_m'] = alt_m_str # Use computed value in template

        # Map Link
        map_link = 'N/A'
        if context['lat'] != '?' and context['long'] != '?':
            # URL should not be escaped
            map_link = f"https://www.openstreetmap.org/?mlat={context['lat']}&mlon={context['long']}#map=15/{context['lat']}/{context['long']}"
        context['_map_link'] = map_link # Use computed value in template

        # Shortened Raw JSON (for default template, used in backticks)
        raw_json = json.dumps(message_dict, ensure_ascii=False, separators=(',', ':'))
        raw_json_short = f"{raw_json[:200]}{'...' if len(raw_json) > 200 else ''}"
        context['_raw_json_short'] = raw_json_short # Use computed value in template

        # *** WICHTIG: Ensure all keys potentially used in ANY template have a value ***
        # Add default values for keys not directly handled above if they might appear in templates
        # Example: if a template uses {hw_id} add:
        # context['hw_id'] = escape_markdown_v2(safe_get('hw_id'))
        # ... add other keys as needed based on your templates ...

        return context


    # Umbenannt von _format_message_markdown
    def _render_template(self, message_dict: dict) -> str:
        """
        Renders the appropriate template from config based on message type.
        """
        msg_type = message_dict.get('type', 'unknown')
        template_str = self.templates.get(msg_type, self.templates.get('default')) # Fallback to default

        if not template_str: # Final fallback if default is somehow missing
            log.error("Kein Template für Typ '%s' oder 'default' gefunden!", msg_type)
            return f"Fehler: Kein Template für Nachrichtentyp '{msg_type}' gefunden."

        log.debug("Verwende Template für Typ '%s'.", msg_type if msg_type in self.templates else 'default')

        # Prepare context data with escaping and computed values
        context = self._prepare_render_context(message_dict)

        # Render using format_map and defaultdict for safety against missing keys
        try:
            # defaultdict returns '???' if a key is missing in the template AND context
            safe_context = defaultdict(lambda: '???', context)
            rendered_text = template_str.format_map(safe_context)
            return rendered_text
        except (KeyError, ValueError, TypeError) as e:
            log.error("Fehler beim Formatieren der Nachricht mit Template für Typ '%s': %s", msg_type, e)
            # Fallback: Send raw JSON dump (or a fixed error message)
            fallback_text = f"*{escape_markdown_v2(f'Fehler beim Formatieren der Nachricht (Typ: {msg_type})')}*\n" \
                            f"```\n{json.dumps(message_dict, indent=1, ensure_ascii=False)}\n```"
            return fallback_text
        except Exception as e:
             log.error("Unerwarteter Fehler beim Template-Rendering für Typ '%s'", msg_type, exc_info=True)
             return f"*{escape_markdown_v2(f'Interner Fehler beim Formatieren (Typ: {msg_type})')}*"


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
        log.debug("Sende Text an Telegram API URL: %s (Größe: %d)", url, len(text))
        try:
            response = requests.post(url, json=payload, timeout=15) # Timeout hinzufügen
            response.raise_for_status() # Fehler werfen für 4xx/5xx Status Codes
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

    # Angepasste Funktion: Ruft jetzt _render_template auf
    def send_message(self, message_dict: dict):
        """
        Renders a message template based on the message dictionary and sends it via send_text.

        :param message_dict: The parsed message dictionary.
        :return: True if sending was apparently successful, False otherwise.
        """
        log.debug("Rendere Template und sende Nachrichten-Dictionary...")
        # Rendere das Template basierend auf dem message_dict
        rendered_message = self._render_template(message_dict)
        # Rufe die send_text Methode mit dem gerenderten Text auf
        return self.send_text(text=rendered_message, parse_mode='MarkdownV2')


# Example usage (Test block needs update if config structure changes significantly)
if __name__ == "__main__":
    # --- Minimal Setup ---
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')

    # Beispiel-Templates für den Test (normalerweise aus Config)
    test_templates = {
        "default": "📡 *Default*\n*Typ:* `{type}`\n*Von:* `{src}`\n*Roh:* `{_raw_json_short}`",
        "msg": "📡 *Nachricht*\n*Von:* `{src}`\n*An:* `{dst}`\n*Text:*\n```\n{msg}\n```",
        "pos": "📡 *Position*\n*Von:* `{src}`\n*Lat/Lon:* `{lat}/{long}`\n*Höhe:* `{_alt_m}m`\n[Karte]({_map_link})"
    }

    test_bot_token = os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "SET_VIA_ENV_OR_CONFIG")
    test_chat_id = os.environ.get("TELEGRAM_TEST_CHAT_ID", "SET_VIA_ENV_OR_CONFIG")

    # Mock-Config erstellen, jetzt mit Templates
    mock_tg_config = SimpleNamespace(
        bot_token=test_bot_token,
        chat_id=test_chat_id,
        templates=test_templates # Füge die Test-Templates hinzu
    )

    sample_msg = {"type":"msg","src":"OE1TEST-1","dst":"ADMIN","msg":"Test *mit* Markdown `code` und Link [example.com](http://example.com)."}
    sample_pos = {"type":"pos","src":"OE3TEST-2","lat":48.2082,"long":16.3738, "alt": 512} # ~156m
    sample_unknown = {"type":"special", "src":"OE5TEST-3", "value": 123, "extra": "info"}

    log.info("--- Teste forwarder.py (mit Templates) ---")

    # Prüfe ob Token/ID gesetzt sind bevor der Test läuft
    if "SET_VIA_ENV_OR_CONFIG" in test_bot_token or "SET_VIA_ENV_OR_CONFIG" in test_chat_id:
         log.error(">>> ECHTE Zugangsdaten benötigt zum Testen! <<<")
         log.error(">>> Setze TELEGRAM_TEST_BOT_TOKEN und TELEGRAM_TEST_CHAT_ID Umgebungsvariablen oder editiere das Skript. <<<")
    else:
        try:
            forwarder = TelegramForwarder(mock_tg_config)

            log.info("Sende formatierte Nachricht (msg) via Template...")
            forwarder.send_message(sample_msg)
            time.sleep(2)

            log.info("Sende formatierte Nachricht (pos) via Template...")
            forwarder.send_message(sample_pos)
            time.sleep(2)

            log.info("Sende formatierte Nachricht (unknown type) via Default-Template...")
            forwarder.send_message(sample_unknown)
            time.sleep(2)

            log.info("Sende direkten Text...")
            forwarder.send_text("✅ Listener Test gestartet.")

            log.info(">>> Test-Nachrichten wurden versucht zu senden. Überprüfe deinen Telegram-Chat! <<<")

        except ValueError as e:
            log.error("Fehler bei der Initialisierung des Forwarders: %s", e)
        except Exception as e:
            log.error("Unerwarteter Fehler im Forwarder-Test.", exc_info=True)