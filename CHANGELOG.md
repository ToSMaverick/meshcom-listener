# Changelog

All notable changes to this project will be documented in this file.

## [v2026.03.26] - Image Optimization
### Fixed
- **Docker Optimization:** Refactored the `Dockerfile` to use `--chown` during copy operations, eliminating duplicate layers and reducing the final image size.

## [v2026.03.22] - Notification fine-tuning
### Changed
- **Refactor notification handling:** Update send_notification method to use structured data format

## [v2026.03.19] - Refinement & Production Readiness (Phase 5)
### Added
- **Housekeeping:** Implemented an asynchronous background task to prune database records older than a configurable number of days (default: 7).
- **Advanced Forwarding:** 
    - Implemented a template system for Apprise notifications with emojis (✉️ msg, 📍 pos, 📡 raw).
    - Added comprehensive filtering: `FORWARD_TYPES`, `FORWARD_INCLUDE_DST`, `FORWARD_EXCLUDE_DST`, and `FORWARD_EXCLUDE_SRC`.
    - Automated OSM map link generation for position packets.
- **Improved Logging:** More robust handling of SurrealDB return types and detailed raw result logging.

### Changed
- **Architecture Refinement:** Centralized message processing in `listener.py` (src/via splitting) to keep `database.py` focused purely on storage.
- **Config Defaults:** Optimized all default values for seamless out-of-the-box operation with Docker Compose.
- **Schema Update:** Reverted table names to a simpler `message` structure and improved the `UPSERT` logic for node tracking.

## [v2026.03.17] - The SurrealDB Migration (Phases 1-4)
### Added
- **Core Migration:** Complete transition from synchronous SQLite to asynchronous **SurrealDB**.
- **Asynchronous Engine:** Rewrote the UDP listener using `asyncio.DatagramProtocol` for better performance.
- **Hybrid Schema:** Implemented a "best-of-both-worlds" database design with structured metadata fields and a flexible `raw` JSON object.
- **12-Factor Compliance:** Switched configuration management to `environs` for environment-based settings.
- **Notification Gateway:** Replaced direct Telegram logic with a decoupled **Apprise API** integration using `httpx`.
- **Modern Tooling:** Adopted `uv` for lightning-fast dependency management and reproducible builds.
- **Automated CI/CD:** Integrated GitHub Actions to automatically build and publish Docker images to **GHCR**.

### Fixed
- Resolved SurrealDB 3.x compatibility issues (RPC keys and `type::record` function).
- Fixed OOM (Out-of-Memory) issues on low-resource hosts (NUC) through ZVOL-Swap optimization and ZFS ARC limits.

## [v2026.03.10] - Legacy Python Version
### Added
- Original synchronous UDP listener with SQLite storage.
- Telegram forwarding using `requests`.
- Configurable message templates for Telegram MarkdownV2.
- Support for altitude conversion (feet to meters).

---
73 de OE3MIF
