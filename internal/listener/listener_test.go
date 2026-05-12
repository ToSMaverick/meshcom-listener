package listener

import (
	"context"
	"log/slog"
	"testing"

	"github.com/ToSMaverick/meshcom-listener/internal/config"
	"github.com/ToSMaverick/meshcom-listener/internal/store"
)

type fakeStore struct {
	saved []store.Message
}

func (f *fakeStore) Connect(context.Context) error               { return nil }
func (f *fakeStore) Init(context.Context) error                  { return nil }
func (f *fakeStore) PruneOldMessages(context.Context, int) error { return nil }
func (f *fakeStore) Ping(context.Context) error                  { return nil }
func (f *fakeStore) Reset(context.Context) error                 { return nil }
func (f *fakeStore) Close() error                                { return nil }
func (f *fakeStore) SaveMessage(_ context.Context, msg store.Message) error {
	f.saved = append(f.saved, msg)
	return nil
}

type fakeForwarder struct {
	sent []store.Message
}

func (f *fakeForwarder) Send(_ context.Context, msg store.Message) (bool, error) {
	f.sent = append(f.sent, msg)
	return true, nil
}

func TestSplitSource(t *testing.T) {
	sender, via := SplitSource("OE3MIF, NODE1, NODE2")
	if sender != "OE3MIF" {
		t.Fatalf("expected sender OE3MIF, got %q", sender)
	}
	if len(via) != 2 || via[0] != "NODE1" || via[1] != "NODE2" {
		t.Fatalf("unexpected via path: %#v", via)
	}
}

func TestShouldForwardMessageFilters(t *testing.T) {
	cfg := config.Config{
		ForwardTypes:      []string{"msg"},
		ForwardIncludeDst: []string{"ADMIN"},
		ForwardExcludeDst: []string{"*"},
	}

	if !ShouldForward(cfg, store.Message{Src: "SRC", MsgType: "msg", Raw: map[string]any{"dst": "ADMIN"}}) {
		t.Fatal("expected ADMIN message to be forwarded")
	}
	if ShouldForward(cfg, store.Message{Src: "SRC", MsgType: "msg", Raw: map[string]any{"dst": "*"}}) {
		t.Fatal("expected broadcast message to be suppressed")
	}
}

func TestProcessPayloadStoresAndForwards(t *testing.T) {
	cfg := config.Config{
		StoreTypes:        []string{"msg"},
		NotifyEnabled:     true,
		ForwardTypes:      []string{"msg"},
		ForwardExcludeDst: []string{},
	}
	store := &fakeStore{}
	forwarder := &fakeForwarder{}
	server := New(cfg, store, forwarder, slog.Default())

	err := server.ProcessPayload(context.Background(), map[string]any{
		"type": "msg",
		"src":  "OE3MIF,NODE1",
		"dst":  "ADMIN",
		"msg":  "hello",
	}, "127.0.0.1:1234")
	if err != nil {
		t.Fatalf("process payload failed: %v", err)
	}
	if len(store.saved) != 1 {
		t.Fatalf("expected one stored message, got %d", len(store.saved))
	}
	if len(forwarder.sent) != 1 {
		t.Fatalf("expected one forwarded message, got %d", len(forwarder.sent))
	}
	if store.saved[0].Src != "OE3MIF" || len(store.saved[0].Via) != 1 || store.saved[0].Via[0] != "NODE1" {
		t.Fatalf("unexpected parsed source: %#v", store.saved[0])
	}
}
