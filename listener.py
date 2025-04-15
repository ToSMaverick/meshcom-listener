# listener.py

import socket
import json
import logging
import datetime
import time # Für eventuelle Pausen bei Fehlern
import sqlite3
import os # Für Umgebungsvariablen (z.B. Telegram Token)
from types import SimpleNamespace # Für Type Hinting

# database_handler Modul/Klasse importieren für Type Hinting
try:
    from database import DatabaseHandler
except ImportError:
    DatabaseHandler = object # type: ignore

# Logger für dieses Modul
log = logging.getLogger(__name__)

# forwarder Modul/Klasse importieren für Type Hinting und Instanziierung
try:
    from forwarder import TelegramForwarder
except ImportError:
    log.warning("Modul 'forwarder.py' nicht gefunden oder TelegramForwarder konnte nicht importiert werden.")
    TelegramForwarder = None # type: ignore

def _handle_packet(
    data: bytes,
    addr: tuple,
    received_time: datetime,
    db_handler: DatabaseHandler,
    forwarder: TelegramForwarder | None, # Kann None sein, wenn deaktiviert/Fehler
    store_types: list[str],
    forwarding_rules: list[dict]
):
    """
    Verarbeitet ein einzelnes empfangenes UDP-Paket.

    Dekodiert, parst JSON, loggt, filtert für Speicherung, filtert für Weiterleitung
    und ruft die entsprechenden Handler auf.

    :param data: Die rohen Empfangsdaten (Bytes).
    :param addr: Die Absenderadresse (Tuple(ip, port)).
    :param received_time: Der Zeitstempel des Empfangs.
    :param db_handler: Instanz des DatabaseHandler.
    :param forwarder: Instanz des TelegramForwarder oder None.
    :param store_types: Liste der Nachrichtentypen, die gespeichert werden sollen.
    :param forwarding_rules: Liste der Regeln für die Weiterleitung.
    """
    try:
        # 1. Als UTF-8 dekodieren
        message_str = data.decode('utf-8')

        # 2. Als JSON parsen
        message_dict = json.loads(message_str)

        # 3. Empfangene Nachricht als kompakten JSON-String loggen
        log_json_str = json.dumps(message_dict, ensure_ascii=False, separators=(',', ':'))
        log.info("UDP Nachricht empfangen von %s: %s", addr, log_json_str)

        # 4. Typ extrahieren für Filterung
        msg_type = message_dict.get('type')

        # 5. Filtern und in Datenbank speichern (falls Typ erlaubt)
        if msg_type in store_types:
            # Daten für DB extrahieren (wie zuvor, passend zur save_message Signatur)
            msg_id = message_dict.get('msg_id')
            source_raw = message_dict.get('src')
            cleaned_source = None
            if source_raw:
                cleaned_source = source_raw.split(',')[0].strip()
            dest = message_dict.get('dst')
            # Stelle sicher, dass dest None ist, wenn es fehlt oder leer ist, für die DB
            if not dest:
                dest = None

            try:
                db_handler.save_message(
                    msg_id=msg_id,
                    source=cleaned_source,
                    dest=dest,
                    msg_type=msg_type,
                    received_time=received_time,
                    raw_message_str=message_str
                )
                # Erfolgs-Logging passiert in save_message
            except sqlite3.Error as e:
                log.error("Datenbankfehler beim Speichern der Nachricht von %s (Typ: %s): %s", addr, msg_type, e, exc_info=True)
            except Exception as e:
                 log.error("Unerwarteter Fehler beim DB-Speichern der Nachricht von %s (Typ: %s).", addr, msg_type, exc_info=True)
        else:
            log.debug("Nachrichtentyp '%s' von %s wird nicht gespeichert (nicht in store_types: %s).", msg_type, addr, store_types)

        # 6. Filtern und Weiterleiten (falls Forwarder aktiv und Regeln vorhanden)
        if forwarder and forwarding_rules:
            msg_dst = message_dict.get('dst') # Ziel für die Regelprüfung holen

            for i, rule in enumerate(forwarding_rules):
                log.debug("Prüfe Weiterleitungsregel %d: %s", i, rule)
                # Prüfe Bedingungen der Regel
                type_match = ('type' not in rule) or (rule.get('type') == msg_type)
                dst_match = ('dst' not in rule) or (rule.get('dst') == msg_dst)
                # Hier könnten weitere Bedingungen wie 'src' hinzugefügt werden

                # Wenn alle Bedingungen der Regel zutreffen
                if type_match and dst_match:
                    log.info("Weiterleitungsregel %s passt für Nachricht von %s (Typ: %s, Dst: %s). Sende an Forwarder.", rule, addr, msg_type, msg_dst)
                    try:
                        # Rufe die send_message Methode des Forwarders auf
                        forwarder.send_message(message_dict)
                    except Exception as e:
                        # Fängt Fehler ab, die direkt beim Aufruf von send_message auftreten könnten
                        # (Intern sollte der Forwarder seine eigenen API-Fehler behandeln)
                        log.error("Fehler beim Aufruf von forwarder.send_message.", exc_info=True)
                    # Stoppe die Regelprüfung nach dem ersten Treffer (übliches Verhalten)
                    break # Aus der for rule Schleife ausbrechen
            else: # Wird ausgeführt, wenn die for-Schleife *nicht* durch break beendet wurde
                log.debug("Keine Weiterleitungsregel hat für Nachricht von %s gepasst.", addr)

    # Fehlerbehandlung für Dekodierung/Parsing *dieser einen* Nachricht
    except UnicodeDecodeError:
        log.warning("Konnte Nachricht von %s nicht als UTF-8 dekodieren. Größe: %d Bytes.", addr, len(data))
        log.debug("Rohdaten (Hex) von %s: %s", addr, data.hex())
    except json.JSONDecodeError as e:
        log.warning("Konnte Nachricht von %s nicht als JSON parsen: %s", addr, e)
        # Versuche den String zu loggen, falls Dekodierung erfolgreich war
        try:
            log.debug("Empfangener Text (fehlerhaftes JSON) von %s: %s", addr, data.decode('utf-8', errors='replace'))
        except: # Falls auch das Dekodieren schon vorher schiefging
             pass
    except Exception as e:
        # Fange alle anderen unerwarteten Fehler bei der Verarbeitung dieser Nachricht ab
        log.error("Unerwarteter Fehler bei Verarbeitung der Nachricht von %s.", addr, exc_info=True)
    # --- Ende Datenverarbeitung für einzelne Nachricht ---


