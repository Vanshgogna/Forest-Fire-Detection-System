from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.transform import from_origin

from backend.database.models import VegetationRecord
from backend.services.environmental_data_service import EnvironmentalDataService
from backend.services.environmental_foundation import DataMode, DataQualityStatus
from backend.services.sentinel_ndvi_service import NDVI_REQUIRED_BANDS, NDVI_OUTPUT_NODATA, SentinelNDVIService, SentinelNDVIStatus
from backend.services.sentinel_provider import SentinelDownloadResult, SentinelProvider, SentinelSceneCandidate
from backend.services.sentinel_quality_mask_service import SentinelQualityMaskService
from backend.services.sentinel_raster_service import SentinelRasterService
from test_sentinel_quality_masking import _safe_product, _scene, _session, _settings, _write_band


def _prepare_pipeline(tmp_path: Path, *, scl: np.ndarray | None = None, settings_overrides: dict | None = None):
    db = _session()
    product = _safe_product(tmp_path, scl=scl if scl is not None else np.full((80, 80), 4, dtype="uint8"))
    scene = _scene(db, product)
    settings = _settings(tmp_path, **(settings_overrides or {}))
    raster = SentinelRasterService(db, settings=settings).prepare_analysis_ready_bands("r1")
    assert raster.ok is True
    quality = SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")
    assert quality.ok is True
    return db, scene, settings, raster, quality


def _rewrite_raster(path: str, data: np.ndarray):
    with rasterio.open(path, "r+") as dataset:
        dataset.write(data.astype(dataset.dtypes[0]), 1)


def _process_api_tiff(red_value: float = 0.2, nir_value: float = 0.6, swir2_value: float = 0.3, scl_value: float = 4, data_mask_value: float = 1) -> bytes:
    profile = {
        "driver": "GTiff",
        "height": 12,
        "width": 12,
        "count": 5,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(76.129, 12.167, 0.01, 0.01),
    }
    with MemoryFile() as memory_file:
        with memory_file.open(**profile) as dataset:
            dataset.write(np.full((12, 12), red_value, dtype="float32"), 1)
            dataset.write(np.full((12, 12), nir_value, dtype="float32"), 2)
            dataset.write(np.full((12, 12), swir2_value, dtype="float32"), 3)
            dataset.write(np.full((12, 12), scl_value, dtype="float32"), 4)
            dataset.write(np.full((12, 12), data_mask_value, dtype="float32"), 5)
        return memory_file.read()


def test_sentinel_ndvi_formula_uses_b04_red_and_b08_nir(tmp_path):
    product = _safe_product(tmp_path, scl=np.full((80, 80), 4, dtype="uint8"))
    _write_band(product / "GRANULE" / "TEST" / "IMG_DATA" / "R10m" / "TEST_B04_10m.tif", "B04", 10, fill=2000)
    _write_band(product / "GRANULE" / "TEST" / "IMG_DATA" / "R10m" / "TEST_B08_10m.tif", "B08", 10, fill=6000)
    db = _session()
    _scene(db, product)
    settings = _settings(tmp_path)
    SentinelRasterService(db, settings=settings).prepare_analysis_ready_bands("r1")
    SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.ok is True
    assert NDVI_REQUIRED_BANDS == {"RED": "B04", "NIR": "B08"}
    assert result.summary is not None
    assert np.isclose(result.summary.stats.mean, 0.5, atol=0.001)
    assert result.summary.provenance["formula"] == "(NIR - RED) / (NIR + RED)"
    assert result.summary.provenance["input_reflectance"].startswith("Part 6D-1 physical surface reflectance")


def test_sentinel_ndvi_writes_float32_output_and_mask(tmp_path):
    db, _, settings, _, _ = _prepare_pipeline(tmp_path)

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.ok is True
    with rasterio.open(result.summary.ndvi_reference) as ndvi, rasterio.open(result.summary.ndvi_valid_mask_reference) as mask:
        assert ndvi.dtypes[0] == "float32"
        assert ndvi.nodata == NDVI_OUTPUT_NODATA
        assert mask.dtypes[0] == "uint8"
        assert ndvi.crs == mask.crs
        assert ndvi.transform == mask.transform
        assert ndvi.width == mask.width == 80
        assert ndvi.height == mask.height == 80


