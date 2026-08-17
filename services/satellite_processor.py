"""
Satellite Image Processor for Mining Remote Sensing
Preprocessing, enhancement, composites, and band math for satellite imagery.
"""

import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingLevel(Enum):
    RAW = "raw"
    TOP_OF_ATMOSPHERE = "toa"
    SURFACE_REFLECTANCE = "sr"
    ANALYTICAL = "analytical"


class CompositeType(Enum):
    TRUE_COLOR = "true_color"
    FALSE_COLOR_INFRARED = "false_color_infrared"
    FALSE_COLOR_SWIR = "false_color_swir"
    GEOLOGY = "geology"
    AGRICULTURE = "agriculture"
    URBAN = "urban"
    VEGETATION = "vegetation"
    MINERAL_DETECTION = "mineral_detection"


COMPOSITE_BANDS = {
    CompositeType.TRUE_COLOR: {"red": "B04", "green": "B03", "blue": "B02"},
    CompositeType.FALSE_COLOR_INFRARED: {"red": "B08", "green": "B04", "blue": "B03"},
    CompositeType.FALSE_COLOR_SWIR: {"red": "B12", "green": "B08A", "blue": "B04"},
    CompositeType.GEOLOGY: {"red": "B12", "green": "B11", "blue": "B02"},
    CompositeType.AGRICULTURE: {"red": "B11", "green": "B08", "blue": "B02"},
    CompositeType.VEGETATION: {"red": "B08", "green": "B04", "blue": "B03"},
    CompositeType.MINERAL_DETECTION: {"red": "B11", "green": "B04", "blue": "B02"},
}


@dataclass
class ProcessingStep:
    name: str
    description: str
    parameters: Dict[str, Any]
    applied: bool = False


@dataclass
class EnhancedImage:
    data: Any
    bands: List[str]
    processing_steps: List[ProcessingStep]
    statistics: Dict[str, Any]
    metadata: Dict[str, Any]


