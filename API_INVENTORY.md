# External API & Credentials Inventory
**Project**: AI-Based Smart Traffic Monitoring and Congestion Prediction System  
**Deployment Target**: Render Web Services & Persistent Cloud Storage  
**Audit Date**: 2026-11-04  

This inventory documents all external APIs, credentials, cryptographic keys, and environment variables used by the Bengaluru Metropolitan Smart Traffic AI application.

---

## 1. External Cloud Services & Provider Credentials

| Service | Environment Variable | Consuming Files | Functional Purpose | Required / Optional | Failover / Fallback Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Maps Platform** | `GOOGLE_MAPS_API_KEY` | `traffic_system/config.py`<br>`traffic_system/integrations/google_maps_client.py`<br>`traffic_system/integrations/api_manager.py`<br>`run_system.py`<br>`app/server.py` | Powers Google Maps JavaScript API, Places Autocomplete search, Geocoding, and macroscopic congestion heatmap layers. | **Optional / Recommended** | Application renders interactive canvas with 24 Bengaluru arterial corridors in obsidian vector fallback mode. |
| **Google Maps Platform (Browser)** | `GOOGLE_MAPS_BROWSER_KEY` | `traffic_system/config.py`<br>`traffic_system/integrations/api_manager.py`<br>`app/server.py` | Browser-restricted key delivered to frontend clients via `/api/map/config` (HTTP referrer restricted). Falls back to `GOOGLE_MAPS_API_KEY`. | **Optional** | Uses `GOOGLE_MAPS_API_KEY` if not explicitly separated. |
| **Google Maps Map ID** | `GOOGLE_MAPS_MAP_ID` | `traffic_system/config.py`<br>`app/server.py` | Vector map styling ID for custom obsidian-themed Google Maps tiles. | **Optional** | Falls back to default Google Maps raster/vector styling. |
| **TomTom Traffic Flow & Routing** | `TOMTOM_API_KEY` | `traffic_system/config.py`<br>`traffic_system/integrations/tomtom_client.py`<br>`traffic_system/live/bridge.py`<br>`traffic_system/integrations/api_manager.py`<br>`run_system.py` | Backend-only probe speed observations (Flow Segment Data), municipal incidents, and Calculate Route traffic-aware routing. Kept strictly on backend. | **Optional / Recommended** | Employs calibrated Bengaluru physics baseline with explicit provenance labels; never falsely reports baseline as live. |
| **Open-Meteo Weather** | `WEATHER_API_KEY` | `traffic_system/config.py`<br>`traffic_system/integrations/weather_client.py`<br>`traffic_system/integrations/api_manager.py` | Meteorological weather telemetry (precipitation, visibility, wind speed, temperature). Default provider is Open-Meteo public API (`https://api.open-meteo.com/v1/forecast`). | **Optional (No key required)** | Open-Meteo public endpoints operate without an API key (`none_required`). If unreachable, falls back to seasonal climatological defaults with explicit provenance. |

---

## 2. Application Security, Cryptography & Vault Credentials

| Component | Environment Variable | Consuming Files | Functional Purpose | Required / Optional | Security Constraints |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Application Security** | `APP_SECRET_KEY` | `traffic_system/config.py`<br>`traffic_system/core/security.py` | Master cryptographic seed for application tokens and CSRF defense. | **Required in Production** | Generated securely via CSPRNG (`secrets.token_hex(32)`) if omitted in development. |
| **Session Security** | `SESSION_SECRET_KEY` | `traffic_system/config.py`<br>`traffic_system/core/security.py` | HMAC signing key for session token validation and expiration checking. | **Optional** | Defaults to `APP_SECRET_KEY`. |
| **Encrypted Secrets Vault** | `VAULT_MASTER_KEY` | `traffic_system/config.py`<br>`traffic_system/core/secrets_manager.py` | Master passphrase for Argon2id/scrypt KDF deriving 256-bit AES-GCM key for `.secrets.vault`. | **Required in Production** | Replaces deprecated `SECRETS_VAULT_KEY`. Fails securely in production if missing when vault is used. |

---

## 3. Server & Deployment Configuration Variables

