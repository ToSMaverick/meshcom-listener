# database.py

import sqlite3
import os
import logging
from types import SimpleNamespace # Für Type Hinting
from datetime import datetime     # Für Type Hinting

# Logger für dieses Modul
log = logging.getLogger(__name__)

class DatabaseHandler:
    """
    Verwaltet die SQLite-Datenbankverbindung und Operationen.

    Stellt sicher, dass die Datenbankdatei und die benötigten Tabellen
    existieren und bietet Methoden zum Speichern von Nachrichten.
    Kann als Context Manager verwendet werden (`with DatabaseHandler(...)`).
    """

    def __init__(self, db_config: SimpleNamespace):
        """
        Initialisiert den DatabaseHandler.

        :param db_config: Das Konfigurationsobjekt für die Datenbank
                          (typischerweise config.database), erwartet Attribute
                          'db_file' und 'table_name'.
        """
        if not hasattr(db_config, 'db_file') or not hasattr(db_config, 'table_name'):
            raise ValueError("db_config fehlen die erwarteten Attribute 'db_file' oder 'table_name'.")

        self.db_file = db_config.db_file
        self.table_name = db_config.table_name
        self.connection = None
        log.debug("DatabaseHandler initialisiert für Datei '%s' und Tabelle '%s'.", self.db_file, self.table_name)
        # Die Verbindung wird erst bei Bedarf oder durch expliziten Aufruf von connect() aufgebaut.
        # Alternativ: Direkt hier self.connect() aufrufen, wenn die Verbindung sofort stehen soll.

    def connect(self):
        """
        Stellt die Verbindung zur SQLite-Datenbank her und stellt sicher,
        dass die notwendigen Tabellen existieren.
        """
        if self.connection:
            log.debug("Verbindung existiert bereits.")
            return # Bereits verbunden

        log.info("Stelle Verbindung zur Datenbank '%s' her...", self.db_file)
        try:
            # Sicherstellen, dass das Verzeichnis existiert
            db_dir = os.path.dirname(self.db_file)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                log.info("Verzeichnis '%s' für Datenbankdatei erstellt.", db_dir)

            # Verbindung aufbauen
            # detect_types ermöglicht das automatische Umwandeln von Timestamp-Spalten
            self.connection = sqlite3.connect(
                self.db_file,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            # Stellt sicher, dass Fremdschlüssel-Constraints aktiv sind (falls verwendet)
            self.connection.execute("PRAGMA foreign_keys = ON;")

            log.info("Verbindung zur Datenbank '%s' erfolgreich hergestellt.", self.db_file)

            # Tabellen erstellen, falls nötig
            self._create_tables()

        except sqlite3.Error as e:
            log.error("SQLite-Fehler beim Verbinden oder Tabellenerstellen für '%s': %s", self.db_file, e, exc_info=True)
            self.connection = None # Verbindung zurücksetzen im Fehlerfall
            raise # Fehler weitergeben
        except OSError as e:
            log.error("OS-Fehler (z.B. Verzeichnis erstellen) für '%s': %s", self.db_file, e, exc_info=True)
            self.connection = None
            raise
        except Exception as e:
            log.error("Unerwarteter Fehler beim Verbinden mit '%s': %s", self.db_file, e, exc_info=True)
            self.connection = None
            raise

    def _create_tables(self):
        """
        Erstellt die benötigten Datenbanktabellen, falls sie noch nicht existieren.
        """
        if not self.connection:
            log.error("Keine Datenbankverbindung vorhanden, um Tabellen zu erstellen.")
            raise sqlite3.Error("Verbindung nicht initialisiert.")

        log.debug("Stelle sicher, dass Tabelle '%s' existiert...", self.table_name)
        try:
            cursor = self.connection.cursor()
            # SQL zum Erstellen der Tabelle (verwende self.table_name)
            # Die Spalten entsprechen dem vorherigen Listener-Beispiel
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TIMESTAMP NOT NULL,
                message_type TEXT,
                source TEXT,
                raw_message TEXT NOT NULL
            )
            """)

            # Indizes für häufige Abfragen erstellen (falls sie nicht existieren)
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type ON {self.table_name} (message_type)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_source ON {self.table_name} (source)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_received_at ON {self.table_name} (received_at)")


            self.connection.commit()
            log.info("Tabelle '%s' und Indizes sind bereit.", self.table_name)
        except sqlite3.Error as e:
            log.error("SQLite-Fehler beim Erstellen der Tabelle '%s': %s", self.table_name, e, exc_info=True)
            raise # Fehler weitergeben

    def save_message(self, received_time: datetime, msg_type: str | None, source: str | None, raw_message_str: str):
        """
        Speichert eine einzelne Nachricht in der Datenbank.

        :param received_time: Der Zeitpunkt des Empfangs (datetime Objekt).
        :param msg_type: Der extrahierte Typ der Nachricht (z.B. 'pos', 'msg') oder None.
        :param source: Die extrahierte Quelle der Nachricht oder None.
        :param raw_message_str: Die komplette Nachricht als JSON-String.
        """
        if not self.connection:
            log.error("Speichern nicht möglich: Keine Datenbankverbindung.")
            # Optional: Versuchen, die Verbindung hier herzustellen?
            # self.connect() # Könnte Seiteneffekte haben, wenn es fehlschlägt
            raise sqlite3.Error("Verbindung nicht initialisiert.")

        log.debug("Speichere Nachricht: type=%s, source=%s", msg_type, source)
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"""
            INSERT INTO {self.table_name} (received_at, message_type, source, raw_message)
            VALUES (?, ?, ?, ?)
            """, (received_time, msg_type, source, raw_message_str))
            self.connection.commit()
            log.debug("Nachricht erfolgreich gespeichert (ID: %s).", cursor.lastrowid)
            return cursor.lastrowid # Gibt die ID des eingefügten Datensatzes zurück
        except sqlite3.Error as e:
            log.error("SQLite-Fehler beim Speichern der Nachricht: %s", e, exc_info=True)
            # Optional: Rollback bei komplexeren Transaktionen nötig
            # self.connection.rollback()
            raise # Fehler weitergeben

    def close(self):
        """Schließt die Datenbankverbindung, falls sie offen ist."""
        if self.connection:
            log.info("Schließe Datenbankverbindung zu '%s'.", self.db_file)
            try:
                self.connection.close()
                self.connection = None
            except sqlite3.Error as e:
                log.error("SQLite-Fehler beim Schließen der Verbindung: %s", e, exc_info=True)
        else:
            log.debug("Keine aktive Datenbankverbindung zum Schließen.")

    # --- Context Manager Support ---
    def __enter__(self):
        """Ermöglicht die Verwendung mit 'with', stellt Verbindung sicher."""
        if not self.connection:
            self.connect() # Verbindung aufbauen, wenn sie noch nicht besteht
        return self # Gibt das Handler-Objekt zurück

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Wird beim Verlassen des 'with'-Blocks aufgerufen, schließt die Verbindung."""
        self.close()

