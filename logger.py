# logger.py

import logging
import logging.handlers
import os
import sys
from types import SimpleNamespace # Nur für Type Hinting hier

# Logger für dieses Modul
log = logging.getLogger(__name__)

# Mapping von Konfigurations-Strings zu TimedRotatingFileHandler 'when' Parametern
INTERVAL_MAP = {
    "second": "S",
    "minute": "M",
    "hour": "H",
    "day": "D",
    "midnight": "MIDNIGHT", # Rotiert täglich um Mitternacht
    "monday": "W0",
    "tuesday": "W1",
    "wednesday": "W2",
    "thursday": "W3",
    "friday": "W4",
    "saturday": "W5",
    "sunday": "W6",
}

def setup_logging(logging_config: SimpleNamespace):
    """
    Konfiguriert das Python logging Framework basierend auf der übergebenen Konfiguration.

    Richtet Console und TimedRotatingFileHandler ein.

    :param logging_config: Ein SimpleNamespace-Objekt mit den Sektionen 'console' und 'file'
                           (typischerweise config.logging_config aus ConfigLoader).
    """
    try:
        root_logger = logging.getLogger() # Den Root-Logger holen

        # Vorhandene Handler entfernen, um Doppel-Logging bei versehentlichem Mehrfachaufruf zu vermeiden
        # Vorsicht: Entfernt auch potenzielle Default-Handler. Für die meisten Anwendungen ist das gewünscht.
        if root_logger.hasHandlers():
            log.debug("Entferne vorhandene Logging-Handler.")
            root_logger.handlers.clear()

        handlers = []
        min_level = logging.CRITICAL # Start mit dem höchsten Level

        # --- Konfiguriere Console Handler ---
        try:
            console_level_str = logging_config.console.level.upper()
            console_level = logging.getLevelName(console_level_str)
            min_level = min(min_level, console_level)

            # Verwende das Template vom File-Handler auch für die Konsole (oder mache es konfigurierbar)
            formatter = logging.Formatter(logging_config.file.output_template)

            console_handler = logging.StreamHandler(sys.stdout) # Loggt auf die Standardausgabe
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            handlers.append(console_handler)
            log.debug("Console-Handler konfiguriert mit Level %s.", console_level_str)
        except Exception as e:
            log.error("Fehler beim Konfigurieren des Console-Handlers.", exc_info=True)
            # Weitermachen, vielleicht funktioniert der File-Handler noch

        # --- Konfiguriere File Handler (Timed Rotating) ---
        try:
            file_level_str = logging_config.file.level.upper()
            file_level = logging.getLevelName(file_level_str)
            min_level = min(min_level, file_level)

            log_file_path = logging_config.file.path
            backup_count = logging_config.file.retained_file_count_limit

            # Verzeichnis für Logdatei erstellen, falls nicht vorhanden
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                    log.debug("Log-Verzeichnis '%s' erstellt.", log_dir)
                except OSError as e:
                    # Loggen, aber weitermachen - Handler-Erstellung wird wahrscheinlich fehlschlagen
                    log.error("Konnte Log-Verzeichnis '%s' nicht erstellen: %s", log_dir, e)

            # Rolling Interval validieren und mappen
            interval_setting = logging_config.file.rolling_interval.lower()
            when = INTERVAL_MAP.get(interval_setting)
            if not when:
                log.warning("Ungültiges 'rolling_interval': '%s' in der Konfiguration. Verwende 'day' (D) stattdessen.", interval_setting)
                when = 'D' # Fallback auf tägliche Rotation

            # Formatter (könnte auch pro Handler unterschiedlich sein, hier der Einfachheit halber gleich)
            file_formatter = logging.Formatter(logging_config.file.output_template)

            # Handler erstellen
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=log_file_path,
                when=when,
                interval=1, # Rotiert jedes Mal, wenn 'when' eintritt (z.B. jeden Tag, jede Stunde)
                backupCount=backup_count,
                encoding='utf-8',
                delay=True # Öffnet die Datei erst beim ersten Log-Eintrag (verhindert leere Dateien bei Start)
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(file_formatter)
            handlers.append(file_handler)
            log.debug("File-Handler konfiguriert für '%s' mit Level %s, Rotation '%s', %d Backups.",
                      log_file_path, file_level_str, when, backup_count)

        except PermissionError as e:
             log.error("Keine Berechtigung zum Erstellen/Schreiben der Log-Datei '%s'. Datei-Logging deaktiviert. %s", logging_config.file.path, e)
        except Exception as e:
            log.error("Fehler beim Konfigurieren des File-Handlers.", exc_info=True)
            # Weitermachen, vielleicht funktioniert der Console-Handler noch

        # --- Root Logger konfigurieren ---
        if not handlers:
            log.error("Keine Logging-Handler konnten erfolgreich konfiguriert werden!")
            # Optional: Minimal-Konfiguration als Fallback
            # logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(name)s: %(message)s')
            return # Beenden, wenn nichts geklappt hat

        root_logger.setLevel(min_level) # Setze Root auf das niedrigste benötigte Level
        for handler in handlers:
            root_logger.addHandler(handler)

        # Testnachricht, die jetzt über das konfigurierte System läuft
        log.info("Logging erfolgreich initialisiert. Root-Level: %s.", logging.getLevelName(min_level))
        log.debug("Verwendete Handler: %s", [type(h).__name__ for h in handlers])

    except AttributeError as e:
        log.critical("Fehler: Fehlende Konfigurationseinstellung im logging_config Objekt: %s", e, exc_info=True)
        raise ValueError(f"Fehlende Logging-Konfiguration: {e}")
    except Exception as e:
        log.critical("Unerwarteter kritischer Fehler während der Logging-Initialisierung.", exc_info=True)
        # Hier könnte man eine absolute Notfall-Logausgabe machen, falls alles schiefgeht
        print(f"!!! KRITISCHER FEHLER BEI LOGGING-INIT: {e}", file=sys.stderr)
        raise # Den Fehler weitergeben, damit das Hauptprogramm abbricht

