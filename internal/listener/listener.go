package listener

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"strings"
	"time"

	"github.com/ToSMaverick/meshcom-listener/internal/config"
	"github.com/ToSMaverick/meshcom-listener/internal/store"
)

type Forwarder interface {
	Send(context.Context, store.Message) (bool, error)
}

type Server struct {
	cfg       config.Config
	store     store.Store
	forwarder Forwarder
	logger    *slog.Logger
}

func New(cfg config.Config, messageStore store.Store, forwarder Forwarder, logger *slog.Logger) *Server {
	return &Server{
		cfg:       cfg,
		store:     messageStore,
		forwarder: forwarder,
		logger:    logger,
	}
}

func (s *Server) Serve(ctx context.Context) error {
	addr := net.JoinHostPort(s.cfg.ListenerHost, fmt.Sprintf("%d", s.cfg.ListenerPort))
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return fmt.Errorf("resolve udp address: %w", err)
	}

	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return fmt.Errorf("listen udp: %w", err)
	}
	defer conn.Close()

	s.logger.Info("UDP listener ready", "addr", addr)
	bufferSize := s.cfg.ListenerBuffer
	if bufferSize <= 0 {
		bufferSize = 2048
	}

	buffer := make([]byte, bufferSize)
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		_ = conn.SetReadDeadline(time.Now().Add(time.Second))
		n, remoteAddr, err := conn.ReadFromUDP(buffer)
		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				continue
			}
			return fmt.Errorf("read udp packet: %w", err)
		}

		payload := append([]byte(nil), buffer[:n]...)
		go func() {
			if err := s.ProcessDatagram(ctx, payload, remoteAddr.String()); err != nil {
				s.logger.Warn("packet processing failed", "remote", remoteAddr.String(), "error", err)
			}
		}()
	}
}

func (s *Server) ProcessDatagram(ctx context.Context, data []byte, remoteAddr string) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()

	var payload map[string]any
	if err := decoder.Decode(&payload); err != nil {
		return fmt.Errorf("decode json payload: %w", err)
	}
	return s.ProcessPayload(ctx, payload, remoteAddr)
}

func (s *Server) ProcessPayload(ctx context.Context, payload map[string]any, remoteAddr string) error {
	msgType := stringValue(payload["type"])
	sender, via := SplitSource(stringValue(payload["src"]))
	if sender == "" {
		sender = "unknown"
	}

	message := store.Message{
		Src:     sender,
		Via:     via,
		SrcType: stringValue(payload["src_type"]),
		MsgType: msgType,
		Raw:     payload,
	}

	s.logger.Info("received message", "type", msgType, "src", sender, "remote", remoteAddr)

	if config.Contains(s.cfg.StoreTypes, msgType) || config.Contains(s.cfg.StoreTypes, "*") {
		if err := s.store.SaveMessage(ctx, message); err != nil {
			return err
		}
	}

	if s.cfg.NotifyEnabled && ShouldForward(s.cfg, message) {
		if _, err := s.forwarder.Send(ctx, message); err != nil {
			return err
		}
	}
	return nil
}

func SplitSource(raw string) (string, []string) {
	parts := strings.Split(raw, ",")
	cleaned := make([]string, 0, len(parts))
	for _, part := range parts {
		item := strings.TrimSpace(part)
		if item != "" {
			cleaned = append(cleaned, item)
		}
	}
	if len(cleaned) == 0 {
		return "", nil
	}
	return cleaned[0], cleaned[1:]
}

func ShouldForward(cfg config.Config, message store.Message) bool {
	if !(config.Contains(cfg.ForwardTypes, message.MsgType) || config.Contains(cfg.ForwardTypes, "*")) {
		return false
	}

	if message.MsgType != "msg" {
		return true
	}

	dst := stringValue(message.Raw["dst"])
	if config.Contains(cfg.ForwardExcludeSrc, message.Src) {
		return false
	}
	if len(cfg.ForwardIncludeDst) > 0 && !config.Contains(cfg.ForwardIncludeDst, dst) {
		return false
	}
	if config.Contains(cfg.ForwardExcludeDst, dst) {
		return false
	}
	return true
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	case json.Number:
		return typed.String()
	case float64:
		return fmt.Sprintf("%g", typed)
	case int:
		return fmt.Sprintf("%d", typed)
	default:
		return ""
	}
}
