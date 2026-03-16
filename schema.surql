-- Schema für MeshCom Listener

-- Tabelle für alle eingegangenen Nachrichten
DEFINE TABLE message SCHEMAFULL;
DEFINE FIELD type ON message TYPE string ASSERT $value IN ['msg', 'pos', 'ack', 'status'];
DEFINE FIELD src ON message TYPE string;
DEFINE FIELD dst ON message TYPE string;
DEFINE FIELD msg ON message TYPE string;
DEFINE FIELD lat ON message TYPE number;
DEFINE FIELD long ON message TYPE number;
DEFINE FIELD alt ON message TYPE number;
DEFINE FIELD time ON message TYPE datetime VALUE $before OR time::now();
DEFINE FIELD raw ON message TYPE object;

-- Tabelle für Funkknoten (Zustandsbehaftet)
DEFINE TABLE node SCHEMAFULL;
DEFINE FIELD last_seen ON node TYPE datetime VALUE time::now();
DEFINE FIELD last_pos ON node TYPE object;

-- Automatisches Update der Knoten-Tabelle bei neuen Nachrichten
DEFINE EVENT update_node ON TABLE message WHEN $event = "CREATE" THEN (
    UPSERT type::thing("node", $after.src) SET 
        last_seen = time::now(),
        last_pos = IF $after.type = "pos" THEN { lat: $after.lat, long: $after.long, alt: $after.alt } ELSE last_pos END
);
