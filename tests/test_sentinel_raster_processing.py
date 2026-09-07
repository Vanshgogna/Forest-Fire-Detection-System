from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import Settings
from backend.database.models import Base, SatelliteImage
from backend.services.environmental_foundation import DataQualityStatus
from backend.services.sentinel_provider import SentinelAcquisitionStatus
from backend.services.sentinel_raster_service import CANONICAL_BANDS, SentinelRasterService, SentinelRasterStatus


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "sentinel_processing_dir": str(tmp_path / "processed"),
        "sentinel_raster_max_memory_mb": 16,
        "sentinel_analysis_resolution": 20,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _write_band(path: Path, band_id: str, resolution: int, crs: str = "EPSG:32643", fill: int = 2000, nodata_pixel: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    eastings, northings = transform("EPSG:4326", crs, [76.629], [11.667])
    width = 80 if resolution == 20 else 160
    height = 80 if resolution == 20 else 160
    transform_affine = from_origin(eastings[0] - (width * resolution / 2), northings[0] + (height * resolution / 2), resolution, resolution)
    data = np.full((height, width), fill, dtype="uint16")
    if nodata_pixel:
        data[:20, :20] = 0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint16",
        crs=crs,
        transform=transform_affine,
        nodata=0,
    ) as dataset:
        dataset.write(data, 1)
        dataset.update_tags(1, BAND_ID=band_id, TEST_FIXTURE="true")


def _metadata_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<n1:Level-2A_User_Product xmlns:n1="https://psd-14.sentinel2.eo.esa.int/PSD/User_Product_Level-2A.xsd">
  <General_Info>
    <Product_Image_Characteristics>
      <BOA_QUANTIFICATION_VALUE>10000</BOA_QUANTIFICATION_VALUE>
      <BOA_ADD_OFFSET_VALUES_LIST>
        <BOA_ADD_OFFSET band_id="3">-1000</BOA_ADD_OFFSET>
        <BOA_ADD_OFFSET band_id="7">-1000</BOA_ADD_OFFSET>
        <BOA_ADD_OFFSET band_id="11">-1000</BOA_ADD_OFFSET>
      </BOA_ADD_OFFSET_VALUES_LIST>
    </Product_Image_Characteristics>
  </General_Info>
