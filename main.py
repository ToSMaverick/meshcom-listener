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
    except ValueError as e: # Fängt Validierungsfehler von ConfigLoader ab
        # Minimales Logging für den Fall, dass ConfigLoader schon scheitert
        logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] CRITICAL CONFIG ERROR: %(message)s')
        logging.error("Fehler in der Konfigurationsdatei: %s", e)
        sys.exit(1) # Beenden, wenn die Konfiguration nicht geladen/validiert werden kann
    except Exception as e:
        logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] CRITICAL CONFIG ERROR: %(message)s')
        logging.error("Kritischer Fehler beim Laden der Konfiguration: %s", e, exc_info=True)
        sys.exit(1)

    # 2. Logging initialisieren (JETZT erst, nachdem die Config geladen und validiert wurde!)
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
    log.info("Starte MeshCom UDP Listener...")

    # 3. Datenbank-Handler vorbereiten und Listener starten
    db_handler = None # Initialisieren für den Fall, dass die Erstellung fehlschlägt
    try:
        # DatabaseHandler wird erstellt. Die Verbindung wird erst
        # beim Eintritt in den 'with'-Block aufgebaut oder durch manuelles connect().
        db_handler = DatabaseHandler(config.database)

        # Verwendung des 'with'-Statements für den DatabaseHandler.
        # __enter__ stellt die DB-Verbindung her.
        # __exit__ schließt die DB-Verbindung am Ende, auch bei Fehlern oder Strg+C.
        with db_handler:
            log.info("Datenbank-Handler bereit und verbunden mit '%s'.", config.database.db_file)

            # 4. Listener starten
            # Der Listener läuft nun innerhalb des 'with'-Blocks.
            # Er erhält die spezifischen Konfigurationsteile und den aktiven db_handler.
            log.info("Starte UDP-Listener...")
            start_udp_listener(
                listener_config=config.listener,      # Listener-spezifische Konfig übergeben
                forwarding_config=config.forwarding,  # Forwarding-spezifische Konfig übergeben
                db_handler=db_handler                 # Aktiven DB-Handler übergeben
            )
            # Der Code hier wird erst erreicht, nachdem start_udp_listener
            # normal beendet wurde (was in der aktuellen Endlosschleife nur durch
            # interne Fehler oder Signale wie KeyboardInterrupt geschieht).

        # Der 'with'-Block wurde verlassen, db_handler.__exit__ hat die DB geschlossen.
        log.info("Listener beendet und Datenbankverbindung geschlossen.")

    except KeyboardInterrupt:
        # Wird gefangen, wenn Strg+C gedrückt wird.
        # Die Bereinigung (DB schließen via 'with', Socket schließen im Listener)
        # sollte bereits erfolgt sein oder im Gange sein.
        log.warning("Anwendung durch Benutzer (Strg+C) beendet.")
    except ValueError as e: # Fehler von ConfigLoader Validierung oder DatabaseHandler Init
        log.critical("Konfigurations- oder Initialisierungsfehler: %s", e)
        sys.exit(1)
    except sqlite3.Error as e: # Datenbankfehler beim Verbinden oder Setup im __enter__
        log.critical("Schwerwiegender Datenbankfehler beim Start: %s", e, exc_info=True)
        sys.exit(1)
    except ImportError as e: # Z.B. wenn python-telegram-bot fehlt
        log.critical("Fehlendes Modul: %s. Bitte Abhängigkeiten installieren.", e)
        sys.exit(1)
    except SystemExit as e: # Fängt sys.exit() ab, falls nötig
         # Normalerweise sollte dies nicht direkt hier auftreten, es sei denn,
         # eine der aufgerufenen Funktionen ruft sys.exit() auf.
         log.info("SystemExit wurde aufgerufen: %s", e)
         # Nicht erneut sys.exit() aufrufen, sondern den Exit-Code übernehmen
         # oder den Fehler einfach weitergeben, damit das Programm endet.
         # Wenn exit() mit Code 0 war, ist es kein Fehler.
         if e.code != 0:
              log.error("Programm wurde mit Fehlercode beendet: %s", e.code)
         # raise # Optional: Exception weitergeben, wenn man sie nicht hier behandeln will
         sys.exit(e.code or 1) # Beenden mit dem Code aus SystemExit oder 1 als Fallback
    except Exception as e: # Fängt alle anderen unerwarteten Fehler ab
        log.critical("Unerwarteter Fehler im Hauptprogramm:", exc_info=True)
        # Sicherstellen, dass die DB-Verbindung geschlossen wird, falls 'with' nicht erreicht/beendet wurde
        if db_handler and db_handler.connection:
            log.warning("Versuche Notfall-Schließung der Datenbankverbindung.")
            db_handler.close()
        sys.exit(1) # Bei schweren Fehlern beenden

    log.info("Anwendung sauber beendet.")
    sys.exit(0) # Expliziter Exit-Code 0 für Erfolg