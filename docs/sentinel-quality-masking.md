# Sentinel-2 Quality Masking

Part 6D-2 adds a quality-mask layer for analysis-ready Sentinel-2 Level-2A raster outputs. It does not calculate NDVI, NBR, EVI, SAVI, vegetation scores, or prediction features.

## Source Layer

Quality masking uses the Sentinel-2 Level-2A Scene Classification Layer (SCL) from the acquired SAFE product or SAFE zip. The service discovers `SCL` rasters, prefers 20 m SCL when present, and resamples categorical classes onto the existing 20 m analysis grid with nearest-neighbor resampling.

The official SCL classes used by the mask are:

| Class | Label | Mask behavior |
| --- | --- | --- |
| 0 | NO_DATA | masked |
| 1 | SATURATED_OR_DEFECTIVE | masked |
| 2 | CAST_SHADOWS | masked |
| 3 | CLOUD_SHADOWS | masked |
| 4 | VEGETATION | valid |
| 5 | NOT_VEGETATED | valid |
| 6 | WATER | masked |
| 7 | UNCLASSIFIED | masked |
| 8 | CLOUD_MEDIUM_PROBABILITY | masked |
| 9 | CLOUD_HIGH_PROBABILITY | masked |
| 10 | THIN_CIRRUS | masked |
| 11 | SNOW_OR_ICE | masked |

## Outputs

The worker writes these files beside the Part 6D-1 analysis-ready rasters:

- `quality_mask.tif`: `uint8` clean-pixel mask, where `1` means valid and `0` means masked.
- `quality_class_scl.tif`: `uint8` SCL class raster resampled to the analysis grid.
- `quality_manifest.json`: internal provenance, class mapping, statistics, and output paths.

The quality mask is combined with the existing Part 6D-1 `valid_mask.tif`, so nodata or invalid reflectance pixels remain masked even when SCL marks the pixel as vegetation or not-vegetated.

## Status And Statistics

Metadata is stored under `satellite_images.metadata_json["quality_masking"]`. API responses redact internal paths and expose only status, version, processed timestamp, and aggregate percentages.

Available status values:

- `DISCOVERED`: a scene exists, but quality masking has not run.
- `PROCESSING`: quality masking is in progress.
- `READY`: enough valid pixels remain after masking.
- `LOW_QUALITY`: masking succeeded, but valid pixels are below `SENTINEL_MIN_VALID_PIXEL_PERCENT`.
- `FAILED`: masking attempted and failed.
- `UNAVAILABLE`: no acquired scene or no analysis-ready raster inputs are available.

Background task:

```text
firesight.apply_sentinel_quality_mask(region_id, scene_id=None)
```

Status API:

```text
GET /api/vegetation/satellite/quality-status?region_id=r1
```

## Guardrails

- No synthetic or assumed cloud-free masks are generated.
- Missing or unreadable SCL data fails safely.
- Continuous spectral bands are not rewritten by this step.
- Categorical SCL data uses nearest-neighbor resampling only.
- Downstream vegetation indices remain out of scope for Part 6D-2.