# Hauptfunktion zum Starten des Listeners
def start_udp_listener(
    listener_config: SimpleNamespace,
    forwarding_config: SimpleNamespace, # Eigene Config für Forwarding
    db_handler: DatabaseHandler
):
    """
    Startet den UDP-Listener und initialisiert den Forwarder basierend auf der Konfiguration.

    :param listener_config: Konfigurationsobjekt für den Listener
                            (host, port, buffer_size, store_types).
    :param forwarding_config: Konfigurationsobjekt für das Forwarding
                              (enabled, rules, provider, telegram).
    :param db_handler: Eine Instanz des DatabaseHandler.
    """
    host = listener_config.host
    port = listener_config.port
    buffer_size = listener_config.buffer_size
    store_types = listener_config.store_types # Filterliste holen
    forwarding_rules = forwarding_config.rules # Regeln holen

    forwarder_instance: TelegramForwarder | None = None # Type Hinting

    # Forwarder initialisieren, falls aktiviert und möglich
    if forwarding_config.enabled:
        if TelegramForwarder: # Prüfen ob die Klasse importiert werden konnte
            log.info("Initialisiere %s Forwarder...", forwarding_config.provider)
            try:
                # Nur die Telegram-spezifische Konfig übergeben
                forwarder_instance = TelegramForwarder(forwarding_config.telegram)

                # Notifizierung an Telegram
                forwarder_instance.send_text(text="*MeshCom Listener* gestartet\\!", parse_mode='MarkdownV2')
               
            except (ValueError, ImportError, Exception) as e:
                 log.error("Fehler bei der Initialisierung des Telegram Forwarders. Forwarding bleibt deaktiviert.", exc_info=True)
                 forwarder_instance = None # Sicherstellen, dass es None ist bei Fehler
        else:
            log.warning("Forwarding ist aktiviert, aber das Forwarder-Modul/Klasse konnte nicht geladen werden.")
            forwarder_instance = None
    else:
        log.info("Forwarding ist in der Konfiguration deaktiviert.")
        forwarder_instance = None


    sock = None # Initialisieren für finally Block
    try:
        # UDP Socket erstellen und binden
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        log.info("UDP-Listener erfolgreich gestartet auf %s:%d", host, port)
        log.info("Nachrichten werden gespeichert für Typen: %s", store_types)
        if forwarder_instance:
            log.info("Nachrichten-Weiterleitung via %s ist AKTIV mit %d Regeln.", forwarding_config.provider, len(forwarding_rules))

        # Haupt-Empfangsschleife
        while True:
            try:
                # Daten empfangen
                data, addr = sock.recvfrom(buffer_size)
                received_time = datetime.datetime.now()

                # Verarbeitung an die separate Funktion übergeben
                _handle_packet(
                    data=data,
                    addr=addr,
                    received_time=received_time,
                    db_handler=db_handler,
                    forwarder=forwarder_instance,
                    store_types=store_types,
                    forwarding_rules=forwarding_rules
                )

            except KeyboardInterrupt:
                log.warning("KeyboardInterrupt empfangen, beende Listener-Schleife.")
                break # Verlässt die while True Schleife
            except socket.error as e:
                log.error("Schwerwiegender Socket-Fehler im Listener: %s", e, exc_info=True)
                time.sleep(1) # Kurze Pause
            except Exception as e:
                 log.critical("Unerwarteter Fehler in der Listener-Hauptschleife.", exc_info=True)
                 time.sleep(1) # Kurze Pause


    except socket.error as e:
        log.critical("Socket-Fehler beim Starten des Listeners auf %s:%d - %s", host, port, e, exc_info=True)
        raise # Fehler weitergeben
    except Exception as e:
        log.critical("Unerwarteter Fehler beim Initialisieren des Listeners.", exc_info=True)
        raise
    finally:
        # Aufräumen: Socket schließen
        if sock:
            try:
                sock.close()
                log.info("UDP-Socket auf %s:%d geschlossen.", host, port)
            except Exception as e:
                log.error("Fehler beim Schließen des Sockets.", exc_info=True)

