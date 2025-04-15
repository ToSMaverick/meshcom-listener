# listener.py

import socket
import json
import logging
import datetime
import time # Für eventuelle Pausen bei Fehlern
import sqlite3
from types import SimpleNamespace # Für Type Hinting

# database_handler Modul/Klasse importieren für Type Hinting
try:
    from database import DatabaseHandler
except ImportError:
    # Fallback, falls Type Hinting in einer Umgebung ohne die Datei fehlschlägt
    DatabaseHandler = object # type: ignore

# Logger für dieses Modul
log = logging.getLogger(__name__)

def start_udp_listener(listener_config: SimpleNamespace, db_handler: DatabaseHandler):
    """
    Startet einen UDP-Listener auf dem konfigurierten Host und Port.

    Empfängt Nachrichten, versucht sie als JSON zu parsen, loggt sie
    als kompakten JSON-String und speichert sie über den DatabaseHandler.

    :param listener_config: Konfigurationsobjekt für den Listener
                            (erwartet host, port, buffer_size).
    :param db_handler: Eine Instanz des DatabaseHandler zum Speichern der Nachrichten.
    """
    host = listener_config.host
    port = listener_config.port
    buffer_size = listener_config.buffer_size

    sock = None # Initialisieren für finally Block
    try:
        # UDP Socket erstellen
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Wiederverwendung der Adresse erlauben (hilfreich bei schnellen Neustarts)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Socket binden
        sock.bind((host, port))
        log.info("UDP-Listener erfolgreich gestartet auf %s:%d", host, port)

        # Haupt-Empfangsschleife
        while True: # Läuft ewig, bis z.B. Strg+C kommt
            try:
                # Daten empfangen
                # recvfrom gibt (bytes, address) zurück
                data, addr = sock.recvfrom(buffer_size)
                received_time = datetime.datetime.now() # Zeitstempel sofort nehmen

                # --- Datenverarbeitung für einzelne Nachricht ---
                try:
                    # 1. Als UTF-8 dekodieren
                    message_str = data.decode('utf-8')

                    # 2. Als JSON parsen
                    message_dict = json.loads(message_str)

                    # 3. Nachricht als kompakten JSON-String loggen
                    #    separators=(',', ':') erzeugt den kompaktesten String ohne Leerzeichen
                    log_json_str = json.dumps(message_dict, ensure_ascii=False, separators=(',', ':'))
                    # INFO-Level wurde gewünscht, DEBUG könnte bei hoher Last besser sein
                    log.info("UDP Nachricht empfangen von %s: %s", addr, log_json_str)

                    # 4. Daten für DB extrahieren
                    msg_id = message_dict.get('msg_id') # Sicherer Zugriff mit .get()
                    msg_src = message_dict.get('src')
                    if msg_src:
                        # Nimmt den ersten Eintrag vor Komma, entfernt eventuelle Leerzeichen
                        msg_src = msg_src.split(',')[0].strip()
                    msg_type = message_dict.get('type')

                    # 5. In Datenbank speichern
                    db_handler.save_message(
                        msg_id=msg_id,
                        source=msg_src,
                        msg_type=msg_type,
                        received_time=received_time,
                        raw_message_str=message_str # Den dekodierten String speichern
                    )
                    # Die save_message Methode loggt bereits Erfolg/Misserfolg intern

                # Fehlerbehandlung für *diese eine* Nachricht
                except UnicodeDecodeError:
                    log.warning("Konnte Nachricht von %s nicht als UTF-8 dekodieren. Größe: %d Bytes.", addr, len(data))
                    # Optional: Rohdaten loggen (als Hex)
                    # log.debug("Rohdaten (Hex) von %s: %s", addr, data.hex())
                except json.JSONDecodeError as e:
                    log.warning("Konnte Nachricht von %s nicht als JSON parsen: %s", addr, e)
                    log.debug("Empfangener Text von %s: %s", addr, message_str) # Logge den fehlerhaften String
                except sqlite3.Error as e: # Import sqlite3 oben nötig für spezifisches Except
                    log.error("Datenbankfehler beim Speichern der Nachricht von %s: %s", addr, e, exc_info=True)
                    # Listener läuft weiter, aber diese Nachricht fehlt in der DB
                except Exception as e:
                    # Fange alle anderen unerwarteten Fehler bei der Nachrichtenverarbeitung ab
                    log.error("Unerwarteter Fehler bei Verarbeitung der Nachricht von %s.", addr, exc_info=True)
                # --- Ende Datenverarbeitung für einzelne Nachricht ---

            except KeyboardInterrupt:
                # Fange Strg+C ab, um die Schleife sauber zu beenden
                log.warning("KeyboardInterrupt empfangen, beende Listener-Schleife.")
                break # Verlässt die while True Schleife
            except socket.error as e:
                # Schwerwiegendere Socket-Fehler (außerhalb von recvfrom?)
                log.error("Schwerwiegender Socket-Fehler im Listener: %s", e, exc_info=True)
                # Optional: Kurze Pause vor erneutem Versuch oder Abbruch?
                time.sleep(1)
            except Exception as e:
                 # Fange alle anderen Fehler in der Hauptschleife ab
                 log.critical("Unerwarteter Fehler in der Listener-Hauptschleife.", exc_info=True)
                 time.sleep(1) # Kurze Pause, um Endlosschleifen bei permanenten Fehlern zu vermeiden


    except socket.error as e:
        # Fehler beim Binden des Sockets (z.B. Port belegt)
        log.critical("Socket-Fehler beim Starten des Listeners auf %s:%d - %s", host, port, e, exc_info=True)
        # Hier sollte das Hauptprogramm informiert werden oder abbrechen
        raise # Fehler weitergeben, damit main.py ihn behandeln kann
    except Exception as e:
        # Andere unerwartete Fehler beim Setup
        log.critical("Unerwarteter Fehler beim Initialisieren des Listeners.", exc_info=True)
        raise
    finally:
        # Aufräumen: Socket schließen, falls er erstellt wurde
        if sock:
            try:
                sock.close()
                log.info("UDP-Socket auf %s:%d geschlossen.", host, port)
            except Exception as e:
                log.error("Fehler beim Schließen des Sockets.", exc_info=True)

