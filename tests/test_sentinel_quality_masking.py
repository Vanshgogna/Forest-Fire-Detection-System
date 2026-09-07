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
from backend.services.sentinel_quality_mask_service import SCL_CLASSES, SentinelQualityMaskService, SentinelQualityMaskStatus
from backend.services.sentinel_raster_service import SentinelRasterService


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "sentinel_processing_dir": str(tmp_path / "processed"),
        "sentinel_raster_max_memory_mb": 16,
        "sentinel_analysis_resolution": 20,
        "sentinel_min_valid_pixel_percent": 40,
        "sentinel_quality_mask_version": "test-mask-v1",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _grid(resolution: int, crs: str = "EPSG:32643") -> tuple[int, int, object]:
    eastings, northings = transform("EPSG:4326", crs, [76.629], [11.667])
    width = 80 if resolution == 20 else 160 if resolution == 10 else 40
    height = 80 if resolution == 20 else 160 if resolution == 10 else 40
    transform_affine = from_origin(eastings[0] - (width * resolution / 2), northings[0] + (height * resolution / 2), resolution, resolution)
    return width, height, transform_affine


def _write_band(path: Path, band_id: str, resolution: int, fill: int = 2000, nodata_pixel: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height, transform_affine = _grid(resolution)
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
        crs="EPSG:32643",
        transform=transform_affine,
        nodata=0,
    ) as dataset:
        dataset.write(data, 1)
        dataset.update_tags(1, BAND_ID=band_id, TEST_FIXTURE="true")


def _write_scl(path: Path, classes: np.ndarray, resolution: int = 20):
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height, transform_affine = _grid(resolution)
    if classes.shape != (height, width):
        classes = np.resize(classes, (height, width))
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs="EPSG:32643",
        transform=transform_affine,
        nodata=0,
    ) as dataset:
        dataset.write(classes.astype("uint8"), 1)
        dataset.update_tags(1, BAND_ID="SCL", TEST_FIXTURE="true")


def _metadata_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<n1:Level-2A_User_Product xmlns:n1="https://psd-14.sentinel2.eo.esa.int/PSD/User_Product_Level-2A.xsd">
  <General_Info>
    <Product_Image_Characteristics>
      <BOA_QUANTIFICATION_VALUE>10000</BOA_QUANTIFICATION_VALUE>
    </Product_Image_Characteristics>
  </General_Info>
