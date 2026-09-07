# NASA FIRMS Hotspot Integration

FireSight ingests NASA FIRMS active-fire detections as the first real hotspot provider in Part 6B. FIRMS detections are treated as satellite active-fire/hotspot observations, not as confirmed wildfires.

## Provider And Product

- Provider: NASA FIRMS
- Default product: `VIIRS_SNPP_NRT`
- API: FIRMS Area CSV API
- URL shape: `/api/area/csv/[MAP_KEY]/[SOURCE]/[AREA_COORDINATES]/[DAY_RANGE]`
- Area format: `west,south,east,north`
- Day range: `1..5`

The default VIIRS S-NPP near-real-time product is used because VIIRS provides higher-resolution active-fire detections than MODIS for hotspot monitoring. The product remains configurable through `FIRMS_PRODUCT`.

## Configuration

Backend-only environment variables:

- `FIRMS_MAP_KEY`
- `FIRMS_BASE_URL`
- `FIRMS_ENABLED`
- `FIRMS_PRODUCT`
- `FIRMS_LOOKBACK_HOURS`
- `FIRMS_MAX_RECORDS`
- `FIRMS_REQUEST_TIMEOUT`
- `FIRMS_REGION_BUFFER_DEGREES`
- `FIRMS_RETRY_ATTEMPTS`
- `FIRMS_RETRY_BACKOFF_SECONDS`
- `FIRMS_REFRESH_INTERVAL_MINUTES`

`FIRMS_MAP_KEY` is never exposed to the frontend and is not committed. Development and test boot do not require a key. If `FIRMS_ENABLED=true` and no key is configured, the provider returns `UNAVAILABLE` with a configuration error.

## Geographic Filtering

FIRMS requests are region-scoped. The FIRMS client reads monitored region latitude, longitude, timezone, database ID, and bounding box from `backend/services/region_registry.py`.

Current limitation: FireSight does not yet store authoritative region polygons for all monitored forests. Until boundary ingestion exists, FIRMS uses a registry-derived monitoring bounding box around each representative region point. No detailed forest boundary is invented.

## Ingestion Flow

1. `FIRMSProvider` builds a bounded Area CSV request.
2. The response is checked for HTTP, rate-limit, authentication, timeout, and malformed CSV failures.
3. Each row is validated before persistence.
4. Rows are normalized into FireSight hotspot fields.
5. `FIRMSIngestionService` ensures idempotency and writes records to `fire_hotspots`.
6. A compact last-ingestion status is stored in `system_settings`.
7. `HotspotAggregationService` calculates regional 24h, 48h, and 7d summaries.
8. Routes and `EnvironmentalSnapshot` consume the same aggregation path.

## Validation And Normalization

Required FIRMS fields:

- `latitude`
- `longitude`
- `acq_date`
- `acq_time`
- `satellite`
- `instrument`
- `confidence`

Optional fields retained when present:

- brightness, including `bright_ti4`, `brightness`, or `bright_t31`
- `frp`
- `scan`
- `track`
- `daynight`
- `version`

Invalid coordinates, invalid timestamps, missing required fields, malformed CSV, and out-of-bounds observations are rejected. Provider failures are not converted to zero hotspots.

## Deduplication

FIRMS records do not expose one universal row ID across all products. FireSight creates a stable `source_record_id` hash from:

- provider
- FIRMS product
- satellite
- instrument
- acquisition timestamp
- latitude and longitude rounded to five decimals
- FRP
- provider version

The database enforces uniqueness on `(provider, source_record_id)`. Running ingestion twice with the same FIRMS response updates retrieval/provenance metadata and does not create duplicate observations.

## Database Storage

Migration `20260829_0003` adds FIRMS provenance fields to `fire_hotspots`. Hotspot locations are stored with standard `latitude` and `longitude` columns.

Coordinates use WGS84 decimal degrees:

```text
latitude, longitude
```

Region/time and provider/source indexes support aggregation and deduplication.

## Freshness

Freshness uses the Part 6A `HOTSPOT_MAX_AGE_HOURS` setting. For regions with detections, status is based on the latest valid FIRMS detection timestamp. For a successful zero-detection ingestion, status is based on successful retrieval time stored in `system_settings`.

This preserves the critical distinction:

- successful FIRMS query with zero detections: `0` detections and `LIVE` or `RECENT`
- provider or database failure: `UNAVAILABLE`

## API And Frontend

Hotspot API responses expose safe provenance:

- provider
- product
- source type
- status
- retrieved timestamp
- latest detection timestamp
- regional counts
- detection locations

The frontend calls FireSight API endpoints only. It never calls FIRMS and never receives `FIRMS_MAP_KEY`. If FIRMS data is unavailable, hotspot views show an unavailable state instead of fixture hotspots. Simulation mode remains explicit through `DATA_MODE=simulation`.

## Scheduling

When Celery is installed, `firesight.ingest_firms_hotspots` runs on a configurable beat schedule using `FIRMS_REFRESH_INTERVAL_MINUTES`. The task has bounded retry/backoff behavior and should refresh the database ahead of dashboard use. Dashboard refreshes must not trigger FIRMS API calls.

## Attribution

FIRMS data is attributed as NASA FIRMS in API payloads, frontend source labels, and this documentation.
