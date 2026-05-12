package store

import (
	"context"
	"errors"
)

var ErrUnsupported = errors.New("backend is not implemented in the Go port yet")

type Message struct {
	Src     string
	Via     []string
	SrcType string
	MsgType string
	Raw     map[string]any
}

type Store interface {
	Connect(ctx context.Context) error
	Init(ctx context.Context) error
	SaveMessage(ctx context.Context, message Message) error
	PruneOldMessages(ctx context.Context, days int) error
	Ping(ctx context.Context) error
	Reset(ctx context.Context) error
	Close() error
}
