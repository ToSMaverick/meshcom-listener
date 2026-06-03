package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/spf13/cobra"

	"github.com/ToSMaverick/meshcom-listener/internal/config"
	"github.com/ToSMaverick/meshcom-listener/internal/forwarder"
	"github.com/ToSMaverick/meshcom-listener/internal/listener"
	"github.com/ToSMaverick/meshcom-listener/internal/store"
	sqlitestore "github.com/ToSMaverick/meshcom-listener/internal/store/sqlite"
	surrealstore "github.com/ToSMaverick/meshcom-listener/internal/store/surreal"
)

func main() {
	cfg := config.Load()
	logger := newLogger(cfg.LogLevel)

	root := &cobra.Command{
		Use:   "meshcom-listener",
		Short: "MeshCom UDP listener",
	}

	root.AddCommand(
		serveCommand(cfg, logger),
		testCommand(cfg),
		dbCommand(cfg),
		&cobra.Command{
			Use:   "version",
			Short: "Show application version",
			Run: func(cmd *cobra.Command, args []string) {
				fmt.Fprintf(cmd.OutOrStdout(), "MeshCom Listener %s\n", config.Version)
			},
		},
	)

	if err := root.Execute(); err != nil {
		logger.Error("command failed", "error", err)
		os.Exit(1)
	}
}

func serveCommand(cfg config.Config, logger *slog.Logger) *cobra.Command {
	return &cobra.Command{
		Use:   "serve",
		Short: "Start the UDP listener",
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(cmd.Context(), os.Interrupt, syscall.SIGTERM)
			defer stop()

			messageStore, err := newStore(cfg)
			if err != nil {
				return err
			}
			defer messageStore.Close()

			if err := messageStore.Connect(ctx); err != nil {
				return err
			}
			if err := messageStore.Init(ctx); err != nil {
				return err
			}

			go runHousekeeping(ctx, logger, messageStore, cfg.DBRetentionDays)

			server := listener.New(cfg, messageStore, forwarder.New(cfg), logger)
			logger.Info("starting MeshCom listener", "version", config.Version, "backend", cfg.DBBackend)
			return server.Serve(ctx)
		},
	}
}

func testCommand(cfg config.Config) *cobra.Command {
	testCmd := &cobra.Command{
		Use:   "test",
		Short: "Test configuration and backing services",
	}

	testCmd.AddCommand(&cobra.Command{
		Use:   "config",
		Short: "Display current configuration",
		Run: func(cmd *cobra.Command, args []string) {
			out := cmd.OutOrStdout()
			fmt.Fprintf(out, "MeshCom Listener Version: %s\n", config.Version)
			fmt.Fprintf(out, "Listener: %s:%d (Buffer: %d)\n", cfg.ListenerHost, cfg.ListenerPort, cfg.ListenerBuffer)
			fmt.Fprintf(out, "Store Types: %s\n", strings.Join(cfg.StoreTypes, ","))
			fmt.Fprintf(out, "Database Backend: %s\n", cfg.DBBackend)
			fmt.Fprintf(out, "SQLite Path: %s\n", cfg.DBSQLitePath)
			fmt.Fprintf(out, "SurrealDB: %s (User: %s, NS: %s, DB: %s)\n", cfg.DBURL, cfg.DBUser, cfg.DBNS, cfg.DBName)
			fmt.Fprintf(out, "Apprise URL: %s\n", cfg.AppriseURL)
			fmt.Fprintf(out, "Notifications: %t\n", cfg.NotifyEnabled)
			fmt.Fprintf(out, "Notification Targets: %s\n", strings.Join(cfg.NotifyTargets, ","))
		},
	})

	testCmd.AddCommand(&cobra.Command{
		Use:   "db",
		Short: "Validate database connection and schema",
		RunE: func(cmd *cobra.Command, args []string) error {
			messageStore, err := newStore(cfg)
			if err != nil {
				return err
			}
			defer messageStore.Close()

			if err := messageStore.Connect(cmd.Context()); err != nil {
				return err
			}
			if err := messageStore.Init(cmd.Context()); err != nil {
				return err
			}
			if err := messageStore.Ping(cmd.Context()); err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), "Database connection OK.")
			return nil
		},
	})

	testCmd.AddCommand(&cobra.Command{
		Use:   "notify",
		Short: "Validate Apprise connection and send a test notification",
		RunE: func(cmd *cobra.Command, args []string) error {
			client := forwarder.New(cfg)
			ok, err := client.Send(cmd.Context(), store.Message{
				Src:     "TEST-NODE",
				Via:     []string{"GATEWAY-1", "GATEWAY-2"},
				MsgType: "msg",
				Raw: map[string]any{
					"type": "msg",
					"src":  "TEST-NODE",
					"dst":  "ADMIN",
					"msg":  "Connection Test: MeshCom Listener Notify works!",
				},
			})
			if err != nil {
				return err
			}
			if !ok {
				return errors.New("notification skipped; check NOTIFY_ENABLED and NOTIFY_TARGETS")
			}
			fmt.Fprintln(cmd.OutOrStdout(), "Apprise notification sent.")
			return nil
		},
	})

	return testCmd
}

func dbCommand(cfg config.Config) *cobra.Command {
	dbCmd := &cobra.Command{
		Use:   "db",
		Short: "Manage database schema",
	}

	dbCmd.AddCommand(&cobra.Command{
		Use:   "init",
		Short: "Initialize database schema",
		RunE: func(cmd *cobra.Command, args []string) error {
			messageStore, err := newStore(cfg)
			if err != nil {
				return err
			}
			defer messageStore.Close()
			if err := messageStore.Connect(cmd.Context()); err != nil {
				return err
			}
			if err := messageStore.Init(cmd.Context()); err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), "Database schema initialized.")
			return nil
		},
	})

	dbCmd.AddCommand(&cobra.Command{
		Use:   "reset",
		Short: "Reset database schema and remove all data",
		RunE: func(cmd *cobra.Command, args []string) error {
			messageStore, err := newStore(cfg)
			if err != nil {
				return err
			}
			defer messageStore.Close()
			if err := messageStore.Connect(cmd.Context()); err != nil {
				return err
			}
			if err := messageStore.Reset(cmd.Context()); err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), "Database reset complete.")
			return nil
		},
	})

	return dbCmd
}

func newStore(cfg config.Config) (store.Store, error) {
	switch cfg.DBBackend {
	case "", "sqlite":
		return sqlitestore.New(cfg.DBSQLitePath), nil
	case "surreal", "surrealdb":
		return surrealstore.New(cfg.DBURL), nil
	default:
		return nil, fmt.Errorf("unsupported DB_BACKEND %q", cfg.DBBackend)
	}
}

func runHousekeeping(ctx context.Context, logger *slog.Logger, messageStore store.Store, retentionDays int) {
	ticker := time.NewTicker(4 * time.Hour)
	defer ticker.Stop()

	for {
		if err := messageStore.PruneOldMessages(ctx, retentionDays); err != nil {
			logger.Warn("housekeeping failed", "error", err)
		}

		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func newLogger(level string) *slog.Logger {
	var parsed slog.Level
	switch strings.ToUpper(level) {
	case "DEBUG":
		parsed = slog.LevelDebug
	case "WARN", "WARNING":
		parsed = slog.LevelWarn
	case "ERROR":
		parsed = slog.LevelError
	default:
		parsed = slog.LevelInfo
	}

	return slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: parsed}))
}