def test_sentinel_ndvi_excludes_zero_denominator_and_nodata(tmp_path):
    db, _, settings, raster, _ = _prepare_pipeline(tmp_path)
    red_path = raster.analysis_ready.output_references["RED"]
    nir_path = raster.analysis_ready.output_references["NIR"]
    with rasterio.open(red_path) as red:
        red_data = red.read(1)
    with rasterio.open(nir_path) as nir:
        nir_data = nir.read(1)
    red_data[2, 2] = 0
    nir_data[2, 2] = 0
    red_data[3, 3] = NDVI_OUTPUT_NODATA
    _rewrite_raster(red_path, red_data)
    _rewrite_raster(nir_path, nir_data)

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.ok is True
    with rasterio.open(result.summary.ndvi_reference) as ndvi, rasterio.open(result.summary.ndvi_valid_mask_reference) as mask:
        assert ndvi.read(1)[2, 2] == NDVI_OUTPUT_NODATA
        assert mask.read(1)[2, 2] == 0
        assert mask.read(1)[3, 3] == 0


def test_sentinel_ndvi_respects_quality_mask(tmp_path):
    scl = np.full((80, 80), 4, dtype="uint8")
    scl[20:30, 20:30] = 9
    db, _, settings, _, _ = _prepare_pipeline(tmp_path, scl=scl)

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.ok is True
    with rasterio.open(result.summary.ndvi_valid_mask_reference) as mask:
        data = mask.read(1)
    assert data[25, 25] == 0
    assert data[40, 40] == 1


def test_sentinel_ndvi_excludes_nan_infinity_and_out_of_range_values(tmp_path):
    db, _, settings, raster, _ = _prepare_pipeline(tmp_path)
    red_path = raster.analysis_ready.output_references["RED"]
    nir_path = raster.analysis_ready.output_references["NIR"]
    with rasterio.open(red_path) as red:
        red_data = red.read(1)
    with rasterio.open(nir_path) as nir:
        nir_data = nir.read(1)
    red_data[4, 4] = np.nan
    nir_data[5, 5] = np.inf
    red_data[6, 6] = -10
    nir_data[6, 6] = 0.1
    _rewrite_raster(red_path, red_data)
    _rewrite_raster(nir_path, nir_data)

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.ok is True
    with rasterio.open(result.summary.ndvi_valid_mask_reference) as mask:
        data = mask.read(1)
    assert data[4, 4] == 0
    assert data[5, 5] == 0
    assert data[6, 6] == 0


def test_sentinel_ndvi_rejects_alignment_mismatch(tmp_path):
    db, _, settings, _, quality = _prepare_pipeline(tmp_path)
    with rasterio.open(quality.mask.quality_mask_reference, "r+") as dataset:
        dataset.transform = dataset.transform * Affine.translation(1, 0)

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.status == SentinelNDVIStatus.FAILED
    assert result.error is not None
    assert "transform" in result.error.message


def test_sentinel_ndvi_statistics_percentiles_and_low_quality(tmp_path):
    scl = np.full((80, 80), 9, dtype="uint8")
    scl[:12, :12] = 4
    db, scene, settings, _, _ = _prepare_pipeline(tmp_path, scl=scl, settings_overrides={"sentinel_min_valid_pixel_percent": 40})

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")
    db.refresh(scene)

    assert result.status == SentinelNDVIStatus.LOW_QUALITY
    assert result.quality_status == DataQualityStatus.SUSPICIOUS
    assert result.summary.stats.valid_pixel_percentage < 40
    assert result.summary.stats.percentiles["p50"] is not None
    assert scene.metadata_json["ndvi_processing"]["status"] == SentinelNDVIStatus.LOW_QUALITY


