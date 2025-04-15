# config.py

import json
import os
import logging # Logging-Modul importieren
from types import SimpleNamespace

# Logger für dieses Modul initialisieren (Konfiguration erfolgt später extern)
log = logging.getLogger(__name__)

CONFIG_FILENAME = "config.json"

# Standardkonfiguration
DEFAULT_CONFIG = {
    "database": {
        "db_file": "db/meshcom_messages.db",
        "table_name": "messages"
    },
    "listener": {
        "host": "0.0.0.0",
        "port": 1799,
        "buffer_size": 2048,
        "store_types": [ # NEU: Nur diese Typen speichern
            "msg"
            # "pos" standardmäßig ausgelassen
        ]
    },
    "logging": {
        "console": {
            "level": "INFO"
        },
        "file": {
            "path": "logs/MeshComListener.log",
            "level": "INFO",
            "rolling_interval": "day",
            "retained_file_count_limit": 7,
            "output_template": "[%(asctime)s %(levelname)s] %(name)s: %(message)s"
        }
    },
    "forwarding": { # NEU: Komplette Sektion für Weiterleitung
        "enabled": False,
        "provider": "telegram", # Aktuell nur Telegram unterstützt
        "rules": [ # Leere Liste als Default
            # Beispielregeln (werden aus config.json geladen, falls vorhanden):
            # {"type": "msg", "dst": "232"},  # Leite Nachrichten an die AT-Gruppe weiter
            # {"type": "pos"}              # Leite alle Positionsmeldungen weiter
        ],
        "telegram": {
            "bot_token": "YOUR_BOT_TOKEN_HERE", # Muss in config.json gesetzt werden!
            "chat_id": "YOUR_TARGET_CHAT_ID_HERE" # Muss in config.json gesetzt werden!
        }
    }
}