class SatelliteProcessor:
    """Processes satellite imagery for mining applications."""

    def __init__(self):
        self.processing_chain = []

    def apply_atmospheric_correction(self, band_data: Dict[str, Any],
                                     solar_angle: float = 45,
                                     atmospheric_visibility: float = 100) -> Dict[str, Any]:
        """Apply simplified atmospheric correction (dark object subtraction)."""
        try:
            import numpy as np

            corrected = {}
            for band_name, data in band_data.items():
                arr = np.array(data, dtype=np.float64)
                min_val = np.percentile(arr, 1)
                corrected_arr = np.clip(arr - min_val, 0, None)

                if np.max(corrected_arr) > 0:
                    corrected_arr = corrected_arr / np.max(corrected_arr) * 10000

                corrected[band_name] = corrected_arr

            return corrected
        except ImportError:
            return band_data

    def apply_enhancement(self, band_data: Dict[str, Any],
                         method: str = "linear_stretch") -> Dict[str, Any]:
        """Apply image enhancement."""
        try:
            import numpy as np

            enhanced = {}
            for band_name, data in band_data.items():
                arr = np.array(data, dtype=np.float64)

                if method == "linear_stretch":
                    p2, p98 = np.percentile(arr[arr > 0], [2, 98]) if np.any(arr > 0) else (0, 1)
                    enhanced_arr = np.clip((arr - p2) / (p98 - p2) * 255, 0, 255)
                elif method == "histogram_equalization":
                    valid = arr[arr > 0]
                    if len(valid) > 0:
                        hist, bins = np.histogram(valid, bins=256)
                        cdf = hist.cumsum()
                        cdf_normalized = cdf / cdf.max()
                        enhanced_arr = np.interp(arr.ravel(), bins[:-1], cdf_normalized * 255).reshape(arr.shape)
                    else:
                        enhanced_arr = arr
                elif method == "sigma_stretch":
                    mean = np.mean(arr[arr > 0]) if np.any(arr > 0) else 0
                    std = np.std(arr[arr > 0]) if np.any(arr > 0) else 1
                    enhanced_arr = np.clip((arr - mean) / (2 * std) * 127 + 127, 0, 255)
                else:
                    enhanced_arr = arr

                enhanced[band_name] = enhanced_arr

            return enhanced
        except ImportError:
            return band_data

    def create_composite(self, band_data: Dict[str, Any],
                        composite_type: CompositeType = CompositeType.TRUE_COLOR) -> Dict[str, Any]:
        """Create an RGB composite from band data."""
        bands = COMPOSITE_BANDS.get(composite_type, COMPOSITE_BANDS[CompositeType.TRUE_COLOR])

        try:
            import numpy as np

            r = np.array(band_data.get(bands["red"], band_data.get(list(band_data.keys())[0])), dtype=np.float64)
            g = np.array(band_data.get(bands["green"], band_data.get(list(band_data.keys())[0])), dtype=np.float64)
            b = np.array(band_data.get(bands["blue"], band_data.get(list(band_data.keys())[0])), dtype=np.float64)

            for arr in [r, g, b]:
                if np.max(arr) > 0:
                    p2, p98 = np.percentile(arr[arr > 0], [2, 98]) if np.any(arr > 0) else (0, 1)
                    arr[:] = np.clip((arr - p2) / (p98 - p2) * 255, 0, 255)

            composite = np.stack([r, g, b], axis=-1).astype(np.uint8)

            return {
                "data": composite.tolist() if hasattr(composite, 'tolist') else composite,
                "composite_type": composite_type.value,
                "bands_used": bands,
                "shape": list(composite.shape)
            }
        except ImportError:
            return {"error": "Composite creation requires numpy"}

    def pan_sharpen(self, pan_band: Any, ms_bands: Dict[str, Any],
                    method: str = "ihs") -> Dict[str, Any]:
        """Pan-sharpen multispectral bands using panchromatic band."""
        try:
            import numpy as np

            pan = np.array(pan_band, dtype=np.float64)
            ms_shape = None
            for v in ms_bands.values():
                ms_shape = np.array(v).shape
                break

            if ms_shape is None:
                return {"error": "No multispectral data"}

            target_shape = pan.shape

            if method == "ihs":
                r = np.array(ms_bands.get("B04", ms_bands.get("Red", list(ms_bands.values())[0])), dtype=np.float64)
                g = np.array(ms_bands.get("B03", ms_bands.get("Green", list(ms_bands.values())[0])), dtype=np.float64)
                b = np.array(ms_bands.get("B02", ms_bands.get("Blue", list(ms_bands.values())[0])), dtype=np.float64)

                from scipy.ndimage import zoom
                if r.shape != target_shape:
                    zoom_factors = tuple(t/s for t, s in zip(target_shape, r.shape))
                    r = zoom(r, zoom_factors)
                    g = zoom(g, zoom_factors)
                    b = zoom(b, zoom_factors)

                intensity = (r + g + b) / 3
                hue = np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)
                saturation = np.where(intensity > 0,
                    1 - 3 * np.minimum(np.minimum(r, g), b) / (r + g + b + 1e-10), 0)

                intensity_sharpened = pan / np.max(pan) * np.mean(intensity)

                r_new = intensity_sharpened * (1 + 2 * saturation * np.cos(hue)) / 3
                g_new = intensity_sharpened * (1 + 2 * saturation * np.cos(hue - 2*math.pi/3)) / 3
                b_new = intensity_sharpened * (1 + 2 * saturation * np.cos(hue + 2*math.pi/3)) / 3

                sharpened = {"B04": r_new, "B03": g_new, "B02": b_new}

                return {
                    "bands": sharpened,
                    "method": "IHS",
                    "resolution_improved": True,
                    "output_resolution": "panchromatic"
                }
        except ImportError:
            pass

        return {"error": "Pan-sharpening requires numpy and scipy"}

    def compute_band_math(self, band_data: Dict[str, Any],
                         formula: str) -> Dict[str, Any]:
        """Compute custom band math from user formula."""
        try:
            import numpy as np

            local_vars = {}
            for band_name, data in band_data.items():
                local_vars[band_name] = np.array(data, dtype=np.float64)
                local_vars[band_name.lower()] = local_vars[band_name]

            result = eval(formula, {"__builtins__": {}}, local_vars)

            if isinstance(result, np.ndarray):
                flat = result.flatten()
                flat_valid = flat[np.isfinite(flat)]
                return {
                    "formula": formula,
                    "min": float(np.min(flat_valid)) if len(flat_valid) > 0 else 0,
                    "max": float(np.max(flat_valid)) if len(flat_valid) > 0 else 0,
                    "mean": float(np.mean(flat_valid)) if len(flat_valid) > 0 else 0,
                    "shape": list(result.shape),
                    "valid_pixels": len(flat_valid)
                }
        except Exception as e:
            return {"error": f"Band math failed: {e}"}

        return {"error": "Band math requires numpy and valid formula"}

    def create_mineral_exploration_composite(self, band_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a mineral exploration optimized composite."""
        try:
            import numpy as np

            iron_oxide = None
            if "B04" in band_data and "B02" in band_data:
                red = np.array(band_data["B04"], dtype=np.float64)
                blue = np.array(band_data["B02"], dtype=np.float64)
                iron_oxide = np.where(blue > 0, red / blue, 0)

            alteration = None
            if "B11" in band_data and "B12" in band_data:
                swir1 = np.array(band_data["B11"], dtype=np.float64)
                swir2 = np.array(band_data["B12"], dtype=np.float64)
                alteration = np.where(swir2 > 0, swir1 / swir2, 0)

            vegetation = None
            if "B08" in band_data and "B04" in band_data:
                nir = np.array(band_data["B08"], dtype=np.float64)
                red = np.array(band_data["B04"], dtype=np.float64)
                vegetation = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)

            if iron_oxide is not None and alteration is not None and vegetation is not None:
                for arr in [iron_oxide, alteration, vegetation]:
                    p2, p98 = np.percentile(arr[arr > 0] if np.any(arr > 0) else arr, [2, 98])
                    arr[:] = np.clip((arr - p2) / (p98 - p2) * 255, 0, 255)

                composite = np.stack([iron_oxide, alteration, vegetation], axis=-1).astype(np.uint8)

                return {
                    "data": composite.tolist() if hasattr(composite, 'tolist') else None,
                    "composite_type": "mineral_exploration",
                    "bands": {
                        "red": "Iron Oxide (Red/Blue)",
                        "green": "Alteration (SWIR1/SWIR2)",
                        "blue": "Vegetation (NDVI)"
                    },
                    "description": "Iron oxide appears RED, clay/alteration appears GREEN, vegetation appears BLUE"
                }
        except ImportError:
            pass

        return {"error": "Mineral composite requires numpy"}

    def calculate_image_quality(self, band_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate image quality metrics."""
        try:
            import numpy as np

            metrics = {}
            for band_name, data in band_data.items():
                arr = np.array(data, dtype=np.float64)
                valid = arr[arr > 0]

                if len(valid) > 0:
                    metrics[band_name] = {
                        "mean": float(np.mean(valid)),
                        "std": float(np.std(valid)),
                        "snr": float(np.mean(valid) / np.std(valid)) if np.std(valid) > 0 else 0,
                        "dynamic_range": float(np.max(valid) - np.min(valid)),
                        "percent_saturated": float(np.sum(valid >= np.percentile(valid, 99.5)) / len(valid) * 100)
                    }

            overall_snr = np.mean([m["snr"] for m in metrics.values()]) if metrics else 0

            return {
                "per_band": metrics,
                "overall_snr": float(overall_snr),
                "quality_rating": "excellent" if overall_snr > 50 else "good" if overall_snr > 20 else "fair" if overall_snr > 10 else "poor"
            }
        except ImportError:
            return {"error": "Quality metrics require numpy"}

    def get_processing_recommendations(self, purpose: str = "mineral_exploration") -> Dict[str, Any]:
        """Get recommended processing steps for a given purpose."""
        recommendations = {
            "mineral_exploration": {
                "preprocessing": [
                    "Atmospheric correction (surface reflectance)",
                    "Cloud masking",
                    "Topographic correction"
                ],
                "enhancement": [
                    "Linear stretch (2-98%)",
                    "Band ratio composites"
                ],
                "analysis": [
                    "Iron oxide mapping (Red/Blue)",
                    "Clay alteration mapping (SWIR1/SWIR2)",
                    "Vegetation anomaly detection (NDVI)",
                    "Bare soil mapping (BSI)",
                    "Lineament extraction"
                ],
                "composites": [
                    "Geology composite (B12/B11/B02)",
                    "Mineral detection composite",
                    "False color SWIR (B12/B8A/B04)"
                ]
            },
            "environmental_monitoring": {
                "preprocessing": [
                    "Atmospheric correction",
                    "Cloud masking"
                ],
                "analysis": [
                    "NDVI time series",
                    "Water detection (NDWI)",
                    "Change detection"
                ]
            },
            "geological_mapping": {
                "preprocessing": [
                    "Atmospheric correction",
                    "Terrain correction"
                ],
                "enhancement": [
                    "Contrast enhancement",
                    "Edge enhancement"
                ],
                "analysis": [
                    "Lithological mapping",
                    "Structural lineament extraction",
                    "DEM terrain analysis"
                ]
            }
        }

        return recommendations.get(purpose, recommendations["mineral_exploration"])

    def format_processing_results(self, results: Dict[str, Any]) -> str:
        """Format processing results for display."""
        lines = ["## Satellite Image Processing Results\n"]

        if "composite_type" in results:
            lines.append(f"**Composite Type:** {results['composite_type']}")
            if "bands_used" in results:
                lines.append(f"**Bands:** R={results['bands_used']['red']}, G={results['bands_used']['green']}, B={results['bands_used']['blue']}")

        if "min" in results:
            lines.append(f"**Value Range:** {results['min']:.2f} to {results['max']:.2f}")
            lines.append(f"**Mean:** {results['mean']:.2f}")

        if "quality_rating" in results:
            lines.append(f"**Image Quality:** {results['quality_rating']} (SNR: {results.get('overall_snr', 0):.1f})")

        return "\n".join(lines)
