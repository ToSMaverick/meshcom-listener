# forwarder.py

import logging
import json
import asyncio # Needed to run async telegram functions from sync code
import time # Für eventuelle Pausen bei Fehlern
from types import SimpleNamespace
import os # Für Zugriff auf Umgebungsvariablen im Test

try:
    from telegram import Bot
    from telegram.error import TelegramError
    from telegram.constants import ParseMode # For MarkdownV2/HTML
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    # Erlaube das Laden des Moduls, auch wenn python-telegram-bot nicht installiert ist,
    # aber die Initialisierung wird fehlschlagen, wenn es benötigt wird.
    Bot = object # type: ignore
    TelegramError = Exception # type: ignore
    ParseMode = object # type: ignore


log = logging.getLogger(__name__)

# Helper zum Escapen von Zeichen für MarkdownV2 (empfohlen von Telegram)
# Quelle: https://core.telegram.org/bots/api#markdownv2-style
def escape_markdown_v2(text: str | None) -> str:
    """Escapes characters for Telegram MarkdownV2 parsing."""
    if text is None:
        return ''
    # Characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . ! \
    # Wichtig: \ muss auch escaped werden, am besten zuerst ersetzen, um Doppel-Escaping zu vermeiden
    text = text.replace('\\', '\\\\')
    escape_chars = r'_*[]()~`>#+=-|{}.!'
    # Ersetze jedes Vorkommen eines zu escapenden Zeichens durch seine Escaped-Version
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

