-- Schema für MeshCom Listener (v0.2.9)
-- Sicherer Modus: Keine REMOVE TABLE Befehle für den Produktivbetrieb.

-- Tabelle message definieren
DEFINE TABLE message SCHEMALESS;
DEFINE FIELD time ON message TYPE datetime VALUE $before OR time::now();
DEFINE FIELD src ON message TYPE string;
-- 'via' speichert den Pfad (die restlichen Knoten) als Liste von Strings
DEFINE FIELD via ON message TYPE array<string> DEFAULT [];
DEFINE FIELD msg_type ON message TYPE string;

DEFINE INDEX IF NOT EXISTS src_idx ON TABLE message FIELDS src;
DEFINE INDEX IF NOT EXISTS time_idx ON TABLE message FIELDS time;
-- Index für die Suche in der via-Liste (z.B. Wer hat geroutet?)
DEFINE INDEX IF NOT EXISTS via_idx ON TABLE message FIELDS via;

-- Tabelle node definieren (SCHEMALESS für flexiblen Status)
DEFINE TABLE node SCHEMALESS;
DEFINE FIELD last_seen ON node TYPE datetime VALUE $before OR time::now();

-- Event-Logik (Sicherstellung, dass nur der Absender genutzt wird)
DEFINE EVENT update_node ON TABLE message WHEN $event = "CREATE" THEN (
    UPSERT type::record("node", $after.src) SET 
        last_seen = time::now(),
        last_pos = IF $after.msg_type = "pos" THEN { 
            lat: $after.raw.lat, 
            long: $after.raw.long, 
            alt: $after.raw.alt 
        } ELSE last_pos END
);