class ConfigLoader:
    """
    Lädt die Konfiguration aus einer JSON-Datei oder erstellt eine Standarddatei,
    falls diese nicht existiert. Stellt die Konfiguration über Attribute
    bereit (z.B. config.database.db_file, config.listener.store_types, config.forwarding.enabled).
    Verwendet das logging-Modul für Ausgaben.
    """
    def __init__(self, filename=CONFIG_FILENAME):
        """
        Initialisiert den ConfigLoader.

        :param filename: Pfad zur JSON-Konfigurationsdatei.
        """
        self.filename = filename
        self.database = None
        self.listener = None
        self.logging_config = None
        self.forwarding = None

        config_data = self._load_or_create()
        self._populate_attributes(config_data)
        self._validate_config() # Grundlegende Prüfung der Werte

    def _load_config_file(self):
        """Versucht, die Konfigurationsdatei zu laden."""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                log.info("Konfiguration aus '%s' geladen.", self.filename)
                return loaded_config
        except FileNotFoundError:
            log.info("Konfigurationsdatei '%s' nicht gefunden.", self.filename)
            return None
        except json.JSONDecodeError as e:
            log.error("Konfigurationsdatei '%s' enthält ungültiges JSON: %s", self.filename, e)
            return None # Behandle ungültige Datei wie nicht vorhanden
        except PermissionError:
            log.error("Keine Leseberechtigung für '%s'.", self.filename)
            raise # Bei Berechtigungsproblemen besser abbrechen
        except Exception as e:
            log.error("Unerwarteter Fehler beim Lesen von '%s'.", self.filename, exc_info=True) # Mit Traceback loggen
            raise # Bei anderen Fehlern auch abbrechen


    def _create_default_config(self):
        """Erstellt die Standardkonfigurationsdatei."""
        log.warning("Erstelle Standardkonfiguration in '%s'.", self.filename)
        try:
            # Sicherstellen, dass das Verzeichnis existiert, falls der Pfad komplexer ist
            conf_dir = os.path.dirname(self.filename)
            if conf_dir and not os.path.exists(conf_dir):
                 os.makedirs(conf_dir, exist_ok=True)
                 log.info("Verzeichnis '%s' für Konfigurationsdatei erstellt.", conf_dir)

            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            log.info("Standardkonfiguration erfolgreich in '%s' erstellt.", self.filename)
            return DEFAULT_CONFIG
        except PermissionError:
            log.error("Keine Schreibberechtigung für '%s'. Standardwerte werden verwendet, aber nicht gespeichert.", self.filename)
            # Im Speicher trotzdem die Defaults verwenden
            return DEFAULT_CONFIG
        except Exception as e:
            log.error("Unerwarteter Fehler beim Erstellen von '%s'. Standardwerte werden verwendet.", self.filename, exc_info=True)
            # Im Speicher trotzdem die Defaults verwenden, aber Fehler anzeigen
            return DEFAULT_CONFIG

    def _merge_configs(self, default, loaded):
        """
        Führt die geladene Konfiguration mit den Standardwerten zusammen.
        Werte aus der geladenen Datei haben Vorrang. Fehlende Sektionen/Keys
        werden aus den Defaults übernommen (tiefer Merge für verschachtelte Dicts).
        """
        merged = default.copy()
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_configs(merged[key], value) # Rekursiv für verschachtelte Dicts
            else:
                merged[key] = value # Überschreiben oder hinzufügen
        return merged

    def _load_or_create(self):
        """Lädt die Konfiguration oder erstellt sie, falls nötig."""
        loaded_config = self._load_config_file()

        if loaded_config is None:
            # Datei nicht gefunden, ungültig oder Lesefehler (außer PermissionError)
            # -> Versuche, Standard zu erstellen und zu verwenden
            config_data = self._create_default_config()
        else:
            # Datei erfolgreich geladen -> mit Defaults zusammenführen
            log.info("Führe geladene Konfiguration mit Standardwerten zusammen.")
            config_data = self._merge_configs(DEFAULT_CONFIG, loaded_config)

        return config_data

    def _populate_attributes(self, config_data):
        """Wandelt das Konfigurations-Dict in SimpleNamespace-Attribute um."""
        # Sicherstellen, dass alle Hauptsektionen vorhanden sind (ggf. aus Defaults)
        db_settings = config_data.get("database", DEFAULT_CONFIG["database"])
        listener_settings = config_data.get("listener", DEFAULT_CONFIG["listener"])
        logging_settings = config_data.get("logging", DEFAULT_CONFIG["logging"])
        forwarding_settings = config_data.get("forwarding", DEFAULT_CONFIG["forwarding"]) # NEU

        self.database = SimpleNamespace(**db_settings)
        # SimpleNamespace(**dict) fügt alle Keys aus dem Dict als Attribute hinzu
        self.listener = SimpleNamespace(**listener_settings) # store_types wird automatisch hinzugefügt

        # Für Logging auch die inneren Strukturen (console, file) als Namespace anlegen
        log_console_settings = logging_settings.get("console", DEFAULT_CONFIG["logging"]["console"])
        log_file_settings = logging_settings.get("file", DEFAULT_CONFIG["logging"]["file"])
        self.logging_config = SimpleNamespace(
             console=SimpleNamespace(**log_console_settings),
             file=SimpleNamespace(**log_file_settings)
        )

        # NEU: Für Forwarding ebenfalls verschachtelte Namespaces erstellen
        telegram_settings = forwarding_settings.get("telegram", DEFAULT_CONFIG["forwarding"]["telegram"])
        self.forwarding = SimpleNamespace(
            enabled=forwarding_settings.get("enabled", DEFAULT_CONFIG["forwarding"]["enabled"]),
            provider=forwarding_settings.get("provider", DEFAULT_CONFIG["forwarding"]["provider"]),
            rules=forwarding_settings.get("rules", DEFAULT_CONFIG["forwarding"]["rules"]),
            telegram=SimpleNamespace(**telegram_settings)
        )

        log.debug("Konfigurationsattribute erfolgreich erstellt.")

    def _validate_config(self):
        """Prüft grundlegende Typen und Werte der Konfiguration."""
        try:
            # --- Datenbank-Validierung ---
            if not isinstance(self.database.db_file, str) or not self.database.db_file:
                raise ValueError("Ungültiger oder fehlender Wert für database.db_file.")
            if not isinstance(self.database.table_name, str) or not self.database.table_name:
                raise ValueError("Ungültiger oder fehlender Wert für database.table_name.")

            # --- Listener-Validierung ---
            if not isinstance(self.listener.host, str):
                raise ValueError("Ungültiger oder fehlender Wert für listener.host.")
            if not isinstance(self.listener.port, int) or not (0 < self.listener.port < 65536):
                raise ValueError(f"Ungültiger Wert für listener.port '{self.listener.port}' (muss eine Zahl zwischen 1 und 65535 sein).")
            if not isinstance(self.listener.buffer_size, int) or self.listener.buffer_size <= 0:
                raise ValueError(f"Ungültiger Wert für listener.buffer_size '{self.listener.buffer_size}' (muss eine positive Zahl sein).")
            # NEU: store_types prüfen
            if not hasattr(self.listener, 'store_types') or not isinstance(self.listener.store_types, list):
                 raise ValueError("Ungültiger oder fehlender Wert für listener.store_types (muss eine Liste sein).")
            if not all(isinstance(item, str) for item in self.listener.store_types):
                 raise ValueError("listener.store_types darf nur Strings enthalten.")
            log.debug("Zu speichernde Typen: %s", self.listener.store_types)


            # --- Logging-Validierung ---
            valid_log_levels = logging._nameToLevel.keys() # Holt die Namen der Log-Level
            if not isinstance(self.logging_config.console.level, str) or self.logging_config.console.level.upper() not in valid_log_levels:
                raise ValueError(f"Ungültiger Wert für logging.console.level '{self.logging_config.console.level}'. Gültige Werte: {list(valid_log_levels)}")
            if not isinstance(self.logging_config.file.path, str) or not self.logging_config.file.path:
                 raise ValueError("Ungültiger oder fehlender Wert für logging.file.path.")
            # Sicherstellen, dass das Verzeichnis für die Log-Datei erstellt werden kann (prüft nicht Schreibrechte!)
            log_file_dir = os.path.dirname(self.logging_config.file.path)
            if log_file_dir: # Nur wenn ein Pfad angegeben ist (nicht nur Dateiname)
                 try:
                      os.makedirs(log_file_dir, exist_ok=True)
                      log.debug("Verzeichnis '%s' für Logdatei sichergestellt.", log_file_dir)
                 except OSError as e:
                      # Fehler nur loggen, nicht abbrechen, da Logger-Setup dies ggf. behandelt
                      log.warning("Konnte Verzeichnis '%s' für Logdatei nicht erstellen/prüfen: %s", log_file_dir, e)

            if not isinstance(self.logging_config.file.level, str) or self.logging_config.file.level.upper() not in valid_log_levels:
                 raise ValueError(f"Ungültiger Wert für logging.file.level '{self.logging_config.file.level}'. Gültige Werte: {list(valid_log_levels)}")
            # rolling_interval ist nur ein String, Validierung erfolgt in logger.py
            if not isinstance(self.logging_config.file.retained_file_count_limit, int) or self.logging_config.file.retained_file_count_limit < 0:
                 raise ValueError(f"Ungültiger Wert für logging.file.retained_file_count_limit '{self.logging_config.file.retained_file_count_limit}' (muss >= 0 sein).")
            if not isinstance(self.logging_config.file.output_template, str): # Keine Prüfung auf leeren String, da evtl. gültig
                 raise ValueError("Ungültiger oder fehlender Wert für logging.file.output_template.")

            # --- NEU: Forwarding-Validierung ---
            if not hasattr(self.forwarding, 'enabled') or not isinstance(self.forwarding.enabled, bool):
                raise ValueError("Ungültiger oder fehlender Wert für forwarding.enabled (muss true oder false sein).")
            if not hasattr(self.forwarding, 'provider') or not isinstance(self.forwarding.provider, str) or not self.forwarding.provider:
                raise ValueError("Ungültiger oder fehlender Wert für forwarding.provider (muss ein String sein).")
            if self.forwarding.provider.lower() != "telegram":
                 log.warning("Forwarding Provider '%s' ist nicht 'telegram'. Aktuell wird nur Telegram unterstützt.", self.forwarding.provider)

            if not hasattr(self.forwarding, 'rules') or not isinstance(self.forwarding.rules, list):
                 raise ValueError("Ungültiger oder fehlender Wert für forwarding.rules (muss eine Liste sein).")
            # Optionale tiefere Prüfung der Regeln
            for i, rule in enumerate(self.forwarding.rules):
                 if not isinstance(rule, dict):
                     raise ValueError(f"Ungültige Regel in forwarding.rules an Index {i}: Muss ein Dictionary sein.")
                 # Hier könnten weitere Prüfungen für Keys wie 'type', 'dst' etc. folgen
                 for key, value in rule.items():
                     if key not in ['type', 'dst', 'src']: # Erlaubte Schlüssel für Regeln (Beispiel)
                         log.warning("Unbekannter Schlüssel '%s' in forwarding.rules[%d]. Wird ignoriert.", key, i)
                     if not isinstance(value, str):
                         raise ValueError(f"Ungültiger Wert für Schlüssel '{key}' in forwarding.rules an Index {i}: Muss ein String sein.")


            if not hasattr(self.forwarding, 'telegram'):
                 raise ValueError("Fehlende Sektion 'telegram' in der forwarding-Konfiguration.")
            if not hasattr(self.forwarding.telegram, 'bot_token') or not isinstance(self.forwarding.telegram.bot_token, str):
                 raise ValueError("Ungültiger oder fehlender Wert für forwarding.telegram.bot_token.")
            if not hasattr(self.forwarding.telegram, 'chat_id') or not isinstance(self.forwarding.telegram.chat_id, str):
                 raise ValueError("Ungültiger oder fehlender Wert für forwarding.telegram.chat_id.")

            # Warnung, wenn Forwarding aktiviert ist, aber die Default-Werte noch drinstehen
            if self.forwarding.enabled:
                 log.info("Forwarding ist aktiviert (Provider: %s).", self.forwarding.provider)
                 if "YOUR_BOT_TOKEN_HERE" in self.forwarding.telegram.bot_token:
                     log.warning("Forwarding ist aktiviert, aber forwarding.telegram.bot_token scheint ein Platzhalter zu sein!")
                 if "YOUR_TARGET_CHAT_ID_HERE" in self.forwarding.telegram.chat_id:
                     log.warning("Forwarding ist aktiviert, aber forwarding.telegram.chat_id scheint ein Platzhalter zu sein!")
            else:
                 log.info("Forwarding ist deaktiviert.")


            log.info("Konfiguration erfolgreich validiert.")

        except ValueError as e:
             log.error("Validierungsfehler in der Konfiguration: %s", e)
             raise # Fehler weitergeben, damit das Hauptprogramm abbrechen kann
        except AttributeError as e:
             # Dieser Fehler sollte durch die .get() Defaults in _populate_attributes unwahrscheinlicher sein,
             # aber zur Sicherheit drinlassen, falls doch mal eine ganze Sektion fehlt und die Defaults nicht greifen.
             log.error("Fehlendes Attribut während der Validierung (wahrscheinlich fehlende Sektion/Key in config.json und Defaults): %s", e, exc_info=True)
             raise ValueError(f"Fehlende Konfigurationseinstellung: {e}")


