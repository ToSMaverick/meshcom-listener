package surreal

import (
	"context"
	"fmt"

	"github.com/ToSMaverick/meshcom-listener/internal/store"
)

type Store struct {
	url string
}

func New(url string) *Store {
	return &Store{url: url}
}

func (s *Store) Connect(context.Context) error {
	return fmt.Errorf("surrealdb backend at %s: %w", s.url, store.ErrUnsupported)
}

func (s *Store) Init(context.Context) error {
	return store.ErrUnsupported
}

func (s *Store) SaveMessage(context.Context, store.Message) error {
	return store.ErrUnsupported
}

func (s *Store) PruneOldMessages(context.Context, int) error {
	return store.ErrUnsupported
}

func (s *Store) Ping(context.Context) error {
	return store.ErrUnsupported
}

func (s *Store) Reset(context.Context) error {
	return store.ErrUnsupported
}

func (s *Store) Close() error {
	return nil
}