# Beispielhafte Verwendung (wird typischerweise aus main.py aufgerufen)
if __name__ == "__main__":
    # Dieser Block dient nur zum Testen von listener.py isoliert.
    # Erfordert das manuelle Erstellen von Mock-Objekten oder eine
    # sehr einfache Konfiguration.

    # --- Minimales Setup für den Test ---
    import sys
    # 1. Logging basic config (damit man was sieht)
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')

    # 2. Mock Config erstellen
    class MockListenerConfig(SimpleNamespace):
        host = "127.0.0.1"
        port = 11799 # Anderer Port als Default, um Konflikte zu vermeiden
        buffer_size = 1024

    test_listener_config = MockListenerConfig()

    # 3. Mock Database Handler (druckt nur statt zu speichern)
    class MockDatabaseHandler:
        def save_message(self, received_time, msg_type, source, raw_message_str):
            log.info("[Mock DB] Speichere: Time=%s, Type=%s, Source=%s, Raw=%s",
                     received_time.isoformat(), msg_type, source, raw_message_str)
            # Simuliere eine DB-ID
            return time.time_ns()

        def connect(self): # Mock-Methode
             log.info("[Mock DB] connect() aufgerufen.")

        def close(self): # Mock-Methode
             log.info("[Mock DB] close() aufgerufen.")


    mock_db = MockDatabaseHandler()
    # --- Ende Setup ---

    log.info("--- Teste listener.py ---")
    print(f"Starte Test-Listener auf {test_listener_config.host}:{test_listener_config.port}")
    print("Du kannst jetzt UDP-Pakete an diesen Port senden, z.B. mit netcat:")
    print(f"  echo '{{\"type\":\"msg\", \"src\":\"TEST-1\", \"msg\":\"Hallo Welt\"}}' | nc -u {test_listener_config.host} {test_listener_config.port}")
    print("Drücke Strg+C, um den Test-Listener zu beenden.")

    try:
        # Listener starten
        start_udp_listener(test_listener_config, mock_db)
    except Exception as e:
        log.error("Fehler während des Listener-Tests.", exc_info=True)
    finally:
        log.info("Test von listener.py beendet.")