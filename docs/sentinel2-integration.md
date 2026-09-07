# Sentinel-2 Acquisition Integration

FireSight Part 6C adds real Sentinel-2 scene acquisition metadata and controlled product downloads. This phase does not calculate NDVI, NBR, burn severity, cloud/shadow masks, raster tiles, or model features.

## Provider And Interface

- Provider: Copernicus Data Space Ecosystem
- Catalogue API: OData Products endpoint
- Catalogue URL: `https://catalogue.dataspace.copernicus.eu/odata/v1/Products`
- Download URL shape: `https://download.dataspace.copernicus.eu/odata/v1/Products(<PRODUCT_UUID>)/$value`
- OAuth token URL: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`
- Default product type: `S2MSI2A`

`S2MSI2A` is used because future NDVI/NBR work needs Sentinel-2 Level-2A surface reflectance bands. Part 6C only acquires the product archive and metadata needed for that future processing.

## Configuration

Backend-only environment variables:

- `COPERNICUS_CLIENT_ID`
- `COPERNICUS_CLIENT_SECRET`
- `COPERNICUS_TOKEN_URL`
- `SENTINEL_ENABLED`
- `SENTINEL_BASE_URL`
- `SENTINEL_CATALOG_URL`
- `SENTINEL_DOWNLOAD_URL`
- `SENTINEL_PRODUCT_TYPE`
- `SENTINEL_LOOKBACK_DAYS`
- `SENTINEL_MAX_CLOUD_COVER`
- `SENTINEL_REQUEST_TIMEOUT`
- `SENTINEL_MAX_SCENE_SIZE_MB`
- `SENTINEL_TEMP_DIR`
- `SENTINEL_RETRY_ATTEMPTS`
- `SENTINEL_RETRY_BACKOFF_SECONDS`
- `SENTINEL_REFRESH_INTERVAL_HOURS`

Credentials are never exposed to the frontend, logs, API responses, or database records. If `SENTINEL_ENABLED=false`, FireSight stays healthy and reports Sentinel/vegetation as `UNAVAILABLE`.

## Discovery And Selection

The provider builds an OData filter with:

- collection: `SENTINEL-2`
- product type: configurable, default `S2MSI2A`
- acquisition date window from `SENTINEL_LOOKBACK_DAYS`
- cloud-cover threshold from `SENTINEL_MAX_CLOUD_COVER`
- geographic intersection with the configured FireSight region bounding box

Candidate scenes are sorted deterministically:

1. online products first
2. lower cloud cover first
3. newer acquisition time first
4. product name as the stable final tie-breaker

## Acquisition

Acquisition is idempotent by `(provider, product_id)`. If a previously verified scene exists, FireSight reuses that record and does not download the same product again.

Downloaded product archives are written under `SENTINEL_TEMP_DIR` using a `.part` file and atomic replacement. The provider enforces `SENTINEL_MAX_SCENE_SIZE_MB`, rejects empty or HTML responses, computes a SHA-256 checksum, and stores only metadata plus a local storage reference in `satellite_images`.

## Database Fields

Migration `20260829_0004` extends `satellite_images` with:

- provider/product id and uniqueness
- platform/product level
- captured/retrieved timestamps
- acquisition and quality statuses
- storage reference, file size, checksum
- source reference and provider metadata

Raw Sentinel imagery is not stored in Git or in the database.

## API And Frontend

Public status endpoints:

- `GET /api/vegetation/satellite/status`
- `GET /api/vegetation/satellite/latest?region_id=r1`

Protected acquisition endpoint:

- `POST /api/vegetation/satellite/acquire?region_id=r1`

The frontend displays Sentinel scene status and continues to label NDVI/NBR as unavailable until a later processing phase creates real vegetation indices.

## Scheduling

When Celery is installed, `firesight.acquire_latest_sentinel_scene` runs on a configurable beat schedule using `SENTINEL_REFRESH_INTERVAL_HOURS`.

## Attribution

Sentinel-2 scene data is attributed to the Copernicus Data Space Ecosystem.
