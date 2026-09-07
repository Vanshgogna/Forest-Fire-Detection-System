# Data Accuracy Audit

Date: 2026-08-29

## Current Status

Weather data is now retrieved from Open-Meteo through the backend production data path. The app requests weather by configured forest-region coordinates, not by generic city name.

Bandipur Tiger Reserve currently uses:

- Region id: `r1`
- Coordinates: `11.667, 76.629`
- Timezone: `Asia/Kolkata`
- Coordinate method: configured representative point
- Provider: Open-Meteo
- Units: Celsius, km/h, mm, hPa

## Live Data

The following weather fields are retrieved from Open-Meteo where available:

- Temperature
- Apparent temperature
- Relative humidity
- Wind speed
- Wind direction
- Wind gusts
- Rainfall and precipitation
- Pressure
- Cloud cover
- Hourly forecast
- Daily forecast
- UV index in hourly/daily forecast

Every weather response includes provider, source URL, source type, coordinates, timezone, observed timestamp, retrieved timestamp, cache status, and quality flags.

## Simulated Data

The following data is still a development fixture because no live provider credentials, catalogs, or ingestion jobs are configured in this repository:

- Region risk scores
- NDVI/NBR vegetation values
- Satellite coverage values
- MODIS/VIIRS hotspot counts
- Alerts
- Reports
- Historical risk trend points
- AI recommendation examples

The backend and frontend now label these as `simulated_development_fixture` or equivalent visible copy. These values must not be treated as operational measurements.

## Fire Weather Metric

The existing custom calculation is now labeled `Fire Weather Risk Index`. It is not the official Canadian Forest Fire Weather Index.

## Diagnostic Endpoints

- `GET /api/weather/?region_id=r1`
- `GET /api/weather/forecast?region_id=r1`
- `GET /api/weather/debug?region_id=r1`
- `GET /api/weather/compare?region_id=r1&reference_temperature=29&reference_source=Google%20Weather`

The comparison endpoint records provider, coordinates, timestamp, source, and metric differences. It does not force Open-Meteo values to match Google Weather.

## Stage 2 Forensic Validation

The Bandipur temperature mismatch was investigated as a data provenance issue, not patched by changing the displayed value.

### Location

The backend now reads forest-region coordinates from `backend/services/region_registry.py`. The frontend fixture views read the same coordinate values from `frontend/src/constants/regionLocations.ts`; the backend registry remains the canonical source for live API calls.

- Bandipur Tiger Reserve: `11.667, 76.629`
- CRS: `EPSG:4326`
- Timezone: `Asia/Kolkata`
- Coordinate method: configured representative point

This is a representative point for the reserve, not a polygon centroid derived from an authoritative boundary file. Open-Meteo can return a nearby model grid location for the requested point; the live check on 2026-08-29 returned model coordinates near `11.704745, 76.63685`. A Google Weather card may use a different place lookup, model grid, or observation station, so both products must be compared by exact coordinate and timestamp before treating a difference as an error.

### Timestamp

Weather responses expose the raw provider timestamp, retrieval time in UTC, application-local time, timezone, and observation age in minutes.

Data status is classified as:

- `LIVE`: valid current data within `WEATHER_RECENT_MINUTES`
- `RECENT`: valid data older than recent threshold but within `WEATHER_STALE_MINUTES`
- `CACHED`: valid cached response within cache TTL
- `STALE`: valid data older than `WEATHER_STALE_MINUTES`
- `UNAVAILABLE`: provider and usable cache are unavailable
- `SUSPICIOUS`: invalid ranges, missing observation age, invalid coordinates, or provider timestamp too far in the future

Default thresholds are configurable in `backend/core/config.py`.

### Weather Variable And Units

The displayed temperature is Open-Meteo `temperature_2m`: air temperature at 2 meters above ground from current conditions. It is not apparent temperature, a historical daily maximum, or a manually corrected station reading.

Exact request parameters are exposed in `request.params` on debug weather responses. The request uses:

- `timezone=Asia/Kolkata`
- `temperature_unit=celsius`
- `wind_speed_unit=kmh`
- `precipitation_unit=mm`
- `forecast_days=1..7`
- Current variables including `temperature_2m`, `apparent_temperature`, `relative_humidity_2m`, `wind_speed_10m`, `rain`, `surface_pressure`, and `cloud_cover`

### Cross-Provider Difference

On the live Bandipur check, Open-Meteo returned `25.8°C` while the user-reported Google Weather value was `29°C`, a difference of `-3.2°C`.

The comparison endpoint classifies this as `warning` with the default temperature threshold:

- Warning: `>= 3.0°C`
- Investigation required: `>= 6.0°C`

This warning means the discrepancy should be reviewed with exact Google coordinates, observation timestamp, and source type. The app must not silently rewrite Open-Meteo data to match another provider.

### Fallback And Cache

The backend no longer returns mock weather when Open-Meteo fails. The weather path is:

- live Open-Meteo response
- valid cache while TTL is active, labeled `CACHED`
- explicit unavailable response when live data and cache are unavailable

Frontend demo fallbacks are labeled as simulated development fixtures so they are not confused with operational weather.

### Prediction Consistency

Prediction responses now include an input snapshot with the exact values used for inference. This prevents the prediction card, detail view, and backend model input from drifting apart when live weather changes or cached values are served.

## Remaining Work Before Operational Use

Connect and validate real providers for:

- Sentinel-2 scene catalog and NDVI/NBR processing
- MODIS/VIIRS hotspot feed ingestion
- Region boundary/polygon storage with centroid derivation
- Historical fire records
- Model training/inference records persisted with weather, vegetation, hotspot, timestamp, and model-version provenance