class TelegramForwarder:
    """
    Kümmert sich um das Formatieren und Senden von Nachrichten an einen Telegram Bot.
    Verwendet die python-telegram-bot Bibliothek.
    """
    def __init__(self, telegram_config: SimpleNamespace):
        """
        Initialisiert den Telegram Bot Forwarder.

        :param telegram_config: Konfigurationsobjekt mit 'bot_token' und 'chat_id'.
        :raises ValueError: Wenn Token oder Chat-ID fehlen oder ungültig sind.
        :raises ImportError: Wenn python-telegram-bot nicht installiert ist.
        """
        if not TELEGRAM_AVAILABLE:
            log.error("Die Bibliothek 'python-telegram-bot' ist nicht installiert. pip install python-telegram-bot")
            raise ImportError("python-telegram-bot ist für den TelegramForwarder erforderlich.")

        self.bot_token = telegram_config.bot_token
        self.chat_id = telegram_config.chat_id
        self.bot: Bot | None = None # Type Hinting für Bot-Instanz

        # Überprüfe auf Platzhalter oder fehlende Werte
        if not self.bot_token or "YOUR_BOT_TOKEN_HERE" in self.bot_token:
            log.error("Telegram Bot Token ist ungültig oder nicht in der Konfiguration gesetzt.")
            raise ValueError("Ungültiger Telegram Bot Token.")
        if not self.chat_id or "YOUR_TARGET_CHAT_ID_HERE" in self.chat_id:
            # Chat ID könnte eine Zahl sein, daher als String behandeln für die Prüfung
            log.error("Telegram Chat ID ist ungültig oder nicht in der Konfiguration gesetzt.")
            raise ValueError("Ungültige Telegram Chat ID.")

        try:
            # Initialisiere die Bot-Instanz
            self.bot = Bot(token=self.bot_token)
            log.info("Telegram Bot Client initialisiert.")
            # Ein erster Test der Verbindung / des Tokens wäre hier sinnvoll,
            # z.B. durch Abrufen der Bot-Infos (ist aber auch ein async-Aufruf).
            # asyncio.run(self.test_connection()) # Siehe Beispiel unten
        except Exception as e:
            log.error("Fehler beim Initialisieren des Telegram Bot Clients.", exc_info=True)
            self.bot = None # Sicherstellen, dass bot None ist bei Fehler
            raise

    async def test_connection(self):
        """Versucht, Bot-Informationen abzurufen, um Token/Verbindung zu testen."""
        if not self.bot: return
        try:
            bot_info = await self.bot.get_me()
            log.info("Telegram Bot Verbindung erfolgreich getestet: Bot Name = %s", bot_info.username)
        except TelegramError as e:
            log.error("Fehler beim Testen der Telegram Bot Verbindung: %s", e)
            # Evtl. hier self.bot auf None setzen oder Fehler weitergeben?
            raise

    def _format_message_markdown(self, message_dict: dict) -> str:
        """Formatiert das Nachrichten-Dictionary in einen MarkdownV2-String."""
        lines = []
        # Sicher extrahieren und für Markdown escapen
        msg_type = escape_markdown_v2(message_dict.get('type', 'N/A'))
        src = escape_markdown_v2(message_dict.get('src', 'N/A'))
        dst = escape_markdown_v2(message_dict.get('dst'))
        msg_id = escape_markdown_v2(message_dict.get('msg_id'))

        # Titelzeile basierend auf Typ
        title = f"📡 Neue `{msg_type}` Nachricht"
        lines.append(f"*{title}*")
        lines.append(f"*Von:* `{src}`")

        # Ziel nur anzeigen, wenn es nicht '*' oder None ist
        if dst and dst != '\*': # '*' wurde escaped zu '\*'
            lines.append(f"*An:* `{dst}`")

        if msg_id:
            lines.append(f"*ID:* `{msg_id}`")

        # Typ-spezifische Formatierung
        if msg_type == 'msg' and 'msg' in message_dict:
            # Nachricht in einem Code-Block darstellen, um Formatierungsprobleme zu vermeiden
            message_text = message_dict['msg'] # Nicht escapen, da im Code-Block
            # Sicherstellen, dass der Code-Block korrekt geschlossen wird, auch wenn ``` drin vorkommt
            # Einfacher Ansatz: Ersetzen (nicht perfekt, aber oft ausreichend)
            message_text = message_text.replace('```', '`​`​`') # Zero-width spaces eingefügt
            lines.append(f"*Nachricht:* \n```\n{message_text}\n```")
        elif msg_type == 'pos' and 'lat' in message_dict and 'long' in message_dict:
            lat = message_dict.get('lat', '?')
            lon = message_dict.get('long', '?')
            alt = message_dict.get('alt')
            lat_str = escape_markdown_v2(str(lat))
            lon_str = escape_markdown_v2(str(lon))
            lines.append(f"*Position:* `{lat_str}, {lon_str}`")
            if alt is not None:
                lines.append(f"*Höhe:* `{escape_markdown_v2(str(alt))}m`")
            # OSM Link (URL braucht kein Escaping für Markdown)
            map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}"
            lines.append(f"[📍 Auf Karte anzeigen]({map_link})")
        elif msg_type == 'ack' and 'ack_id' in message_dict:
            ack_id = escape_markdown_v2(message_dict['ack_id'])
            lines.append(f"*Ack ID:* `{ack_id}`")
        elif msg_type == 'status' and 'msg' in message_dict:
            status_text = escape_markdown_v2(message_dict['msg'])
            lines.append(f"*Status:* {status_text}")
        elif msg_type == 'bulletin' and 'msg' in message_dict:
             bulletin_text = escape_markdown_v2(message_dict['msg'])
             lines.append(f"*Bulletin:* {bulletin_text}")

        # Fallback für unbekannte Typen oder wenn keine spezifischen Felder gefunden wurden
        if len(lines) <= 4: # Wenn nur die Standard-Header drin sind
             # Füge ggf. den rohen JSON hinzu (gekürzt?)
             raw_json = json.dumps(message_dict, ensure_ascii=False, separators=(',', ':'))
             lines.append(f"*Rohdaten:* `{escape_markdown_v2(raw_json[:200])}{'...' if len(raw_json) > 200 else ''}`")


        return "\n".join(lines)

    async def _send_async(self, formatted_message: str):
        """Asynchrone Hilfsmethode zum Senden der Nachricht."""
        if not self.bot:
            log.error("Telegram Bot ist nicht initialisiert. Senden nicht möglich.")
            return

        log.debug("Sende Nachricht an Telegram Chat ID %s", self.chat_id)
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted_message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            # Bei Erfolg nur noch debug loggen, um Logs nicht zu überfluten
            log.debug("Nachricht erfolgreich an Telegram gesendet.")
        except TelegramError as e:
            log.error("Telegram API Fehler beim Senden an Chat %s: %s", self.chat_id, e)
            # Bei bestimmten Fehlern könnte man hier spezifischer reagieren
            # z.B. bei 'Chat not found' das Forwarding temporär deaktivieren?
        except Exception as e:
             log.error("Unerwarteter Fehler beim Senden an Telegram.", exc_info=True)

    def send_message(self, message_dict: dict):
        """
        Formatiert und sendet ein Nachrichten-Dictionary an Telegram.
        Nutzt asyncio.run() zum Aufruf der asynchronen Sende-Methode.

        :param message_dict: Das geparste Dictionary der Nachricht.
        """
        if not self.bot:
            log.warning("Telegram Bot nicht initialisiert, überspringe Senden.")
            return

        # Nachricht formatieren
        formatted_message = self._format_message_markdown(message_dict)

        # --- Workaround für Aufruf von async aus sync Code ---
        # TODO: Effizienz prüfen und ggf. auf ThreadPoolExecutor oder dedizierten Async-Thread umstellen.
        log.debug("Versuche Nachricht asynchron via asyncio.run zu senden...")
        try:
            asyncio.run(self._send_async(formatted_message))
        except RuntimeError as e:
             # Dies kann passieren, wenn bereits ein Event-Loop im aktuellen Thread läuft.
             # In komplexeren Szenarien bräuchte man eine andere Lösung (z.B. asyncio.create_task
             # wenn man sich in einem Async-Kontext befindet, oder run_coroutine_threadsafe).
             log.error("RuntimeError beim Ausführen von asyncio.run (evtl. schon laufender Loop?): %s", e, exc_info=True)
        except Exception as e:
             # Fange andere mögliche Fehler vom asyncio.run selbst ab
             log.error("Unerwarteter Fehler bei asyncio.run.", exc_info=True)
        # --- Ende Workaround ---