# Beispiel für die Verwendung (im Hauptskript)
if __name__ == "__main__":
    # Dieser Teil dient nur zur Demonstration und zum Testen von database.py direkt.
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')

    log.info("--- Teste database.py ---")

    # 1. Beispiel-Konfiguration erstellen
    class MockDbConfig(SimpleNamespace):
        db_file = "test_messages.db"
        table_name = "test_log"

    test_config = MockDbConfig()

    # Optional: Alte Test-DB löschen
    if os.path.exists(test_config.db_file):
        log.debug("Lösche alte Test-Datenbank: %s", test_config.db_file)
        os.remove(test_config.db_file)

    # 2. DatabaseHandler als Context Manager verwenden
    try:
        log.info("Verwende DatabaseHandler mit 'with'-Statement:")
        with DatabaseHandler(test_config) as db_handler:
            log.info("Datenbankverbindung innerhalb von 'with' hergestellt.")

            # 3. Beispielnachrichten speichern
            now = datetime.now()
            msg_id1 = db_handler.save_message(now, 'msg', 'OE1ABC-1', '{"type":"msg", "src":"OE1ABC-1", "msg":"Test 1"}')
            msg_id2 = db_handler.save_message(now, 'pos', 'OE3XYZ-2', '{"type":"pos", "src":"OE3XYZ-2", "lat":48.1, "lon":16.3}')
            msg_id3 = db_handler.save_message(now, 'msg', 'DL1ZZZ-3', '{"type":"msg", "src":"DL1ZZZ-3", "msg":"Test 3"}')
            msg_id4 = db_handler.save_message(datetime.now(), None, None, 'INVALID JSON DATA') # Beispiel mit fehlenden Werten

            log.info(f"Nachrichten gespeichert mit IDs: {msg_id1}, {msg_id2}, {msg_id3}, {msg_id4}")

            # 4. Daten zur Überprüfung auslesen (optional)
            log.info("Lese gespeicherte Daten aus:")
            cursor = db_handler.connection.cursor()
            cursor.execute(f"SELECT id, received_at, message_type, source FROM {db_handler.table_name}")
            rows = cursor.fetchall()
            for row in rows:
                log.info(f"  Gelesen: ID={row[0]}, Time={row[1]}, Type={row[2]}, Source={row[3]}")

        log.info("Nach Verlassen des 'with'-Blocks wurde die Verbindung automatisch geschlossen.")

        # Prüfen, ob die Datei existiert
        if os.path.exists(test_config.db_file):
            log.info("Test-Datenbankdatei '%s' wurde erfolgreich erstellt.", test_config.db_file)
        else:
            log.error("Test-Datenbankdatei '%s' wurde NICHT erstellt!", test_config.db_file)


        # 5. Test ohne Context Manager (manuelles connect/close)
        log.info("\nTeste DatabaseHandler ohne 'with' (manuelles connect/close):")
        handler_manual = DatabaseHandler(test_config)
        try:
            handler_manual.connect()
            log.info("Manuelle Verbindung hergestellt.")
            manual_id = handler_manual.save_message(datetime.now(), 'status', 'SYSTEM', '{"type":"status", "info":"Manual test"}')
            log.info("Weitere Nachricht gespeichert mit ID: %s", manual_id)
        finally:
            handler_manual.close() # Wichtig: Manuell schließen!
            log.info("Manuelle Verbindung geschlossen.")


    except Exception as e:
        log.error("FEHLER während des Datenbank-Tests:", exc_info=True)