def test_low_quality_sentinel_ndvi_status_is_available_with_suspicious_quality(tmp_path):
    scl = np.full((80, 80), 9, dtype="uint8")
    scl[:12, :12] = 4
    db, _, settings, _, _ = _prepare_pipeline(tmp_path, scl=scl, settings_overrides={"sentinel_min_valid_pixel_percent": 40})
    SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    status = SentinelNDVIService(db, settings=settings).ndvi_status("r1")

    assert status["processing_status"] == SentinelNDVIStatus.LOW_QUALITY
    assert status["quality_status"] == DataQualityStatus.SUSPICIOUS.value
    assert status["available"] is True
    assert status["mean"] is not None


def test_sentinel_ndvi_is_idempotent_and_persists_vegetation_record(tmp_path):
    db, _, settings, _, _ = _prepare_pipeline(tmp_path)
    service = SentinelNDVIService(db, settings=settings)

    first = service.calculate_ndvi("r1")
    second = service.calculate_ndvi("r1")
    records = db.query(VegetationRecord).all()

    assert first.ok is True
    assert second.ok is True
    assert second.summary.ndvi_reference == first.summary.ndvi_reference
    assert second.summary.processed_at == first.summary.processed_at
    assert len(records) == 1
    assert records[0].nbr is None
    assert records[0].vegetation_health_index is None
    assert records[0].provenance_metadata["red_band"] == "B04"
    assert "statistics" in records[0].provenance_metadata


def test_sentinel_ndvi_status_redacts_filesystem_paths(tmp_path):
    db, _, settings, _, _ = _prepare_pipeline(tmp_path)
    SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    status = SentinelNDVIService(db, settings=settings).ndvi_status("r1")

    assert status["processing_status"] == SentinelNDVIStatus.READY
    assert status["available"] is True
    assert status["mean"] is not None
    assert "ndvi_path" not in status
    assert "manifest_path" not in status


def test_sentinel_ndvi_uses_process_api_without_odata_product_download(tmp_path, monkeypatch):
    db = _session()
    settings = _settings(
        tmp_path,
        sentinel_enabled=True,
        copernicus_client_id="client-id",
        copernicus_client_secret="client-secret",
        sentinel_ndvi_processing_version="test-process-v1",
    )
    captured_at = datetime(2026, 8, 30, 5, 6, tzinfo=timezone.utc)
    candidate = SentinelSceneCandidate(
        region_id="r1",
        database_region_id=1,
        product_id="process-product-1",
        name="S2B_MSIL2A_20260830T050649_N0512_R019_T43PGN_20260830T085227.SAFE",
        captured_at=captured_at,
        retrieved_at=datetime.now(timezone.utc),
        cloud_percentage=12.5,
        platform="S2B",
        product_level="L2A",
        product_type="S2MSI2A",
        tile_id="43PGN",
        source_url="https://catalogue.example/odata/v1/Products?...",
    )

    class SearchResult:
        error = None
        selected_scene = candidate

    download_called = False
    captured_payload = {}

    def fail_download(self, scene, destination_root=None) -> SentinelDownloadResult:
        nonlocal download_called
        download_called = True
        raise AssertionError("OData product download must not be used for Process API NDVI")

    def process_api_response(self, token, payload):
        captured_payload.update(payload)
        return httpx.Response(200, content=_process_api_tiff())

    monkeypatch.setattr(SentinelProvider, "_access_token", lambda self: "token")
    monkeypatch.setattr(SentinelProvider, "search_scenes", lambda self, region_id: SearchResult())
    monkeypatch.setattr(SentinelProvider, "download_scene", fail_download)
    monkeypatch.setattr(SentinelNDVIService, "_process_api_request", process_api_response)

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")
    records = db.query(VegetationRecord).all()

    assert result.ok is True
    assert download_called is False
    assert np.isclose(result.summary.stats.mean, 0.5, atol=0.001)
    assert np.isclose(result.summary.nbr_stats.mean, (0.6 - 0.3) / (0.6 + 0.3), atol=0.001)
    assert result.summary.provenance["source_api"] == "sentinel_hub_process_api"
    assert result.summary.provenance["nbr_formula"] == "(B08 - B12) / (B08 + B12)"
    assert result.summary.provenance["swir2_band"] == "B12"
    assert result.summary.provenance["input_reflectance"].endswith("no full OData product download")
    assert "B12" in captured_payload["evalscript"]
    assert len(records) == 1
    assert records[0].ndvi == result.summary.stats.mean
    assert records[0].nbr == result.summary.nbr_stats.mean
    assert records[0].provider == "sentinel-2"


