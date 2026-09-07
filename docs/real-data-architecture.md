# Real Data Architecture

Date: 2026-08-29

## Scope

Part 6A establishes the foundation for real environmental data. Part 6B adds NASA FIRMS hotspot ingestion and regional hotspot aggregation. Part 6C adds Copernicus Sentinel-2 scene discovery, metadata persistence, controlled product download, and acquisition provenance. Part 6D-1 adds Sentinel-2 raster/band validation and analysis-ready RED/NIR/SWIR preparation. It does not implement NDVI, NBR, cloud masking, ML retraining, or real environmental prediction.

## Canonical Flow

External providers should plug into this path:

`Provider client -> ingestion/validation -> canonical model -> database/repository -> domain service -> API -> frontend/ML/alerts`

Frontend and ML code must consume FireSight APIs or domain services, not external provider SDKs directly.

## Provider Foundation

Shared provider vocabulary lives in `backend/services/environmental_foundation.py`.

- Provider types: `WEATHER`, `SATELLITE`, `HOTSPOT`, `OTHER`
- Data statuses: `LIVE`, `RECENT`, `CACHED`, `STALE`, `UNAVAILABLE`, `SUSPICIOUS`, `SIMULATED`
- Data modes: `live`, `simulation`
- Error kinds: `CONFIGURATION_ERROR`, `AUTHENTICATION_ERROR`, `RATE_LIMITED`, `TIMEOUT`, `PROVIDER_UNAVAILABLE`, `INVALID_RESPONSE`, `VALIDATION_ERROR`, `DATABASE_ERROR`, `UNKNOWN`

The Open-Meteo weather provider still owns its API-specific request/normalization logic, but now reports provider type, canonical status, provenance, unit metadata, and classified errors through the shared foundation.

## Region Registry

`backend/services/region_registry.py` is the canonical source for configured forest-region coordinates in this phase. Region ids are string ids such as `r1`; existing database tables use integer `regions.id`. Part 6B maps registry ids to database ids in the registry and derives monitoring bounding boxes from the same configuration.

Frontend fixture screens use `frontend/src/constants/regionLocations.ts` only for demo rendering. Backend provider calls resolve regions through the backend registry.

## Provenance

Reusable provenance is represented by `DataProvenance`.

Supported fields include:

- `provider`
- `provider_type`
- `source_type`
- `source_record_id`
- `source_url`
- `observed_at`
- `acquired_at`
- `retrieved_at`
- `request_id`
- `region_id`
- `quality_status`

Observation/acquisition time and retrieval time are separate. Weather uses `observed_at` and `retrieved_at`; FIRMS hotspots use detection/acquisition time separately from retrieval time.

## Freshness And Units

Freshness is centralized through `FreshnessPolicy.from_settings()`.

- Weather recent window: `WEATHER_RECENT_MINUTES`
- Weather stale/max-age window: `WEATHER_STALE_MINUTES`
- Vegetation max age: `VEGETATION_MAX_AGE_DAYS`
- Hotspot max age: `HOTSPOT_MAX_AGE_HOURS`

Canonical units are defined in `CANONICAL_UNITS`: temperature in Celsius, wind in km/h, rainfall/precipitation in mm, pressure in hPa, humidity/cloud cover in percent, and WGS84 coordinates in degrees.

## Environmental Snapshot

The partial snapshot API is:

`GET /api/environmental-snapshot/{region_id}`

It returns a canonical shape with:

- `region_id`
- `timestamp`
- `data_mode`
- `region`
- `weather`
- `vegetation`
- `hotspots`
- `provenance`
- `quality`
- `availability`

Weather is populated from the existing Open-Meteo integration when available. Vegetation remains an explicit `UNAVAILABLE` value record because Sentinel-2 Part 6D-1 prepares bands only and does not compute NDVI/NBR. When a Sentinel scene exists, vegetation provenance can point to that acquired scene and raster-preparation status. Hotspots are populated from FIRMS-ingested database records when available; otherwise they remain `UNAVAILABLE`. Missing data is represented as missing data, not as zero or fabricated NDVI/NBR/hotspot values.

## Repository And Service Boundary

Existing repositories in `backend/repositories/environment.py` provide database access for:

- regions
- weather records
- vegetation records
- satellite image acquisition records
- hotspots
- predictions
- alerts

The new `EnvironmentalDataService` is the domain-level access point for latest environmental data and snapshots. Future provider ingestion should write canonical records through repositories, while APIs should read through domain services.

## Cache Policy

The current weather path uses provider response caching before returning API payloads. Cached responses carry `cache.status`, `age_seconds`, `ttl_seconds`, and a canonical `CACHED` data status. Expired or unavailable live data must not be presented as `LIVE`.

Redis remains optional; the existing memory fallback is sufficient for this phase.

## Simulation Mode

`DATA_MODE` supports:

- `live`
- `simulation`

Production validation requires `DATA_MODE=live`. Simulation and fixture data are allowed for tests and demos, but production code must not silently fall back to fixtures when a live provider is unavailable.

## Mock-Data Boundary

Current mock dependencies discovered:

- `backend/services/mock_environment.py`: development fixture regions, vegetation/risk/hotspot/alert values.
- Backend demo/API surfaces using those fixtures: dashboard risk summary, GIS demo risk layers, analytics summary, vegetation summary, prediction list, selected explainability sample non-weather features. Live-mode hotspot APIs now read FIRMS-backed database aggregation.
- `frontend/src/constants/mockData.ts`: frontend demo cards, charts, reports, alerts, risk values, vegetation values, and hotspot values.
- Tests: fixture payloads for ML, API contracts, remote-sensing contracts, and weather provider mocks.

These are acceptable for testing/demo use when `DATA_MODE=simulation`. They are not operational environmental measurements and must not be used as silent fallbacks when FIRMS is unavailable.

## Future Integration Points

Part 6B and later can add:

- NASA FIRMS client as a `HOTSPOT` provider: implemented in Part 6B
- Sentinel-2/Copernicus client as a `SATELLITE` provider: acquisition implemented in Part 6C
- validation/normalization into canonical hotspot and vegetation records
- repository writes for real ingested hotspot records: implemented in Part 6B
- snapshot lineage from prediction to environmental inputs
- ML feature construction from canonical snapshots

Do not connect ML directly to FIRMS, Sentinel, or Open-Meteo provider clients.
