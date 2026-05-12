package config

import "testing"

func TestLoadDefaults(t *testing.T) {
	t.Setenv("DB_BACKEND", "")
	t.Setenv("DB_SQLITE_PATH", "")
	t.Setenv("LISTENER_PORT", "")

	cfg := Load()
	if cfg.DBBackend != "sqlite" {
		t.Fatalf("expected sqlite backend, got %q", cfg.DBBackend)
	}
	if cfg.DBSQLitePath != "/data/meshcom.db" {
		t.Fatalf("expected default sqlite path, got %q", cfg.DBSQLitePath)
	}
	if cfg.ListenerPort != 1799 {
		t.Fatalf("expected listener port 1799, got %d", cfg.ListenerPort)
	}
}

func TestLoadLists(t *testing.T) {
	t.Setenv("STORE_TYPES", "msg, pos,,tele ")
	cfg := Load()

	want := []string{"msg", "pos", "tele"}
	if len(cfg.StoreTypes) != len(want) {
		t.Fatalf("expected %d store types, got %d", len(want), len(cfg.StoreTypes))
	}
	for i := range want {
		if cfg.StoreTypes[i] != want[i] {
			t.Fatalf("expected store type %q at index %d, got %q", want[i], i, cfg.StoreTypes[i])
		}
	}
}
