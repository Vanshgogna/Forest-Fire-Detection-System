# Remote Sensing Pipeline

The remote-sensing pipeline centralizes satellite and GIS operations so raster work is reusable across API routes, background workers, and future data ingestion jobs.

## Pipeline Stages

1. Satellite download manifest
2. Dataset validation
3. Coordinate system inspection
4. Projection conversion plan
5. Windowed raster processing
6. Cloud masking
7. Raster clipping by forest boundary
8. NDVI generation
9. NBR generation
10. Raster normalization
11. GeoJSON generation
12. Heatmap creation
13. Tile cache manifest generation
14. Raster storage manifest generation
15. Temporary file cleanup planning

## Coordinate Systems

- Project API coordinates use `EPSG:4326`.
- Analysis and web visualization plans default to `EPSG:3857`.
- Projection conversion is represented explicitly so background workers can choose the correct Rasterio/GDAL operation.

## Performance Strategy

- Large raster datasets are processed with a windowed strategy.
- Default chunk size is `1024`.
- Tile cache manifests use XYZ tiles and stable cache keys.
- Heavy scientific dependencies are optional at API import time so control-plane endpoints stay available even before worker images are fully provisioned.

## Storage Strategy

Scene outputs are grouped by source and scene ID under `backend/artifacts/rasters` by default. Production deployments should map these manifests to object storage such as Cloudinary, S3, or another managed media store.

## Cleanup

Temporary files are declared through cleanup manifests. Workers should only delete paths returned by `cleanup_plan` where `safe_to_delete` is true.

## API Contracts

### Calculate Vegetation Indices

- Endpoint: `/api/vegetation/indices`
- Method: `POST`
- Authentication: public demo endpoint
- Request body: `nir`, `red`, `swir`, optional `cloud_percentage`
- Validation: reflectance bands must be between `-1` and `1`; cloud percentage must be between `0` and `100`
- Response: `ndvi`, `nbr`, `vegetation_health_index`
- Status codes: `200`, `422`

Example request:

```json
{"nir": 0.72, "red": 0.21, "swir": 0.38, "cloud_percentage": 12}
```

Example response:

```json
{"ndvi": 0.5484, "nbr": 0.3091, "vegetation_health_index": 0.4336}
```

### Build Satellite Scene Plan

- Endpoint: `/api/vegetation/satellite/scene-plan`
- Method: `POST`
- Authentication: public demo endpoint
- Request body: `scene_id`, `source`, `acquisition_date`, `crs`, `cloud_percentage`, optional `storage_uri`, optional `bounds`
- Validation: source must be `Sentinel-2`, `MODIS`, or `VIIRS`; scene ID is required; cloud percentage must be between `0` and `100`
- Response: download, validation, projection, cloud mask, processing, storage, temporary files, and cleanup manifests
- Status codes: `200`, `422`

### GIS Cache Manifest

- Endpoint: `/api/gis/cache-manifest/{layer}`
- Method: `GET`
- Authentication: public demo endpoint
- Request parameters: `layer`, optional `scene_id`
- Response: tile scheme, zoom levels, and deterministic cache key
- Status codes: `200`