def test_process_api_nbr_masks_zero_denominator_and_invalid_pixels(tmp_path, monkeypatch):
    db = _session()
    settings = _settings(
        tmp_path,
        sentinel_enabled=True,
        copernicus_client_id="client-id",
        copernicus_client_secret="client-secret",
        sentinel_ndvi_processing_version="test-process-nbr-v1",
    )
    candidate = SentinelSceneCandidate(
        region_id="r1",
        database_region_id=1,
        product_id="process-product-nbr",
        name="S2B_MSIL2A_PROCESS_NBR.SAFE",
        captured_at=datetime(2026, 8, 30, 5, 6, tzinfo=timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        cloud_percentage=12.5,
        platform="S2B",
        product_level="L2A",
        product_type="S2MSI2A",
        tile_id="43PGN",
    )

    class SearchResult:
        error = None
        selected_scene = candidate

    profile = {
        "driver": "GTiff",
        "height": 6,
        "width": 6,
        "count": 5,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(76.129, 12.167, 0.01, 0.01),
    }
    red = np.full((6, 6), 0.2, dtype="float32")
    nir = np.full((6, 6), 0.6, dtype="float32")
    swir2 = np.full((6, 6), 0.3, dtype="float32")
    scl = np.full((6, 6), 4, dtype="float32")
    data_mask = np.full((6, 6), 1, dtype="float32")
    nir[0, 0] = 0
    swir2[0, 0] = 0
    swir2[1, 1] = np.nan
    scl[2, 2] = 9
    data_mask[3, 3] = 0
    with MemoryFile() as memory_file:
        with memory_file.open(**profile) as dataset:
            for index, band in enumerate([red, nir, swir2, scl, data_mask], start=1):
                dataset.write(band, index)
        content = memory_file.read()

    monkeypatch.setattr(SentinelProvider, "_access_token", lambda self: "token")
    monkeypatch.setattr(SentinelProvider, "search_scenes", lambda self, region_id: SearchResult())
    monkeypatch.setattr(SentinelNDVIService, "_process_api_request", lambda self, token, payload: httpx.Response(200, content=content))

    result = SentinelNDVIService(db, settings=settings).calculate_ndvi("r1")

    assert result.ok is True
    with rasterio.open(result.summary.nbr_valid_mask_reference) as mask:
        mask_data = mask.read(1)
    assert mask_data[0, 0] == 0
    assert mask_data[1, 1] == 0
    assert mask_data[2, 2] == 0
    assert mask_data[3, 3] == 0
    assert mask_data[4, 4] == 1


def test_sentinel_ndvi_missing_prerequisites_and_corrupt_input_fail_safely(tmp_path):
    db = _session()
    _scene(db, _safe_product(tmp_path))
    unavailable = SentinelNDVIService(db, settings=_settings(tmp_path)).calculate_ndvi("r1")
    assert unavailable.status == SentinelNDVIStatus.UNAVAILABLE

    corrupt_db, _, corrupt_settings, raster, _ = _prepare_pipeline(tmp_path / "corrupt")
    Path(raster.analysis_ready.output_references["RED"]).write_text("not a raster")
    corrupt = SentinelNDVIService(corrupt_db, settings=corrupt_settings).calculate_ndvi("r1")
    assert corrupt.status == SentinelNDVIStatus.FAILED


def test_live_mode_does_not_return_mock_ndvi_without_processed_record(tmp_path, monkeypatch):
    db = _session()

    class SessionFactory:
        def __call__(self):
            return db

    monkeypatch.setattr("backend.services.environmental_data_service.SessionLocal", SessionFactory())
    service = EnvironmentalDataService(settings=_settings(tmp_path, data_mode=DataMode.LIVE.value))

    vegetation = service.get_latest_vegetation("r1")

    assert vegetation.available is False
    assert vegetation.status == DataQualityStatus.UNAVAILABLE
    assert vegetation.values is None