</n1:Level-2A_User_Product>
"""


def _safe_product(tmp_path: Path, *, missing: str | None = None, swir_crs: str = "EPSG:32643", corrupt: bool = False) -> Path:
    root = tmp_path / "TEST_SENTINEL_L2A.SAFE"
    (root / "GRANULE" / "TEST" / "IMG_DATA" / "R10m").mkdir(parents=True, exist_ok=True)
    (root / "GRANULE" / "TEST" / "IMG_DATA" / "R20m").mkdir(parents=True, exist_ok=True)
    (root / "MTD_MSIL2A.xml").write_text(_metadata_xml())
    if missing != "RED":
        _write_band(root / "GRANULE" / "TEST" / "IMG_DATA" / "R10m" / "TEST_B04_10m.tif", "B04", 10, fill=2000, nodata_pixel=True)
    if missing != "NIR":
        _write_band(root / "GRANULE" / "TEST" / "IMG_DATA" / "R10m" / "TEST_B08_10m.tif", "B08", 10, fill=3000)
    if missing != "SWIR":
        if corrupt:
            swir_path = root / "GRANULE" / "TEST" / "IMG_DATA" / "R20m" / "TEST_B11_20m.tif"
            swir_path.write_text("not a raster")
        else:
            _write_band(root / "GRANULE" / "TEST" / "IMG_DATA" / "R20m" / "TEST_B11_20m.tif", "B11", 20, crs=swir_crs, fill=4000)
    return root


def _zip_product(product_dir: Path) -> Path:
    archive_path = product_dir.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in product_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(product_dir.parent))
    return archive_path


def _scene(db, storage_reference: Path, **overrides) -> SatelliteImage:
    values = {
        "region_id": 1,
        "source": "Sentinel-2",
        "scene_id": "TEST_SENTINEL_L2A.SAFE",
        "provider": "sentinel-2",
        "product_id": "product-1",
        "platform": "S2A",
        "product_level": "L2A",
        "captured_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "retrieved_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "storage_reference": str(storage_reference),
        "file_url": str(storage_reference),
        "cloud_percentage": 5,
        "quality_status": DataQualityStatus.LIVE.value,
        "acquisition_status": SentinelAcquisitionStatus.VERIFIED,
        "metadata_json": {"source_type": "copernicus_odata_products"},
    }
    values.update(overrides)
    scene = SatelliteImage(**values)
    db.add(scene)
    db.commit()
    return scene


def test_sentinel_raster_prepares_analysis_ready_red_nir_swir_outputs(tmp_path):
    db = _session()
    product = _safe_product(tmp_path)
    _scene(db, product)

    result = SentinelRasterService(db, settings=_settings(tmp_path)).prepare_analysis_ready_bands("r1")

    assert result.ok is True
    analysis = result.analysis_ready
    assert analysis is not None
    assert sorted(analysis.bands) == ["NIR", "RED", "SWIR"]
    assert analysis.analysis_crs == "EPSG:32643"
    assert analysis.resolution == (20.0, 20.0)
    assert analysis.width == 80
    assert analysis.height == 80
    assert analysis.provenance["resampling_method"] == "bilinear_for_continuous_reflectance"
    assert analysis.provenance["cloud_shadow_masking"] == "not_implemented_in_part_6d_1"
    for output in analysis.output_references.values():
        with rasterio.open(output) as dataset:
            assert dataset.crs.to_string() == "EPSG:32643"
            assert dataset.width == 80
            assert dataset.height == 80
            assert dataset.nodata == -9999.0
            assert dataset.read(1).dtype == np.float32


def test_sentinel_raster_applies_scale_offset_and_valid_mask_without_ndvi(tmp_path):
    db = _session()
    product = _safe_product(tmp_path)
    _scene(db, product)

    analysis = SentinelRasterService(db, settings=_settings(tmp_path)).prepare_analysis_ready_bands("r1").analysis_ready

    with rasterio.open(analysis.output_references["RED"]) as red:
        data = red.read(1)
    with rasterio.open(analysis.valid_mask_reference) as mask:
        valid_mask = mask.read(1)
    assert np.isclose(float(data[10, 10]), 0.1)
    assert -9999.0 in data
    assert 0 in valid_mask
    assert valid_mask[10, 10] == 1
    assert "ndvi" not in analysis.output_references
    assert "nbr" not in analysis.output_references


def test_sentinel_raster_discovers_bands_from_zipped_safe_product(tmp_path):
    db = _session()
    product = _safe_product(tmp_path)
    archive = _zip_product(product)
    _scene(db, archive)

    result = SentinelRasterService(db, settings=_settings(tmp_path)).prepare_analysis_ready_bands("r1")

    assert result.ok is True
    assert set(result.analysis_ready.provenance["source_band_identifiers"].values()) == {"B04", "B08", "B11"}


def test_sentinel_raster_missing_required_bands_fail_safely(tmp_path):
    for missing in CANONICAL_BANDS:
        db = _session()
        product = _safe_product(tmp_path / missing, missing=missing)
        _scene(db, product, product_id=f"product-{missing}")

        result = SentinelRasterService(db, settings=_settings(tmp_path / missing)).prepare_analysis_ready_bands("r1")

        assert result.status == SentinelRasterStatus.FAILED
        assert result.error is not None
        assert missing in result.error.message


def test_sentinel_raster_rejects_incompatible_crs(tmp_path):
    db = _session()
    product = _safe_product(tmp_path, swir_crs="EPSG:4326")
    _scene(db, product)

    result = SentinelRasterService(db, settings=_settings(tmp_path)).prepare_analysis_ready_bands("r1")

    assert result.status == SentinelRasterStatus.FAILED
    assert result.error is not None
    assert "CRS" in result.error.message


def test_sentinel_raster_rejects_missing_scene_file_and_unsupported_product(tmp_path):
    missing_db = _session()
    _scene(missing_db, tmp_path / "missing.zip")
    unsupported_db = _session()
    _scene(unsupported_db, _safe_product(tmp_path / "l1c"), product_level="L1C", product_id="l1c-product")

    missing = SentinelRasterService(missing_db, settings=_settings(tmp_path)).prepare_analysis_ready_bands("r1")
    unsupported = SentinelRasterService(unsupported_db, settings=_settings(tmp_path / "l1c")).prepare_analysis_ready_bands("r1")

    assert missing.status == SentinelRasterStatus.FAILED
    assert missing.error is not None
    assert "missing" in missing.error.message.lower()
    assert unsupported.status == SentinelRasterStatus.FAILED
    assert "Level-2A" in unsupported.error.message


def test_sentinel_raster_rejects_corrupt_raster(tmp_path):
    db = _session()
    product = _safe_product(tmp_path, corrupt=True)
    _scene(db, product)

    result = SentinelRasterService(db, settings=_settings(tmp_path)).prepare_analysis_ready_bands("r1")

    assert result.status == SentinelRasterStatus.FAILED
    assert result.error is not None
    assert "Unable to read Sentinel band B11" in result.error.message


def test_sentinel_raster_processing_is_idempotent_and_updates_status(tmp_path):
    db = _session()
    product = _safe_product(tmp_path)
    scene = _scene(db, product)
    service = SentinelRasterService(db, settings=_settings(tmp_path))

    first = service.prepare_analysis_ready_bands("r1")
    second = service.prepare_analysis_ready_bands("r1")
    status = service.processing_status("r1")
    db.refresh(scene)

    assert first.ok is True
    assert second.ok is True
    assert second.analysis_ready.output_references == first.analysis_ready.output_references
    assert second.analysis_ready.processing_started_at == first.analysis_ready.processing_started_at
    assert scene.processing_time is not None
    assert scene.metadata_json["raster_processing"]["status"] == SentinelRasterStatus.READY
    assert status["processing_status"] == SentinelRasterStatus.READY
    assert status["available_bands"] == ["NIR", "RED", "SWIR"]


def test_sentinel_raster_memory_guard_prevents_oversized_crop(tmp_path):
    db = _session()
    product = _safe_product(tmp_path)
    _scene(db, product)

    result = SentinelRasterService(db, settings=_settings(tmp_path, sentinel_raster_max_memory_mb=0.0001)).prepare_analysis_ready_bands("r1")

    assert result.status == SentinelRasterStatus.FAILED
    assert result.error is not None
    assert "SENTINEL_RASTER_MAX_MEMORY_MB" in result.error.message
