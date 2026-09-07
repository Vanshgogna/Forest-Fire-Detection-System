# Sentinel-2 NDVI Processing

Part 6D-3 calculates real Sentinel-2 NDVI only. It does not calculate NBR, EVI, SAVI, NDMI, vegetation-health scoring, fire-risk scoring, ML features, forecasts, or map tile serving.

## Formula And Bands

NDVI is calculated as:

```text
NDVI = (NIR - RED) / (NIR + RED)
```

For Sentinel-2 this implementation uses:

- RED: `B04`
- NIR: `B08`

`B8A`, `B11`, RGB bands, and any fire-risk features are not used by Part 6D-3.

## Reflectance Handling

Part 6D-3 consumes the Part 6D-1 analysis-ready rasters:

- `red.tif`
- `nir.tif`
- `valid_mask.tif`

Part 6D-1 already applies Sentinel-2 L2A quantification and BOA offset metadata and writes physical surface-reflectance `Float32` rasters. Part 6D-3 validates that the RED/NIR inputs are `Float32` analysis-ready rasters and does not apply `/10000` or any second scaling.

## Quality Mask Dependency

Part 6D-3 also requires the Part 6D-2 output:

- `quality_mask.tif`

The final NDVI mask is:

```text
ndvi_valid_mask =
  valid_mask
  AND quality_mask
  AND finite RED
  AND finite NIR
  AND non-zero denominator
  AND finite NDVI
  AND NDVI range valid
```

This excludes pixels already identified as nodata, clouds, cloud shadows, cirrus, snow/ice, saturated/defective, water, unclassified, or otherwise invalid by the earlier stages.

## Output

The worker writes:

- `ndvi.tif`: `Float32`, same CRS/transform/resolution/width/height as the analysis grid.
- `ndvi_valid_mask.tif`: `uint8`, where `1` means valid NDVI and `0` means invalid.
- `ndvi_manifest.json`: internal provenance, statistics, input references, and processing version.

Nodata is the project raster nodata value, `-9999.0`. Nodata is never treated as valid NDVI, and valid mathematical NDVI values of `-1` remain distinguishable from nodata.

## Validation

Before calculation, the service verifies:

- RED is Sentinel-2 `B04`.
- NIR is Sentinel-2 `B08`.
- Scale/offset provenance exists in the analysis-ready manifest.
- RED, NIR, `valid_mask`, and `quality_mask` share CRS, transform, width, height, and resolution.
- RED/NIR are `Float32` reflectance rasters with the expected nodata convention.

Zero denominator pixels are masked as invalid. NaN and infinity are masked. NDVI values outside `[-1, 1]` beyond a small numerical tolerance are invalid, not clipped into an acceptable range. Tiny floating-point tolerance is only used to handle numerical noise near the mathematical bounds.

## Statistics

Statistics are calculated over valid NDVI pixels only:

- total pixels
- valid pixels
- invalid pixels
- valid pixel percentage
- min
- max
- mean
- median
- standard deviation
- p10, p25, p50, p75, p90

Coverage is reported separately from NDVI values. Low coverage is marked `LOW_QUALITY` when valid pixels fall below `SENTINEL_MIN_VALID_PIXEL_PERCENT`.

## Persistence And Provenance

The canonical regional NDVI mean is stored in `vegetation_records.ndvi`. NBR and vegetation-health index remain `NULL` for Sentinel NDVI records because Part 6D-3 does not implement them.

Detailed reproducibility metadata is stored in:

- `satellite_images.metadata_json["ndvi_processing"]`
- `vegetation_records.provenance_metadata`
- `ndvi_manifest.json`

Provenance includes provider, scene id, product id, region id, acquisition time, processed time, processing version, B04/B08 mapping, analysis CRS/resolution, quality-mask source, valid-pixel coverage, and scale/offset provenance. Credentials and raw developer filesystem paths are not exposed through API responses.

## Background Processing And API

Large NDVI calculation is performed through the background task:

```text
firesight.calculate_sentinel_ndvi(region_id, scene_id=None)
```

Status is available through:

```text
GET /api/vegetation/satellite/ndvi-status?region_id=r1
```

The status endpoint does not trigger raster processing and does not expose raw GeoTIFF paths.

## Caching

Processing is idempotent for:

- region
- scene
- processing version
- existing NDVI manifest/output files

If cached outputs and the manifest are present for the current `SENTINEL_NDVI_PROCESSING_VERSION`, the service reuses them.

## Real-Data Validation

Real-data validation requires an acquired Sentinel-2 L2A scene plus completed 6D-1 raster prep and 6D-2 quality masking. If no real scene is available, deterministic synthetic rasters are used only in tests.

## Limitations

- No NBR or vegetation scoring is implemented.
- No fire-risk or prediction logic is changed.
- No raw raster-serving endpoint is exposed.
- Exact percentiles are computed from valid NDVI values after windowed raster processing; this avoids reading source rasters as whole scenes, but exact percentile calculation still materializes the valid NDVI sample.
