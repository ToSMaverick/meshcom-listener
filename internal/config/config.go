package config

import (
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

const Version = "0.3.0-go"

type Config struct {
	LogLevel string

	ListenerHost   string
	ListenerPort   int
	ListenerBuffer int
	StoreTypes     []string

	DBBackend       string
	DBSQLitePath    string
	DBURL           string
	DBUser          string
	DBPass          string
	DBNS            string
	DBName          string
	DBRetentionDays int

	NotifyEnabled     bool
	AppriseURL        string
	NotifyTargets     []string
	ForwardTypes      []string
	ForwardIncludeDst []string
	ForwardExcludeDst []string
	ForwardExcludeSrc []string
}

func Load() Config {
	_ = godotenv.Load()

	return Config{
		LogLevel: getString("LOG_LEVEL", "INFO"),

		ListenerHost:   getString("LISTENER_HOST", "0.0.0.0"),
		ListenerPort:   getInt("LISTENER_PORT", 1799),
		ListenerBuffer: getInt("LISTENER_BUFFER", 2048),
		StoreTypes:     getList("STORE_TYPES", []string{"msg", "pos", "tele"}),

		DBBackend:       strings.ToLower(getString("DB_BACKEND", "sqlite")),
		DBSQLitePath:    getString("DB_SQLITE_PATH", "/data/meshcom.db"),
		DBURL:           getString("DB_URL", "ws://surrealdb:8000"),
		DBUser:          getString("DB_USER", "root"),
		DBPass:          getString("DB_PASS", "root"),
		DBNS:            getString("DB_NS", "meshcom"),
		DBName:          getString("DB_DB", "listener"),
		DBRetentionDays: getInt("DB_RETENTION_DAYS", 7),

		NotifyEnabled:     getBool("NOTIFY_ENABLED", false),
		AppriseURL:        getString("APPRISE_URL", "http://apprise:8000/notify"),
		NotifyTargets:     getList("NOTIFY_TARGETS", nil),
		ForwardTypes:      getList("FORWARD_TYPES", []string{"msg", "pos"}),
		ForwardIncludeDst: getList("FORWARD_INCLUDE_DST", nil),
		ForwardExcludeDst: getList("FORWARD_EXCLUDE_DST", []string{"*"}),
		ForwardExcludeSrc: getList("FORWARD_EXCLUDE_SRC", nil),
	}
}

func getString(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func getInt(key string, fallback int) int {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func getBool(key string, fallback bool) bool {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func getList(key string, fallback []string) []string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return append([]string(nil), fallback...)
	}

	parts := strings.Split(value, ",")
	items := make([]string, 0, len(parts))
	for _, part := range parts {
		item := strings.TrimSpace(part)
		if item != "" {
			items = append(items, item)
		}
	}
	return items
}

func Contains(items []string, value string) bool {
	for _, item := range items {
		if item == value {
			return true
		}
	}
	return false
}