# Der __main__ Block hier wird komplexer, da mehr Mocks benötigt werden.
# Er dient eher als Referenz und ist für echtes Testen weniger geeignet als Unit-Tests.
if __name__ == "__main__":
    # --- Minimales Setup für den isolierten Test ---
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
    log.info("--- Teste listener.py (isoliert) ---")

    # 1. Mock Listener Config
    mock_listener_cfg = SimpleNamespace(
        host="127.0.0.1",
        port=11799,
        buffer_size=1024,
        store_types=["msg", "ack", "status"] # Test: 'pos' nicht speichern
    )

    # 2. Mock Forwarding Config
    mock_forwarding_cfg = SimpleNamespace(
        enabled=True, # Test: Forwarding aktivieren
        provider="telegram",
        rules=[
            {"type": "msg", "dst": "ADMIN"}, # Nur Nachrichten an ADMIN
            {"type": "status"}             # Alle Statusmeldungen
        ],
        telegram=SimpleNamespace( # Benötigt für Forwarder-Initialisierung
            bot_token=os.environ.get("TELEGRAM_TEST_BOT_TOKEN", "FAKE_TOKEN_FOR_TEST"), # Sicherer Wert für Test ohne Senden
            chat_id=os.environ.get("TELEGRAM_TEST_CHAT_ID", "-12345") # Sicherer Wert
        )
    )
    # Hinweis: Wenn FAKE_TOKEN verwendet wird, wird der Forwarder initialisiert,
    # aber das Senden schlägt fehl (was ok ist für den Listener-Test).

    # 3. Mock Database Handler
    class MockDatabaseHandler:
        def save_message(self, msg_id, source, dest, msg_type, received_time, raw_message_str):
            log.info("[Mock DB] Speichere: ID=%s, Type=%s, Source=%s, Dest=%s", msg_id, msg_type, source, dest)
        def connect(self): pass
        def close(self): pass
    mock_db = MockDatabaseHandler()

    # 4. Mock Telegram Forwarder (optional, falls TelegramForwarder nicht importiert werden kann)
    if not TelegramForwarder:
        class MockTelegramForwarder:
            def __init__(self, config): log.info("[Mock FWD] Init mit %s", config)
            def send_message(self, msg_dict): log.info("[Mock FWD] Sende: %s", msg_dict.get('type'))
        # Überschreibe den importierten None-Wert
        TelegramForwarder = MockTelegramForwarder

    print(f"Starte Test-Listener auf {mock_listener_cfg.host}:{mock_listener_cfg.port}")
    print(f"  Speichert Typen: {mock_listener_cfg.store_types}")
    print(f"  Leitet weiter für Regeln: {mock_forwarding_cfg.rules}")
    print("Sende Testpakete (Strg+C zum Beenden):")
    print(f"  echo '{{\"type\":\"msg\", \"src\":\"TEST-1\", \"dst\":\"USER\", \"msg\":\"Hallo\"}}' | nc -u {mock_listener_cfg.host} {mock_listener_cfg.port}")
    print(f"  echo '{{\"type\":\"msg\", \"src\":\"TEST-2\", \"dst\":\"ADMIN\", \"msg\":\"Wichtig\"}}' | nc -u {mock_listener_cfg.host} {mock_listener_cfg.port}")
    print(f"  echo '{{\"type\":\"pos\", \"src\":\"TEST-POS\", \"lat\":10, \"lon\":10}}' | nc -u {mock_listener_cfg.host} {mock_listener_cfg.port}")
    print(f"  echo '{{\"type\":\"status\", \"src\":\"SYSTEM\", \"msg\":\"Bereit\"}}' | nc -u {mock_listener_cfg.host} {mock_listener_cfg.port}")

    try:
        start_udp_listener(mock_listener_cfg, mock_forwarding_cfg, mock_db)
    except Exception as e:
        log.error("Fehler während des Listener-Tests.", exc_info=True)
    finally:
        log.info("Test von listener.py beendet.")