# Beispielverwendung zum direkten Testen von forwarder.py
if __name__ == "__main__":
    # --- Minimales Setup für den Test ---
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')

    # === WICHTIG: ECHTE DATEN ZUM TESTEN BENÖTIGT ===
    # Entweder Umgebungsvariablen setzen:
    # export TELEGRAM_TEST_BOT_TOKEN="123456:ABC..."
    # export TELEGRAM_TEST_CHAT_ID="-100123456789" (für Gruppen) oder "987654321" (für User)
    # Oder die folgenden Zeilen direkt anpassen:
    test_bot_token = os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    test_chat_id = os.environ.get("TELEGRAM_TEST_CHAT_ID", "YOUR_TARGET_CHAT_ID_HERE")
    # ===============================================

    if "YOUR_" in test_bot_token or "YOUR_" in test_chat_id:
        log.error(">>> ECHTE Zugangsdaten benötigt zum Testen! <<<")
        log.error(">>> Setze TELEGRAM_TEST_BOT_TOKEN und TELEGRAM_TEST_CHAT_ID Umgebungsvariablen oder editiere das Skript. <<<")
        # sys.exit(1) # Auskommentiert, damit der Rest des Codes analysiert werden kann

    # Mock-Config erstellen
    mock_tg_config = SimpleNamespace(bot_token=test_bot_token, chat_id=test_chat_id)

    # Beispiel-Nachrichten
    sample_msg = {"src_type":"lora","type":"msg","src":"OE1TEST-1","dst":"ADMIN","msg":"Dies ist eine *Testnachricht* mit Markdown-Zeichen.\nUnd einem Backslash \\. Sowie ```code```","msg_id":"TEST001"}
    sample_pos = {"src_type":"lora","type":"pos","src":"OE3TEST-2","msg":"","lat":48.2082,"lat_dir":"N","long":16.3738,"long_dir":"E","aprs_symbol":"y","aprs_symbol_group":"/","hw_id":4,"msg_id":"TEST002","alt":156,"batt":100,"firmware":34,"fw_sub":"w"}
    sample_status = {"src_type":"node","type":"status", "src":"SYSTEM", "msg":"Listener gestartet."}
    sample_unknown = {"src_type":"node", "type":"unknown_type", "src":"DEVICE-X", "value": 123}

    log.info("--- Teste forwarder.py ---")

    try:
        forwarder = TelegramForwarder(mock_tg_config)

        # Optional: Verbindung testen (benötigt auch asyncio.run)
        # log.info("Teste Bot-Verbindung...")
        # asyncio.run(forwarder.test_connection())

        # Teste das Senden verschiedener Nachrichten
        log.info("Sende Test-Nachricht (msg)...")
        forwarder.send_message(sample_msg)
        time.sleep(2) # Kleine Pause

        log.info("Sende Test-Nachricht (pos)...")
        forwarder.send_message(sample_pos)
        time.sleep(2)

        log.info("Sende Test-Nachricht (status)...")
        forwarder.send_message(sample_status)
        time.sleep(2)

        log.info("Sende Test-Nachricht (unknown)...")
        forwarder.send_message(sample_unknown)

        log.info(">>> Test-Nachrichten wurden versucht zu senden. Überprüfe deinen Telegram-Chat! <<<")

    except ValueError as e:
         log.error("Fehler bei der Initialisierung des Forwarders (ungültige Config?): %s", e)
    except ImportError as e:
         log.error("Fehler bei der Initialisierung des Forwarders: %s", e)
    except Exception as e:
        log.error("Unerwarteter Fehler im Forwarder-Test.", exc_info=True)