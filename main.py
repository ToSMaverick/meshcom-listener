# main.py

import logging
import sys
import sqlite3 # Nötig für die Fehlerbehandlung spezifischer DB-Fehler
from config import ConfigLoader
from logger import setup_logging
from database import DatabaseHandler   # Klasse importieren
from listener import start_udp_listener # Listener-Funktion importieren

if __name__ == "__main__":
    # 1. Config laden
    try:
        config = ConfigLoader()
        # Stellen Sie sicher, dass die Konfiguration geladen wird, bevor der Logger sie verwendet
    except Exception as e:
        # Minimales Logging für den Fall, dass ConfigLoader schon scheitert
        logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] CRITICAL CONFIG ERROR: %(message)s')
        logging.error("Fehler beim Laden der Konfiguration: %s", e)
        sys.exit(1) # Beenden, wenn die Konfiguration nicht geladen werden kann

    # 2. Logging initialisieren (JETZT erst, nachdem die Config geladen wurde!)
    try:
        setup_logging(config.logging_config) # Übergabe des Logging-Teils der Config
    except Exception as e:
        # Falls Logging-Setup scheitert, versuchen mit Print auszugeben
        # Verwenden Sie logging hier, falls basicConfig funktioniert hat, sonst print
        try:
             logging.critical("!!! KRITISCHER FEHLER BEIM LOGGING SETUP: %s", e, exc_info=True)
        except:
             print(f"!!! KRITISCHER FEHLER BEIM LOGGING SETUP: {e}", file=sys.stderr)
        sys.exit(1) # Beenden, wenn Logging nicht initialisiert werden kann

    # Logger für das Hauptmodul holen (jetzt, wo Logging konfiguriert ist)
    log = logging.getLogger(__name__)

    log.info("Anwendungskonfiguration und Logging initialisiert.")

    # 3. Datenbank-Handler vorbereiten und Listener starten
    try:
        # DatabaseHandler wird erstellt. Die Verbindung wird erst
        # beim Eintritt in den 'with'-Block aufgebaut.
        db_handler = DatabaseHandler(config.database)

        # Verwendung des 'with'-Statements für den DatabaseHandler.
        # __enter__ stellt die DB-Verbindung her.
        # __exit__ schließt die DB-Verbindung am Ende, auch bei Fehlern oder Strg+C.
        with db_handler:
            log.info("Datenbank-Handler bereit und verbunden.")

            # 4. Listener starten
            # Der Listener läuft nun innerhalb des 'with'-Blocks.
            # Er erhält die Listener-Konfiguration und den aktiven db_handler.
            log.info("Starte UDP-Listener...")
            start_udp_listener(
                listener_config=config.listener,
                db_handler=db_handler # Übergabe des gesamten Handlers
            )
            # Der Code hier wird erst erreicht, nachdem start_udp_listener
            # beendet wurde (z.B. durch Strg+C im Listener).

        # Der 'with'-Block wurde verlassen, __exit__ hat die DB geschlossen.
        log.info("Listener beendet und Datenbankverbindung geschlossen.")

    except KeyboardInterrupt:
        # Wird gefangen, wenn Strg+C gedrückt wird, *nachdem* der Listener
        # seine eigene KeyboardInterrupt-Behandlung abgeschlossen hat und
        # die Exception möglicherweise weitergereicht wurde (oder wenn Strg+C
        # außerhalb des Listener-Hauptloops auftritt).
        log.warning("Anwendung durch Benutzer (Strg+C) beendet.")
        # Die Ressourcen (DB durch 'with', Socket durch 'finally' im Listener)
        # sollten bereits geschlossen sein.
    except ValueError as e: # Fehler von ConfigLoader Validierung oder DatabaseHandler Init
        log.critical("Konfigurations- oder Initialisierungsfehler: %s", e)
        sys.exit(1)
    except sqlite3.Error as e: # Datenbankfehler beim Verbinden oder Setup
        log.critical("Schwerwiegender Datenbankfehler beim Start: %s", e, exc_info=True)
        sys.exit(1)
    except SystemExit as e: # Fängt sys.exit() ab, falls nötig (normalerweise nicht)
         log.info("SystemExit aufgerufen: %s", e)
         raise # SystemExit weitergeben, um das Programm wirklich zu beenden
    except Exception as e: # Fängt alle anderen unerwarteten Fehler ab
        log.critical("Unerwarteter Fehler im Hauptprogramm:", exc_info=True)
        sys.exit(1) # Bei schweren Fehlern beenden

    log.info("Anwendung sauber beendet.")
    sys.exit(0) # Expliziter Exit-Code 0 für Erfolg