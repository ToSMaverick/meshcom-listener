package sqlite

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	"github.com/ToSMaverick/meshcom-listener/internal/store"
)

func TestStoreMessageAndNode(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "meshcom.db")
	s := New(path)

	if err := s.Connect(ctx); err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	defer s.Close()
	if err := s.Init(ctx); err != nil {
		t.Fatalf("init failed: %v", err)
	}

	err := s.SaveMessage(ctx, store.Message{
		Src:     "OE3MIF",
		Via:     []string{"NODE1"},
		SrcType: "node",
		MsgType: "pos",
		Raw: map[string]any{
			"type": "pos",
			"lat":  48.2,
			"long": 16.3,
			"alt":  1200,
		},
	})
	if err != nil {
		t.Fatalf("save message failed: %v", err)
	}

	var messageCount int
	if err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM message`).Scan(&messageCount); err != nil {
		t.Fatalf("count messages failed: %v", err)
	}
	if messageCount != 1 {
		t.Fatalf("expected one message, got %d", messageCount)
	}

	var lat, long sql.NullFloat64
	if err := s.db.QueryRowContext(ctx, `SELECT last_lat, last_long FROM node WHERE src = ?`, "OE3MIF").Scan(&lat, &long); err != nil {
		t.Fatalf("query node failed: %v", err)
	}
	if !lat.Valid || lat.Float64 != 48.2 || !long.Valid || long.Float64 != 16.3 {
		t.Fatalf("unexpected node position: lat=%#v long=%#v", lat, long)
	}
}

func TestReset(t *testing.T) {
	ctx := context.Background()
	s := New(filepath.Join(t.TempDir(), "meshcom.db"))
	if err := s.Connect(ctx); err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	defer s.Close()
	if err := s.Init(ctx); err != nil {
		t.Fatalf("init failed: %v", err)
	}
	if err := s.Reset(ctx); err != nil {
		t.Fatalf("reset failed: %v", err)
	}
	if err := s.Ping(ctx); err != nil {
		t.Fatalf("ping after reset failed: %v", err)
	}
}

func TestPruneOldMessages(t *testing.T) {
	ctx := context.Background()
	s := New(filepath.Join(t.TempDir(), "meshcom.db"))
	if err := s.Connect(ctx); err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	defer s.Close()
	if err := s.Init(ctx); err != nil {
		t.Fatalf("init failed: %v", err)
	}

	_, err := s.db.ExecContext(ctx, `INSERT INTO message (time, src, msg_type, raw) VALUES (?, ?, ?, ?)`, "2000-01-01T00:00:00Z", "OLD", "msg", "{}")
	if err != nil {
		t.Fatalf("insert old message failed: %v", err)
	}
	if err := s.SaveMessage(ctx, store.Message{Src: "NEW", MsgType: "msg", Raw: map[string]any{"type": "msg"}}); err != nil {
		t.Fatalf("save new message failed: %v", err)
	}
	if err := s.PruneOldMessages(ctx, 7); err != nil {
		t.Fatalf("prune failed: %v", err)
	}

	var count int
	if err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM message`).Scan(&count); err != nil {
		t.Fatalf("count messages failed: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected one remaining message, got %d", count)
	}
}
