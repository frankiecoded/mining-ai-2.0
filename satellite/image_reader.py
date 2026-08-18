"""Adapter: bridges main.py satellite image endpoints to services/satellite_image_reader.py."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

_reader_instance: Optional["SatelliteImageReader"] = None


class SatelliteImageReader:
    """Thin wrapper around services.satellite_image_reader.SatelliteImageReader
    that matches the interface expected by the FastAPI endpoints."""

    def __init__(self):
        from services.satellite_image_reader import SatelliteImageReader as _SIR
        self._reader: Optional[_SIR] = None
        self._image_id: Optional[str] = None

    def load_image(self, bands: dict, metadata: dict = None, image_id: str = None) -> dict[str, Any]:
        from services.satellite_image_reader import SatelliteImageReader as _SIR, ImageMetadata

        meta = ImageMetadata(
            filename=metadata.get("filename", "uploaded_image"),
            satellite=metadata.get("satellite", "unknown"),
            crs=metadata.get("crs", "EPSG:4326"),
            bounds=metadata.get("bounds"),
            resolution=metadata.get("resolution"),
        )

        band_arrays = {}
        for name, data in bands.items():
            if isinstance(data, list):
                arr = np.array(data, dtype=np.float64)
            elif isinstance(data, np.ndarray):
                arr = data.astype(np.float64)
            else:
                arr = np.array(data, dtype=np.float64)
            if arr.ndim == 1:
                side = int(np.sqrt(arr.size))
                if side * side == arr.size:
                    arr = arr.reshape(side, side)
            band_arrays[name] = arr

        self._reader = _SIR(metadata=meta)
        self._reader.load_from_arrays(band_arrays, meta)
        self._image_id = self._reader.image_id

        return {
            "image_id": self._image_id,
            "bands_loaded": list(band_arrays.keys()),
            "shape": list(self._reader.shape),
            "metadata": meta.to_dict(),
        }

    def analyze_image(self, image_id: str = None, bands: dict = None) -> dict[str, Any]:
        if not self._reader:
            return {"error": "No image loaded. Call load_image first."}

        stats = self._reader.get_image_stats()

        result = {
            "image_id": self._image_id or image_id,
            "band_statistics": {},
            "spectral_indices": {},
        }

        for band_name, band_stats in stats.items():
            result["band_statistics"][band_name] = {
                k: v for k, v in band_stats.items()
                if k != "histogram"
            }

        try:
            if "B08" in self._reader.band_names and "B04" in self._reader.band_names:
                ndvi = self._reader._compute_ndvi()
                valid = ndvi[np.isfinite(ndvi)]
                if valid.size > 0:
                    result["spectral_indices"]["NDVI"] = {
                        "mean": float(np.mean(valid)),
                        "min": float(np.min(valid)),
                        "max": float(np.max(valid)),
                    }
        except Exception:
            pass

        try:
            if "B11" in self._reader.band_names and "B08" in self._reader.band_names:
                bsi = self._reader._compute_bsi()
                valid = bsi[np.isfinite(bsi)]
                if valid.size > 0:
                    result["spectral_indices"]["BSI"] = {
                        "mean": float(np.mean(valid)),
                        "min": float(np.min(valid)),
                        "max": float(np.max(valid)),
                    }
        except Exception:
            pass

        result["total_bands"] = len(self._reader.band_names)
        result["dimensions"] = {"width": self._reader.shape[1], "height": self._reader.shape[0]}

        return result

    def detect_features(self, image_id: str = None, bands: dict = None,
                        detection_type: str = "all") -> dict[str, Any]:
        if not self._reader:
            return {"error": "No image loaded."}

        result = {"image_id": self._image_id or image_id, "detections": {}}

        try:
            if detection_type in ("all", "vegetation") and "B08" in self._reader.band_names:
                mask = self._reader.detect_vegetation()
                result["detections"]["vegetation"] = {
                    "pixel_count": int(np.sum(mask)),
                    "total_pixels": int(mask.size),
                    "percentage": round(100.0 * np.sum(mask) / mask.size, 2),
                }
        except Exception as e:
            result["detections"]["vegetation"] = {"error": str(e)}

        try:
            if detection_type in ("all", "water") and "B08" in self._reader.band_names:
                mask = self._reader.detect_water()
                result["detections"]["water"] = {
                    "pixel_count": int(np.sum(mask)),
                    "total_pixels": int(mask.size),
                    "percentage": round(100.0 * np.sum(mask) / mask.size, 2),
                }
        except Exception as e:
            result["detections"]["water"] = {"error": str(e)}

        try:
            if detection_type in ("all", "bare_soil"):
                mask = self._reader.detect_bare_soil()
                result["detections"]["bare_soil"] = {
                    "pixel_count": int(np.sum(mask)),
                    "total_pixels": int(mask.size),
                    "percentage": round(100.0 * np.sum(mask) / mask.size, 2),
                }
        except Exception as e:
            result["detections"]["bare_soil"] = {"error": str(e)}

        try:
            if detection_type in ("all", "clouds") and "B02" in self._reader.band_names:
                mask = self._reader.detect_clouds()
                result["detections"]["clouds"] = {
                    "pixel_count": int(np.sum(mask)),
                    "total_pixels": int(mask.size),
                    "percentage": round(100.0 * np.sum(mask) / mask.size, 2),
                }
        except Exception as e:
            result["detections"]["clouds"] = {"error": str(e)}

        return result

    def get_pixel_info(self, image_id: str, longitude: float, latitude: float) -> dict[str, Any]:
        if not self._reader:
            return {"error": "No image loaded."}
        try:
            values = self._reader.get_pixel_value(longitude, latitude)
            return {
                "image_id": self._image_id or image_id,
                "coordinates": {"longitude": longitude, "latitude": latitude},
                "band_values": values,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_thumbnail(self, image_id: str, width: int = 256, height: int = 256) -> dict[str, Any]:
        if not self._reader:
            return {"error": "No image loaded."}
        try:
            b64 = self._reader.generate_thumbnail(width, height)
            return {
                "image_id": self._image_id or image_id,
                "thumbnail_base64": b64,
                "width": width,
                "height": height,
            }
        except Exception as e:
            return {"error": str(e)}

    def create_overlay(self, image_id: str, annotations: dict) -> dict[str, Any]:
        if not self._reader:
            return {"error": "No image loaded."}
        try:
            features = annotations.get("annotations", []) if isinstance(annotations, dict) else annotations
            if isinstance(features, dict):
                features = features.get("features", [])

            b64 = self._reader.generate_annotated_overlay(features)
            return {
                "image_id": self._image_id or image_id,
                "overlay_base64": b64,
                "annotation_count": len(features) if isinstance(features, list) else 0,
            }
        except Exception as e:
            return {"error": str(e)}


def get_image_reader() -> SatelliteImageReader:
    global _reader_instance
    if _reader_instance is None:
        _reader_instance = SatelliteImageReader()
    return _reader_instance