# Kleines Beispiel, wie man die Klasse verwenden könnte
if __name__ == "__main__":
    # WICHTIG: Damit die Logs aus diesem Testlauf sichtbar sind,
    # muss das Logging *minimal* konfiguriert werden, BEVOR ConfigLoader genutzt wird.
    # Im echten Programm passiert das zentral in logger.py NACH dem Laden der Config.
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')

    log.info("Teste ConfigLoader...")
    try:
        # Versuche, die Konfiguration zu laden/erstellen
        # Zum Testen kann man auch explizit eine nicht existierende Datei angeben:
        # test_config_file = "nonexistent_config.json"
        # if os.path.exists(test_config_file): os.remove(test_config_file)
        # config = ConfigLoader(filename=test_config_file)

        config = ConfigLoader() # Lädt/erstellt config.json

        # Zugriff auf die Konfigurationswerte
        log.info("--- Geladene/Erstellte Konfiguration ---")
        log.info("DB Datei: %s", config.database.db_file)
        log.info("DB Tabelle: %s", config.database.table_name)
        log.info("Listener Host: %s", config.listener.host)
        log.info("Listener Port: %d", config.listener.port)
        log.info("Listener Puffergröße: %d", config.listener.buffer_size)
        log.info("Listener zu speichernde Typen: %s", config.listener.store_types) # NEU
        log.info("Log Konsole Level: %s", config.logging_config.console.level)
        log.info("Log Datei Pfad: %s", config.logging_config.file.path)
        log.info("Log Datei Level: %s", config.logging_config.file.level)
        log.info("Log Datei Rolling Interval: %s", config.logging_config.file.rolling_interval)
        log.info("Log Datei Anzahl behalten: %d", config.logging_config.file.retained_file_count_limit)
        log.info("Log Datei Template: %s", config.logging_config.file.output_template)
        log.info("Forwarding Aktiviert: %s", config.forwarding.enabled) # NEU
        log.info("Forwarding Provider: %s", config.forwarding.provider) # NEU
        log.info("Forwarding Regeln: %s", config.forwarding.rules) # NEU
        log.info("Forwarding Telegram Token: %s... (versteckt)", config.forwarding.telegram.bot_token[:5]) # NEU (nur Anfang loggen)
        log.info("Forwarding Telegram Chat ID: %s", config.forwarding.telegram.chat_id) # NEU
        log.info("--- Ende Konfiguration ---")


        # Zeige, dass die config.json existiert (oder erstellt wurde)
        if os.path.exists(CONFIG_FILENAME):
             log.info("Datei '%s' existiert.", CONFIG_FILENAME)
        else:
             log.warning("Datei '%s' konnte nicht erstellt werden.", CONFIG_FILENAME)

    except ValueError as e:
        log.error("Validierungsfehler in der Konfiguration: %s", e)
    except Exception as e:
        log.error("Ein Fehler ist aufgetreten:", exc_info=True)