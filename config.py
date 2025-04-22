# config.py

import json
import os
import logging
from types import SimpleNamespace
# Importiere Dict für Type Hinting
from typing import Dict, Any

log = logging.getLogger(__name__)

CONFIG_FILENAME = "config.json"

# Standardkonfiguration, mit neuem "templates"-Abschnitt
DEFAULT_CONFIG = {
    "database": {
        "db_file": "db/meshcom_messages.db",
        "table_name": "messages"
    },
    "listener": {
        "host": "0.0.0.0",
        "port": 1799,
        "buffer_size": 2048,
        "store_types": [ # Nur diese Typen speichern
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
    "forwarding": {
        "enabled": False,
        "provider": "telegram", # Aktuell nur Telegram unterstützt
        "rules": [ # Leere Liste als Default
            # Beispielregeln (werden aus config.json geladen, falls vorhanden):
            # {"type": "msg", "dst": "232"},  # Leite Nachrichten an die AT-Gruppe weiter
            # {"type": "pos"}              # Leite alle Positionsmeldungen weiter
        ],
        "telegram": {
            "bot_token": "SET_VIA_ENV_OR_CONFIG",
            "chat_id": "SET_VIA_ENV_OR_CONFIG",
            # NEU: Templates für Telegram Nachrichten (MarkdownV2)
            "templates": {
                "default": "📡 *Neue Nachricht*\n*Typ:* `{type}`\n*Von:* `{src}`\n*An:* `{dst}`\n*ID:* `{msg_id}`\n*Rohdaten:* `{_raw_json_short}`",
                "msg": "📡 *Neue Nachricht*\n*Typ:* `msg`\n*Von:* `{src}`\n*An:* `{dst}`\n*ID:* `{msg_id}`\n*Nachricht:*\n```\n{msg}\n```",
                "pos": "📡 *Position*\n*Von:* `{src}`\n*Position:* `{lat}, {long}`\n*Höhe:* `{_alt_m}m`\n[📍 Auf Karte anzeigen]({_map_link})"
                # Platzhalter: {key}, {_computed_key}
                # MarkdownV2 wird im Template erwartet, dynamische Werte werden escaped
            }
        }
    }
}

class ConfigLoader:
    """
    Lädt die Konfiguration aus einer JSON-Datei oder erstellt eine Standarddatei.
    Überschreibt Telegram Token/ChatID mit Umgebungsvariablen, falls gesetzt.
    Stellt die Konfiguration über Attribute bereit.
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
        # Die Validierung erfolgt nach dem potenziellen Überschreiben durch Umgebungsvariablen
        self._validate_config()

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
            # Prüfe, ob der Schlüssel im Default existiert und beide Werte Dictionaries sind
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                 merged[key] = self._merge_configs(merged[key], value) # Rekursiv für verschachtelte Dicts
            else:
                 # Überschreiben oder hinzufügen, wenn kein deep merge möglich/nötig
                 merged[key] = value
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


    def _populate_attributes(self, config_data: Dict[str, Any]):
        """
        Wandelt das Konfigurations-Dict in SimpleNamespace-Attribute um
        und überschreibt Telegram-Secrets mit Umgebungsvariablen, falls vorhanden.
        """
        # 1. Populate aus config_data (wie bisher)
        db_settings = config_data.get("database", DEFAULT_CONFIG["database"])
        listener_settings = config_data.get("listener", DEFAULT_CONFIG["listener"])
        logging_settings = config_data.get("logging", DEFAULT_CONFIG["logging"])
        forwarding_settings = config_data.get("forwarding", DEFAULT_CONFIG["forwarding"])

        self.database = SimpleNamespace(**db_settings)
        self.listener = SimpleNamespace(**listener_settings)

        log_console_settings = logging_settings.get("console", DEFAULT_CONFIG["logging"]["console"])
        log_file_settings = logging_settings.get("file", DEFAULT_CONFIG["logging"]["file"])
        self.logging_config = SimpleNamespace(
             console=SimpleNamespace(**log_console_settings),
             file=SimpleNamespace(**log_file_settings)
        )

        # Behandle 'telegram' Sektion sorgfältiger, da sie jetzt 'templates' enthält
        default_telegram_settings = DEFAULT_CONFIG["forwarding"]["telegram"]
        loaded_telegram_settings = forwarding_settings.get("telegram", default_telegram_settings)

        # Stelle sicher, dass 'templates' ein Dict ist, falls es in der Config fehlt oder null ist
        telegram_templates = loaded_telegram_settings.get("templates", default_telegram_settings["templates"])
        if not isinstance(telegram_templates, dict):
            log.warning("Ungültiger 'templates'-Eintrag in forwarding.telegram, verwende Standard-Templates.")
            telegram_templates = default_telegram_settings["templates"]

        # Erstelle den telegram Namespace
        self.forwarding_telegram = SimpleNamespace(
            bot_token=loaded_telegram_settings.get("bot_token", default_telegram_settings["bot_token"]),
            chat_id=loaded_telegram_settings.get("chat_id", default_telegram_settings["chat_id"]),
            templates=telegram_templates # Verwende das validierte/default Template-Dict
        )

        # Erstelle den forwarding Namespace
        self.forwarding = SimpleNamespace(
            enabled=forwarding_settings.get("enabled", DEFAULT_CONFIG["forwarding"]["enabled"]),
            provider=forwarding_settings.get("provider", DEFAULT_CONFIG["forwarding"]["provider"]),
            rules=forwarding_settings.get("rules", DEFAULT_CONFIG["forwarding"]["rules"]),
            telegram=self.forwarding_telegram # Füge den erstellten Telegram-Namespace hinzu
        )

        # 2. Überschreibe Telegram-Secrets mit Umgebungsvariablen (falls gesetzt)
        #    Wir greifen jetzt auf das verschachtelte Objekt zu
        env_token = os.getenv('TELEGRAM_BOT_TOKEN')
        env_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if env_token:
            log.info("Überschreibe telegram.bot_token aus Umgebungsvariable TELEGRAM_BOT_TOKEN.")
            self.forwarding.telegram.bot_token = env_token

        if env_chat_id:
            log.info("Überschreibe telegram.chat_id aus Umgebungsvariable TELEGRAM_CHAT_ID.")
            self.forwarding.telegram.chat_id = env_chat_id

        log.debug("Konfigurationsattribute erfolgreich erstellt und ggf. mit Umgebungsvariablen überschrieben.")

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
            log_file_dir = os.path.dirname(self.logging_config.file.path)
            if log_file_dir:
                  try:
                       os.makedirs(log_file_dir, exist_ok=True)
                       log.debug("Verzeichnis '%s' für Logdatei sichergestellt.", log_file_dir)
                  except OSError as e:
                       log.warning("Konnte Verzeichnis '%s' für Logdatei nicht erstellen/prüfen: %s", log_file_dir, e)
            if not isinstance(self.logging_config.file.level, str) or self.logging_config.file.level.upper() not in valid_log_levels:
                  raise ValueError(f"Ungültiger Wert für logging.file.level '{self.logging_config.file.level}'. Gültige Werte: {list(valid_log_levels)}")
            if not isinstance(self.logging_config.file.retained_file_count_limit, int) or self.logging_config.file.retained_file_count_limit < 0:
                  raise ValueError(f"Ungültiger Wert für logging.file.retained_file_count_limit '{self.logging_config.file.retained_file_count_limit}' (muss >= 0 sein).")
            if not isinstance(self.logging_config.file.output_template, str):
                  raise ValueError("Ungültiger oder fehlender Wert für logging.file.output_template.")


            # --- Forwarding-Validierung (angepasst für Templates) ---
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
                 for key, value in rule.items():
                     if key not in ['type', 'dst', 'src']:
                         log.warning("Unbekannter Schlüssel '%s' in forwarding.rules[%d]. Wird ignoriert.", key, i)
                     if not isinstance(value, str):
                         raise ValueError(f"Ungültiger Wert für Schlüssel '{key}' in forwarding.rules an Index {i}: Muss ein String sein.")

            if not hasattr(self.forwarding, 'telegram'):
                 raise ValueError("Fehlende Sektion 'telegram' in der forwarding-Konfiguration.")
            if not hasattr(self.forwarding.telegram, 'bot_token') or not isinstance(self.forwarding.telegram.bot_token, str):
                 raise ValueError("Ungültiger oder fehlender Wert für forwarding.telegram.bot_token.")
            if not hasattr(self.forwarding.telegram, 'chat_id') or not isinstance(self.forwarding.telegram.chat_id, str):
                 raise ValueError("Ungültiger oder fehlender Wert für forwarding.telegram.chat_id.")

            # NEU: Template-Validierung
            if not hasattr(self.forwarding.telegram, 'templates') or not isinstance(self.forwarding.telegram.templates, dict):
                 raise ValueError("Ungültiger oder fehlender Wert für forwarding.telegram.templates (muss ein Dictionary sein).")
            if 'default' not in self.forwarding.telegram.templates or not isinstance(self.forwarding.telegram.templates['default'], str):
                 raise ValueError("Ein 'default' Template (String) muss in forwarding.telegram.templates vorhanden sein.")
            # Optional: Weitere Prüfungen, ob Templates für msg, pos etc. Strings sind
            for tpl_key, tpl_value in self.forwarding.telegram.templates.items():
                if not isinstance(tpl_value, str):
                    raise ValueError(f"Template für '{tpl_key}' in forwarding.telegram.templates muss ein String sein.")
                # Optional: Prüfen, ob die Templates gültige Format-Strings sind? (komplex)


            # Strengere Prüfung für Secrets bleibt gleich
            placeholder_token = "SET_VIA_ENV_OR_CONFIG"
            placeholder_chat_id = "SET_VIA_ENV_OR_CONFIG"
            if self.forwarding.enabled:
                log.info("Forwarding ist aktiviert (Provider: %s).", self.forwarding.provider)
                if not self.forwarding.telegram.bot_token or self.forwarding.telegram.bot_token == placeholder_token:
                    raise ValueError("Forwarding ist aktiviert, aber telegram.bot_token fehlt oder ist Platzhalter. Setze TELEGRAM_BOT_TOKEN Umgebungsvariable oder den Wert in config.json.")
                if not self.forwarding.telegram.chat_id or self.forwarding.telegram.chat_id == placeholder_chat_id:
                    raise ValueError("Forwarding ist aktiviert, aber telegram.chat_id fehlt oder ist Platzhalter. Setze TELEGRAM_CHAT_ID Umgebungsvariable oder den Wert in config.json.")
            else:
                 log.info("Forwarding ist deaktiviert.")

            log.info("Konfiguration erfolgreich validiert.")

        except ValueError as e:
             log.error("Validierungsfehler in der Konfiguration: %s", e)
             raise # Fehler weitergeben, damit das Hauptprogramm abbrechen kann
        except AttributeError as e:
             log.error("Fehlendes Attribut während der Validierung: %s", e, exc_info=True)
             raise ValueError(f"Fehlende Konfigurationseinstellung: {e}")

# Kleines Beispiel, wie man die Klasse verwenden könnte
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
    log.info("Teste ConfigLoader...")
    try:
        config = ConfigLoader() # Lädt/erstellt config.json und wendet Env-Vars an

        # Zugriff auf die Konfigurationswerte
        log.info("--- Geladene/Erstellte Konfiguration (inkl. Env-Override) ---")
        # ... (Ausgaben für DB, Listener, Logging wie vorher) ...
        log.info("DB Datei: %s", config.database.db_file)
        # ... (andere Ausgaben) ...
        log.info("Listener zu speichernde Typen: %s", config.listener.store_types)
        # ... (Logging Ausgaben) ...
        log.info("Forwarding Aktiviert: %s", config.forwarding.enabled)
        log.info("Forwarding Provider: %s", config.forwarding.provider)
        log.info("Forwarding Regeln: %s", config.forwarding.rules)
        log.info("Forwarding Telegram Token: %s...", config.forwarding.telegram.bot_token[:5] if config.forwarding.telegram.bot_token else "None")
        log.info("Forwarding Telegram Chat ID: %s", config.forwarding.telegram.chat_id)
        log.info("Forwarding Telegram Templates:")
        for key, tpl in config.forwarding.telegram.templates.items():
             log.info("  %s: %s", key, tpl[:80] + ('...' if len(tpl) > 80 else '')) # Gekürzte Ausgabe
        log.info("--- Ende Konfiguration ---")

        if os.path.exists(CONFIG_FILENAME):
             log.info("Datei '%s' existiert.", CONFIG_FILENAME)

    except ValueError as e:
        log.error("Validierungsfehler in der Konfiguration: %s", e)
    except Exception as e:
        log.error("Ein Fehler ist aufgetreten:", exc_info=True)