| Variable | Default Value | Consuming Files | Description |
| :--- | :--- | :--- | :--- |
| `APP_ENV` / `ENV` | `development` | `traffic_system/config.py`<br>`run_system.py`<br>`app/server.py` | Environment mode (`production`, `development`, `test`). In production, strict security and credentials enforcement are enabled. |
| `DEBUG` | `false` (prod) / `true` (dev) | `traffic_system/config.py`<br>`run_system.py` | Toggles detailed debugging logs and tracebacks. |
| `HOST` | `0.0.0.0` | `run_system.py`<br>`app/server.py` | Network interface binding address. Binds to `0.0.0.0` for containerized hosting. |
| `PORT` | `10000` (Render) / `8080` (local) | `run_system.py`<br>`app/server.py` | HTTP listener port dynamically assigned by Render or local runner. |
| `PERSISTENT_DATA_DIR` | `/var/data` | `traffic_system/config.py`<br>`run_system.py`<br>`traffic_system/storage/video_storage.py` | Directory path of mounted persistent disk (Render 10 GB disk). Preserves user database, sessions, video uploads, and events. |
| `MAX_VIDEO_UPLOAD_SIZE` | `268435456` (256 MB) | `traffic_system/config.py`<br>`app/server.py` | Maximum size for Computer Vision traffic video uploads. |
| `CHUNK_UPLOAD_SIZE` | `8388608` (8 MB) | `traffic_system/config.py`<br>`app/routes/vision_routes.py` | Chunk upload buffer size for disk-backed chunked transfer. |
| `ALLOW_DEMO_ACCOUNTS` | `false` (prod) / `true` (dev) | `traffic_system/config.py`<br>`traffic_system/core/security.py` | Controls whether default demo logins (`commuter`, `traffic_admin`) can be seeded or authenticated. |
| `ENFORCE_ADMIN_AUTH` | `true` (prod) / `false` (dev) | `traffic_system/config.py`<br>`app/server.py` | Enforces strict Bearer token authentication on all administrative endpoints. |
| `CORS_ALLOWED_ORIGINS` | `*` | `traffic_system/config.py`<br>`app/server.py` | Permitted origins for Cross-Origin Resource Sharing. |
| `SESSION_TTL_SECONDS` | `86400` (24h) | `traffic_system/config.py`<br>`traffic_system/core/security.py` | Session lifetime before automatic token invalidation. |

---

## 4. Key Archival & Deprecation Mapping

The following legacy variable names were identified and mapped to canonical variables to resolve startup configuration mismatches:

| Legacy / Deprecated Name | Canonical Variable | Status |
| :--- | :--- | :--- |
| `API_KEY_GOOGLE_MAPS` | `GOOGLE_MAPS_API_KEY` | Deprecated, backwards-compatible alias maintained in config. |
| `API_KEY_TOMTOM` | `TOMTOM_API_KEY` | Deprecated, backwards-compatible alias maintained in config. |
| `API_KEY_WEATHER` | `WEATHER_API_KEY` | Deprecated, backwards-compatible alias maintained in config. |
| `SECRETS_VAULT_KEY` | `VAULT_MASTER_KEY` | Deprecated, backwards-compatible alias maintained in config. |
| `SECRET_KEY` | `APP_SECRET_KEY` | Deprecated, backwards-compatible alias maintained in config. |
| `JWT_SECRET` | `SESSION_SECRET_KEY` | Deprecated, backwards-compatible alias maintained in config. |

---

## 5. Security & Isolation Invariants

1. **TomTom Traffic API**: Key remains 100% server-side. Frontend browser code never receives or directly calls TomTom endpoints.
2. **Google Maps Platform**: Separate browser key (`GOOGLE_MAPS_BROWSER_KEY`) is delivered to client via `/api/map/config` with HTTP referrer restrictions. Backend Google API keys are never exposed in JSON responses.
3. **No Plaintext Secrets in Vault**: Sensitive keys stored on disk are encrypted using AES-256-GCM with scrypt/Argon2id KDF and memory zeroization of master buffers upon unload.
4. **Resilient Offline Modes**: If external provider credentials are missing or unreachable, the system fails gracefully into calibrated baseline modes rather than crashing or claiming stale data as live.
