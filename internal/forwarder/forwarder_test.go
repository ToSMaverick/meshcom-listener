package forwarder

import (
	"strings"
	"testing"

	"github.com/ToSMaverick/meshcom-listener/internal/store"
)

func TestBuildPayloadForMessage(t *testing.T) {
	payload := BuildPayload([]string{"mailto://user@example.com"}, store.Message{
		Src:     "OE3MIF",
		Via:     []string{"NODE1"},
		MsgType: "msg",
		Raw: map[string]any{
			"dst": "ADMIN",
			"msg": "hello",
		},
	})

	if payload.Title != "Message from OE3MIF" {
		t.Fatalf("unexpected title: %q", payload.Title)
	}
	if !strings.Contains(payload.Body, "To: ADMIN") || !strings.Contains(payload.Body, "hello") {
		t.Fatalf("unexpected body: %q", payload.Body)
	}
}

func TestBuildPayloadForPosition(t *testing.T) {
	payload := BuildPayload([]string{"json://example"}, store.Message{
		Src:     "OE3MIF",
		MsgType: "pos",
		Raw: map[string]any{
			"lat":  48.2,
			"long": 16.3,
			"alt":  1200,
		},
	})

	if payload.Title != "Position from OE3MIF" {
		t.Fatalf("unexpected title: %q", payload.Title)
	}
	if !strings.Contains(payload.Body, "openstreetmap.org") {
		t.Fatalf("expected OSM link in body: %q", payload.Body)
	}
}