# Beispiel für die Verwendung (im Hauptskript)
if __name__ == "__main__":
    # Dieser Teil dient nur zur Demonstration und zum Testen von logger.py direkt.
    # Im echten Programm wird setup_logging aus main.py aufgerufen.

    print("--- Teste logger.py ---")
    # Erstelle eine Beispiel-Konfiguration (normalerweise kommt die aus ConfigLoader)
    test_config_dict = {
        "console": {
            "level": "DEBUG"
        },
        "file": {
            "path": "logs/test_logger.log",
            "level": "INFO",
            "rolling_interval": "day",
            "retained_file_count_limit": 3,
            "output_template": "[%(asctime)s %(levelname)-8s] %(name)-15s: %(message)s"
        }
    }
    # Wandle das Dict in SimpleNamespace um, so wie es ConfigLoader tun würde
    test_logging_config = SimpleNamespace(
        console=SimpleNamespace(**test_config_dict["console"]),
        file=SimpleNamespace(**test_config_dict["file"])
    )

    print("Konfiguriere Logging mit Beispiel-Einstellungen...")
    try:
        setup_logging(test_logging_config)

        # Hol dir Logger für verschiedene "Module" und logge Testnachrichten
        main_log = logging.getLogger("main_test")
        db_log = logging.getLogger("database_test")

        main_log.debug("Dies ist eine Debug-Nachricht von main.") # Sollte nur auf Konsole erscheinen
        main_log.info("Dies ist eine Info-Nachricht von main.")   # Konsole + Datei
        db_log.warning("Dies ist eine Warnung von database.")     # Konsole + Datei
        db_log.error("Dies ist ein Fehler von database.")         # Konsole + Datei
        main_log.critical("Dies ist eine kritische Meldung.")     # Konsole + Datei

        print("\nLogging-Test abgeschlossen. Überprüfe die Konsole und die Datei 'logs/test_logger.log'.")
        print("Die Datei sollte INFO, WARNING, ERROR, CRITICAL enthalten.")
        print("Die Konsole sollte DEBUG, INFO, WARNING, ERROR, CRITICAL enthalten.")

    except Exception as e:
        print(f"\nFEHLER während des Logger-Tests: {e}", file=sys.stderr)
        # Im Fehlerfall Traceback manuell ausgeben, da Logging evtl. nicht geht
        import traceback
        traceback.print_exc()