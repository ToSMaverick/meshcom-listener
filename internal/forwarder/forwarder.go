package forwarder

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/ToSMaverick/meshcom-listener/internal/config"
	"github.com/ToSMaverick/meshcom-listener/internal/store"
)

type Client struct {
	cfg        config.Config
	httpClient *http.Client
}

type apprisePayload struct {
	URLs   string `json:"urls"`
	Title  string `json:"title"`
	Body   string `json:"body"`
	Format string `json:"format"`
	Type   string `json:"type"`
}

func New(cfg config.Config) *Client {
	return &Client{
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (c *Client) Send(ctx context.Context, message store.Message) (bool, error) {
	if !c.cfg.NotifyEnabled || len(c.cfg.NotifyTargets) == 0 {
		return false, nil
	}

	payload := BuildPayload(c.cfg.NotifyTargets, message)
	body, err := json.Marshal(payload)
	if err != nil {
		return false, fmt.Errorf("marshal apprise payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.cfg.AppriseURL, bytes.NewReader(body))
	if err != nil {
		return false, fmt.Errorf("create apprise request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return false, fmt.Errorf("send apprise request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return false, fmt.Errorf("apprise returned status %s", resp.Status)
	}
	return true, nil
}

func BuildPayload(targets []string, message store.Message) apprisePayload {
	viaDisplay := strings.Join(message.Via, ", ")

	title := fmt.Sprintf("%s from %s", strings.ToUpper(message.MsgType), message.Src)
	body := fmt.Sprintf("Via: %s\n```json\n%s\n```", viaDisplay, prettyJSON(message.Raw))

	switch message.MsgType {
	case "msg":
		dst := stringValue(message.Raw["dst"], "???")
		text := stringValue(message.Raw["msg"], "")
		title = fmt.Sprintf("Message from %s", message.Src)
		body = fmt.Sprintf("To: %s\nVia: %s\n\n%s", dst, viaDisplay, text)
	case "pos":
		lat := stringValue(message.Raw["lat"], "?")
		long := stringValue(message.Raw["long"], "?")
		alt := stringValue(message.Raw["alt"], "?")
		title = fmt.Sprintf("Position from %s", message.Src)
		body = fmt.Sprintf("Via: %s\nLat: %s, Lon: %s\nAlt: %sft", viaDisplay, lat, long, alt)
		if lat != "?" && long != "?" {
			body += fmt.Sprintf("\n[OSM Map](https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=15/%s/%s)", lat, long, lat, long)
		}
	}

	return apprisePayload{
		URLs:   strings.Join(targets, ","),
		Title:  title,
		Body:   body,
		Format: "markdown",
		Type:   "info",
	}
}

func prettyJSON(value any) string {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return "{}"
	}
	return string(data)
}

func stringValue(value any, fallback string) string {
	switch typed := value.(type) {
	case string:
		if typed != "" {
			return typed
		}
	case json.Number:
		return typed.String()
	case float64:
		return fmt.Sprintf("%g", typed)
	case int:
		return fmt.Sprintf("%d", typed)
	}
	return fallback
}
