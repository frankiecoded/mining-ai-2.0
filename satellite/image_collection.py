"""Adapter: bridges main.py image collection endpoints to services/satellite_image_reader.py."""

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ImageCollection:
    """Thin wrapper around services.satellite_image_reader.ImageCollection."""

    def __init__(self, name: str = "default"):
        from services.satellite_image_reader import ImageCollection as _IC
        self._collection = _IC(name=name)
        self._active_reader = None

    def create_composite(self, image_id: str = None, composite_type: str = "true_color") -> dict[str, Any]:
        if not self._active_reader:
            return {"error": "No active image loaded. Call load_image first via image endpoints."}

        reader = self._active_reader
        result = {
            "image_id": image_id or reader.image_id,
            "composite_type": composite_type,
            "bands_used": {},
        }

        composite_maps = {
            "true_color": {"red": "B04", "green": "B03", "blue": "B02"},
            "false_color": {"red": "B08", "green": "B04", "blue": "B03"},
            "mineral": None,
            "vegetation": {"red": "B08", "green": "B04", "blue": "B03"},
        }

        band_map = composite_maps.get(composite_type)

        if composite_type == "mineral" and "B04" in reader.band_names:
            try:
                composite = reader.get_mineral_composite()
                result["bands_used"] = {"red": "iron_oxide", "green": "alteration", "blue": "NDVI"}
                result["shape"] = list(composite["red"].shape)
                return result
            except Exception as e:
                return {"error": f"Mineral composite failed: {e}"}

        if band_map:
            available = set(band_map.values()) & set(reader.band_names)
            missing = set(band_map.values()) - set(reader.band_names)
            if missing:
                result["warning"] = f"Missing bands: {missing}"
            result["bands_used"] = band_map
            try:
                composite = reader._get_rgb(
                    band_map["red"], band_map["green"], band_map["blue"]
                )
                result["shape"] = list(composite["red"].shape)
            except Exception as e:
                result["error"] = str(e)

        return result

    def analyze_terrain(self, dem: Any = None) -> dict[str, Any]:
        if dem is None:
            return {"error": "No DEM data provided."}

        if isinstance(dem, list):
            dem_arr = np.array(dem, dtype=np.float64)
        elif isinstance(dem, np.ndarray):
            dem_arr = dem.astype(np.float64)
        else:
            return {"error": "DEM must be a 2D array or list of lists."}

        if dem_arr.ndim != 2:
            return {"error": f"DEM must be 2D, got {dem_arr.ndim}D"}

        valid = dem_arr[np.isfinite(dem_arr)]
        if valid.size == 0:
            return {"error": "DEM contains no valid data"}

        try:
            dy, dx = np.gradient(dem_arr)
            slope = np.sqrt(dx**2 + dy**2)
            aspect = np.degrees(np.arctan2(-dx, dy)) % 360

            slope_valid = slope[np.isfinite(slope)]
            aspect_valid = aspect[np.isfinite(aspect)]

            return {
                "elevation": {
                    "min": float(np.min(valid)),
                    "max": float(np.max(valid)),
                    "mean": float(np.mean(valid)),
                    "std": float(np.std(valid)),
                },
                "slope": {
                    "min": float(np.min(slope_valid)) if slope_valid.size > 0 else 0,
                    "max": float(np.max(slope_valid)) if slope_valid.size > 0 else 0,
                    "mean": float(np.mean(slope_valid)) if slope_valid.size > 0 else 0,
                },
                "aspect": {
                    "mean": float(np.mean(aspect_valid)) if aspect_valid.size > 0 else 0,
                },
                "shape": list(dem_arr.shape),
            }
        except Exception as e:
            return {"error": f"Terrain analysis failed: {e}"}
