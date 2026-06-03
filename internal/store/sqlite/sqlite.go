package sqlite

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/ToSMaverick/meshcom-listener/internal/store"

	_ "modernc.org/sqlite"
)

type Store struct {
	path string
	db   *sql.DB
}

func New(path string) *Store {
	return &Store{path: path}
}

func (s *Store) Connect(ctx context.Context) error {
	if s.db != nil {
		return nil
	}
	if dir := filepath.Dir(s.path); dir != "." && dir != "" {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return fmt.Errorf("create sqlite directory: %w", err)
		}
	}

	db, err := sql.Open("sqlite", s.path)
	if err != nil {
		return fmt.Errorf("open sqlite database: %w", err)
	}
	db.SetMaxOpenConns(1)

	if _, err := db.ExecContext(ctx, "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;"); err != nil {
		_ = db.Close()
		return fmt.Errorf("configure sqlite database: %w", err)
	}

	s.db = db
	return nil
}

func (s *Store) Init(ctx context.Context) error {
	if err := s.requireDB(); err != nil {
		return err
	}

	schema := `
CREATE TABLE IF NOT EXISTS message (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	src TEXT NOT NULL,
	via TEXT NOT NULL DEFAULT '[]',
	src_type TEXT,
	msg_type TEXT NOT NULL,
	raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS message_src_idx ON message (src);
CREATE INDEX IF NOT EXISTS message_time_idx ON message (time);
CREATE INDEX IF NOT EXISTS message_msg_type_idx ON message (msg_type);

CREATE TABLE IF NOT EXISTS node (
	src TEXT PRIMARY KEY,
	last_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	last_lat REAL,
	last_long REAL,
	last_alt REAL
);`

	if _, err := s.db.ExecContext(ctx, schema); err != nil {
		return fmt.Errorf("initialize sqlite schema: %w", err)
	}
	return nil
}

func (s *Store) SaveMessage(ctx context.Context, message store.Message) error {
	if err := s.requireDB(); err != nil {
		return err
	}

	viaJSON, err := json.Marshal(message.Via)
	if err != nil {
		return fmt.Errorf("marshal via path: %w", err)
	}
	rawJSON, err := json.Marshal(message.Raw)
	if err != nil {
		return fmt.Errorf("marshal raw payload: %w", err)
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("start sqlite transaction: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()

	if _, err = tx.ExecContext(
		ctx,
		`INSERT INTO message (src, via, src_type, msg_type, raw) VALUES (?, ?, ?, ?, ?)`,
		message.Src,
		string(viaJSON),
		nullableString(message.SrcType),
		message.MsgType,
		string(rawJSON),
	); err != nil {
		return fmt.Errorf("insert message: %w", err)
	}

	if message.MsgType == "pos" {
		lat, long, alt := numberPtr(message.Raw["lat"]), numberPtr(message.Raw["long"]), numberPtr(message.Raw["alt"])
		if _, err = tx.ExecContext(
			ctx,
			`INSERT INTO node (src, last_seen, last_lat, last_long, last_alt)
			 VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, ?)
			 ON CONFLICT(src) DO UPDATE SET
				last_seen = excluded.last_seen,
				last_lat = excluded.last_lat,
				last_long = excluded.last_long,
				last_alt = excluded.last_alt`,
			message.Src,
			lat,
			long,
			alt,
		); err != nil {
			return fmt.Errorf("upsert position node: %w", err)
		}
	} else if _, err = tx.ExecContext(
		ctx,
		`INSERT INTO node (src, last_seen)
		 VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
		 ON CONFLICT(src) DO UPDATE SET last_seen = excluded.last_seen`,
		message.Src,
	); err != nil {
		return fmt.Errorf("upsert node: %w", err)
	}

	if err = tx.Commit(); err != nil {
		return fmt.Errorf("commit sqlite transaction: %w", err)
	}
	return nil
}

func (s *Store) PruneOldMessages(ctx context.Context, days int) error {
	if err := s.requireDB(); err != nil {
		return err
	}
	if days <= 0 {
		return nil
	}
	cutoff := fmt.Sprintf("-%d days", days)
	if _, err := s.db.ExecContext(ctx, `DELETE FROM message WHERE datetime(time) < datetime('now', ?)`, cutoff); err != nil {
		return fmt.Errorf("prune old messages: %w", err)
	}
	return nil
}

func (s *Store) Ping(ctx context.Context) error {
	if err := s.requireDB(); err != nil {
		return err
	}
	return s.db.PingContext(ctx)
}

func (s *Store) Reset(ctx context.Context) error {
	if err := s.requireDB(); err != nil {
		return err
	}
	if _, err := s.db.ExecContext(ctx, `DROP TABLE IF EXISTS message; DROP TABLE IF EXISTS node;`); err != nil {
		return fmt.Errorf("reset sqlite schema: %w", err)
	}
	return s.Init(ctx)
}

func (s *Store) Close() error {
	if s.db == nil {
		return nil
	}
	err := s.db.Close()
	s.db = nil
	return err
}

func (s *Store) requireDB() error {
	if s.db == nil {
		return fmt.Errorf("sqlite database is not connected")
	}
	return nil
}

func nullableString(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func numberPtr(value any) any {
	switch typed := value.(type) {
	case float64:
		return typed
	case json.Number:
		if parsed, err := typed.Float64(); err == nil {
			return parsed
		}
	case int:
		return float64(typed)
	case string:
		var parsed json.Number = json.Number(typed)
		if value, err := parsed.Float64(); err == nil {
			return value
		}
	}
	return nil
}