</n1:Level-2A_User_Product>
"""


def _safe_product(tmp_path: Path, *, scl: np.ndarray | None = None, scl_resolution: int = 20, missing_scl: bool = False, corrupt_scl: bool = False) -> Path:
    root = tmp_path / "TEST_SENTINEL_L2A.SAFE"
    r10m = root / "GRANULE" / "TEST" / "IMG_DATA" / "R10m"
    r20m = root / "GRANULE" / "TEST" / "IMG_DATA" / "R20m"
    r10m.mkdir(parents=True, exist_ok=True)
    r20m.mkdir(parents=True, exist_ok=True)
    (root / "MTD_MSIL2A.xml").write_text(_metadata_xml())
    _write_band(r10m / "TEST_B04_10m.tif", "B04", 10, fill=2000, nodata_pixel=True)
    _write_band(r10m / "TEST_B08_10m.tif", "B08", 10, fill=3000)
    _write_band(r20m / "TEST_B11_20m.tif", "B11", 20, fill=4000)
    if not missing_scl:
        scl_name = f"TEST_SCL_{scl_resolution}m.tif" if scl_resolution in {10, 20, 60} else "TEST_SCL.tif"
        scl_path = root / "GRANULE" / "TEST" / "IMG_DATA" / f"R{scl_resolution}m" / scl_name
        if corrupt_scl:
            scl_path.parent.mkdir(parents=True, exist_ok=True)
            scl_path.write_text("not a raster")
        else:
            _write_scl(scl_path, scl if scl is not None else np.full((80, 80), 4, dtype="uint8"), resolution=scl_resolution)
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


def _prepare(db, settings: Settings):
    raster_result = SentinelRasterService(db, settings=settings).prepare_analysis_ready_bands("r1")
    assert raster_result.ok is True
    return raster_result


def test_sentinel_quality_mask_uses_official_scl_class_mapping():
    assert SCL_CLASSES[0]["label"] == "NO_DATA"
    assert SCL_CLASSES[2]["label"] == "CAST_SHADOWS"
    assert SCL_CLASSES[3]["label"] == "CLOUD_SHADOWS"
    assert SCL_CLASSES[4]["valid"] is True
    assert SCL_CLASSES[5]["valid"] is True
    assert SCL_CLASSES[8]["category"] == "cloud"
    assert SCL_CLASSES[9]["category"] == "cloud"
    assert SCL_CLASSES[10]["category"] == "cirrus"
    assert SCL_CLASSES[11]["category"] == "snow"


def test_sentinel_quality_mask_generates_clean_mask_and_statistics(tmp_path):
    db = _session()
    scl = np.full((80, 80), 4, dtype="uint8")
    scl[0:10, 0:10] = 8
    scl[10:20, 0:10] = 9
    scl[20:30, 0:10] = 3
    scl[30:40, 0:10] = 2
    scl[40:50, 0:10] = 10
    scl[50:60, 0:10] = 11
    scl[60:70, 0:10] = 7
    scl[70:80, 0:10] = 6
    product = _safe_product(tmp_path, scl=scl)
    _scene(db, product)
    settings = _settings(tmp_path)
    _prepare(db, settings)

    result = SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")

    assert result.ok is True
    assert result.status == SentinelQualityMaskStatus.READY
    assert result.mask is not None
    assert result.mask.stats.cloud_pixels == 200
    assert result.mask.stats.shadow_pixels == 200
    assert result.mask.stats.cirrus_pixels == 100
    assert result.mask.stats.snow_pixels == 100
    with rasterio.open(result.mask.quality_mask_reference) as dataset:
        mask = dataset.read(1)
    assert mask[5, 5] == 0
    assert mask[75, 75] == 1
    assert result.mask.provenance["downstream_indices"] == "not_implemented_in_part_6d_2"


def test_sentinel_quality_mask_combines_scl_with_analysis_valid_mask(tmp_path):
    db = _session()
    product = _safe_product(tmp_path, scl=np.full((80, 80), 4, dtype="uint8"))
    _scene(db, product)
    settings = _settings(tmp_path)
    raster_result = _prepare(db, settings)
    with rasterio.open(raster_result.analysis_ready.valid_mask_reference, "r+") as dataset:
        valid_mask = dataset.read(1)
        valid_mask[:20, :20] = 0
        dataset.write(valid_mask, 1)

    result = SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")

    assert result.ok is True
    with rasterio.open(result.mask.quality_mask_reference) as dataset:
        mask = dataset.read(1)
    assert mask[10, 10] == 0
    assert mask[30, 30] == 1


def test_sentinel_quality_mask_supports_zipped_safe_product(tmp_path):
    db = _session()
    product = _safe_product(tmp_path, scl=np.full((80, 80), 5, dtype="uint8"))
    archive = _zip_product(product)
    _scene(db, archive)
    settings = _settings(tmp_path)
    _prepare(db, settings)

    result = SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")

    assert result.ok is True
    assert result.mask.quality_layer.source_identifier == "SCL"


def test_sentinel_quality_mask_uses_nearest_resampling_for_categorical_scl(tmp_path):
    db = _session()
    coarse = np.zeros((40, 40), dtype="uint8")
    coarse[:, :20] = 4
    coarse[:, 20:] = 9
    product = _safe_product(tmp_path, scl=coarse, scl_resolution=40)
    _scene(db, product)
    settings = _settings(tmp_path)
    _prepare(db, settings)

    result = SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")

    assert result.ok is True
    with rasterio.open(result.mask.quality_class_reference) as dataset:
        classes = dataset.read(1)
    assert set(np.unique(classes)).issubset({4, 9})


def test_sentinel_quality_mask_rejects_missing_and_corrupt_scl_without_fake_mask(tmp_path):
    missing_db = _session()
    _scene(missing_db, _safe_product(tmp_path / "missing", missing_scl=True))
    missing_settings = _settings(tmp_path / "missing")
    _prepare(missing_db, missing_settings)

    corrupt_db = _session()
    _scene(corrupt_db, _safe_product(tmp_path / "corrupt", corrupt_scl=True), product_id="corrupt-product")
    corrupt_settings = _settings(tmp_path / "corrupt")
    _prepare(corrupt_db, corrupt_settings)

    missing = SentinelQualityMaskService(missing_db, settings=missing_settings).apply_quality_mask("r1")
    corrupt = SentinelQualityMaskService(corrupt_db, settings=corrupt_settings).apply_quality_mask("r1")

    assert missing.status == SentinelQualityMaskStatus.FAILED
    assert "SCL" in missing.error.message
    assert corrupt.status == SentinelQualityMaskStatus.FAILED
    assert "Unable to read Sentinel-2 SCL" in corrupt.error.message


def test_sentinel_quality_mask_requires_analysis_ready_rasters(tmp_path):
    db = _session()
    _scene(db, _safe_product(tmp_path))

    result = SentinelQualityMaskService(db, settings=_settings(tmp_path)).apply_quality_mask("r1")

    assert result.status == SentinelQualityMaskStatus.UNAVAILABLE
    assert result.error is not None
    assert "raster preparation" in result.error.message


def test_sentinel_quality_mask_detects_low_valid_pixel_percentage(tmp_path):
    db = _session()
    scl = np.full((80, 80), 9, dtype="uint8")
    scl[0:10, 0:10] = 4
    product = _safe_product(tmp_path, scl=scl)
    scene = _scene(db, product)
    settings = _settings(tmp_path, sentinel_min_valid_pixel_percent=40)
    _prepare(db, settings)

    result = SentinelQualityMaskService(db, settings=settings).apply_quality_mask("r1")
    db.refresh(scene)

    assert result.status == SentinelQualityMaskStatus.LOW_QUALITY
    assert result.quality_status == DataQualityStatus.SUSPICIOUS
    assert scene.metadata_json["quality_masking"]["status"] == SentinelQualityMaskStatus.LOW_QUALITY


def test_sentinel_quality_mask_is_idempotent_and_exposes_safe_status(tmp_path):
    db = _session()
    product = _safe_product(tmp_path, scl=np.full((80, 80), 4, dtype="uint8"))
    _scene(db, product)
    settings = _settings(tmp_path)
    _prepare(db, settings)
    service = SentinelQualityMaskService(db, settings=settings)

    first = service.apply_quality_mask("r1")
    second = service.apply_quality_mask("r1")
    status = service.quality_status("r1")

    assert first.ok is True
    assert second.ok is True
    assert second.mask.quality_mask_reference == first.mask.quality_mask_reference
    assert second.mask.processing_started_at == first.mask.processing_started_at
    assert status["processing_status"] == SentinelQualityMaskStatus.READY
    assert status["available"] is True
    assert "quality_mask_path" not in status
