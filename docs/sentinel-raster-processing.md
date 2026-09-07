# Sentinel Raster Processing

FireSight Part 6D-1 prepares acquired Sentinel-2 scenes for future vegetation-index processing. It stops after producing validated RED, NIR, and SWIR raster inputs.

**NDVI and NBR are NOT implemented in Part 6D-1.**

## Product Scope

Supported product:

- Sentinel-2 Level-2A (`S2MSI2A`)
- SAFE directory or SAFE product archive (`.zip`) acquired by Part 6C
- Local storage reference from `satellite_images.storage_reference`

The raster service rejects non-Sentinel records, missing storage references, missing files, unacquired scenes, and unsupported processing levels.

## Band Mapping

Canonical FireSight band names are mapped to Sentinel-2 MSI identifiers:

| Canonical band | Sentinel-2 band | Native resolution | Future use |
| --- | --- | ---: | --- |
| `RED` | `B04` | 10 m | NDVI red input |
| `NIR` | `B08` | 10 m | NDVI/NBR near-infrared input |
| `SWIR` | `B11` | 20 m | NBR shortwave-infrared input |

The code discovers bands from the product file structure and metadata. It does not substitute another band if a required band is missing.

## Analysis Grid

The common analysis grid uses the `B11` SWIR grid at 20 m.

Rationale:

- `B04` and `B08` are native 10 m.
- `B11` is native 20 m.
- Future NBR requires NIR and SWIR on the same grid.
- Using 20 m avoids arbitrary SWIR upsampling and does not claim to create spatial detail that is absent in the source product.

If a future phase needs 10 m NDVI-only outputs, that can be generated separately from `B04` and `B08`.

## CRS Strategy

The service uses the scene CRS from the Sentinel product, typically the scene UTM CRS. It does not reproject all bands into latitude/longitude for analysis.

All required bands must share a CRS. If RED, NIR, and SWIR do not share the same CRS, processing fails.

## Crop Strategy

Processing is region-scoped. FireSight uses `backend/services/region_registry.py` to resolve known monitored regions and uses the registry bounding box for clipping.

Current limitation: authoritative forest-boundary polygons are not available for every monitored region, so Part 6D-1 uses the configured monitoring bounding box. It does not invent forest boundaries.

## Resampling

When band resolution differs from the analysis grid, the service resamples continuous reflectance data with bilinear interpolation through Rasterio/GDAL `WarpedVRT`.

Recorded provenance includes:

- source native resolution
- target analysis resolution
- analysis CRS
- crop bounds
- resampling method

Nearest-neighbor is not used for continuous reflectance in this phase.

## Scale And Offset

The service reads Sentinel product XML metadata when available:

- `BOA_QUANTIFICATION_VALUE`
- `BOA_ADD_OFFSET`

Analysis-ready reflectance is written as:

```text
(digital_number + offset) / quantification_value
```

If product metadata is absent, the service records identity scaling in provenance instead of silently pretending metadata was verified.

## Nodata And Valid Mask

Nodata is preserved explicitly:

- output bands are `float32`
- output nodata value is `-9999`
- source nodata, masked pixels, NaN, infinity, and impossible reflectance values are invalid
- invalid pixels are not converted to zero

The service writes `valid_mask.tif` where:

- `1` means valid for future calculations
- `0` means invalid or missing

Cloud, shadow, snow, and cirrus masking are not implemented in Part 6D-1.

## Storage

Generated outputs are stored under:

```text
SENTINEL_PROCESSING_DIR/<product_id>/<region_id>/
  red.tif
  nir.tif
  swir.tif
  valid_mask.tif
  analysis_ready_manifest.json
```

`backend/artifacts/` is ignored by Git. Raw arrays are not stored in PostgreSQL.

## Caching And Idempotency

Processing is idempotent for the same scene, region, and processing outputs. If a completed manifest and output rasters already exist, the service returns the cached analysis-ready contract instead of regenerating files.

## Provenance

`satellite_images.metadata_json["raster_processing"]` stores processing state and safe metadata. The manifest stores full internal provenance, including output references, for worker/runtime use.

API responses expose status and metadata only; they do not expose internal filesystem paths.

## Background Processing

Celery task:

```text
firesight.prepare_sentinel_raster(region_id, scene_id=None)
```

Public API reads only status:

```text
GET /api/vegetation/satellite/processing-status?region_id=r1
```

Dashboard loads do not trigger raster processing.

## Dependencies

Part 6D-1 uses existing backend dependencies:

- Rasterio/GDAL
- NumPy
- SQLAlchemy

No paid geospatial services are introduced.

## Future Stages

Part 6D-2 can add cloud/shadow/snow/cirrus quality masking on top of these analysis-ready bands.

Part 6D-3/4 can add NDVI/NBR and regional vegetation summaries.
