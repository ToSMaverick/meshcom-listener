import logging
import sys
import sqlite3
from config import ConfigLoader
from logger import setup_logging
from database import DatabaseHandler # Klasse importieren
# from udp_listener import start_udp_listener # (Nächster Schritt)

if __name__ == "__main__":
    # 1. Config laden
    try:
        config = ConfigLoader()
    except Exception as e:
        # Minimales Logging für den Fall, dass ConfigLoader schon scheitert
        logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] CRITICAL CONFIG ERROR: %(message)s')
        logging.error("Fehler beim Laden der Konfiguration: %s", e)
        sys.exit(1)

    # 2. Logging initialisieren (JETZT erst!)
    try:
        setup_logging(config.logging_config) # Übergabe des Logging-Teils der Config
    except Exception as e:
        # Falls Logging-Setup scheitert, versuchen mit Print auszugeben
        print(f"!!! KRITISCHER FEHLER BEIM LOGGING SETUP: {e}", file=sys.stderr)
        sys.exit(1)
        
    log = logging.getLogger(__name__) # Logger für main.py

    # 3. Datenbank initialisieren (als Context Manager für sauberes Schließen)
    try:
        # DatabaseHandler wird erstellt, Verbindung aber erst im 'with' aufgebaut
        db_handler = DatabaseHandler(config.database)

        with db_handler: # Stellt Verbindung her, schließt sie am Ende automatisch
            log.info("Datenbank-Handler bereit.")

            # 4. Listener starten und DB-Handler übergeben
            # (Hier wird der Listener gestartet und bekommt eine Referenz
            # auf die save_message Methode des aktiven db_handler)
            # start_udp_listener(
            #     listener_config=config.listener,
            #     db_handler=db_handler # Übergabe des gesamten Handlers
            # )
            # ACHTUNG: Der Listener läuft normalerweise "ewig".
            #          Das `with`-Statement endet erst, wenn der Block verlassen wird.
            #          Für einen dauerhaft laufenden Listener ist ein `with`-Block
            #          im Hauptskript evtl. unpraktisch. Alternativ:
            #          db_handler.connect() am Anfang aufrufen und
            #          db_handler.close() in einem try...finally Block am Ende
            #          des Hauptprogramms oder bei Signal-Handhabung (Strg+C).

            # --- Alternative für langlebigen Listener ---
            try:
                db_handler.connect() # Manuell verbinden
                log.info("Datenbank-Handler manuell verbunden.")
                # start_udp_listener(listener_config=config.listener, db_handler=db_handler)
                # Hier würde der Listener laufen... z.B. in einer Endlosschleife
                # oder bis er durch ein Signal gestoppt wird.
                # Simulieren wir das Laufen für den Moment:
                print("Listener würde jetzt laufen... (Drücke Strg+C zum Beenden in einer echten App)")
                import time
                while True: # Beispiel für einen laufenden Prozess
                    time.sleep(10)

            except KeyboardInterrupt:
                 log.info("Anwendung durch Benutzer beendet (Strg+C).")
            finally:
                 log.info("Räume auf...")
                 db_handler.close() # Manuell schließen im finally-Block
            # --- Ende Alternative ---


    except ValueError as e: # Fehler von ConfigLoader oder DatabaseHandler Init
        log.critical("Konfigurations- oder Initialisierungsfehler: %s", e)
        sys.exit(1)
    except sqlite3.Error as e:
        log.critical("Schwerwiegender Datenbankfehler beim Start: %s", e, exc_info=True)
        sys.exit(1)
    except Exception as e:
        log.critical("Unerwarteter Fehler im Hauptprogramm:", exc_info=True)
        sys.exit(1)

    log.info("Anwendung sauber beendet.")