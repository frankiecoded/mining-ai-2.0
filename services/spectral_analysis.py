"""
Spectral Analysis Engine for Mining Remote Sensing
Computes spectral indices from multispectral satellite imagery.
Implements vegetation, mineral, alteration, and structural indices.
"""

import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class IndexCategory(Enum):
    VEGETATION = "vegetation"
    MINERAL = "mineral"
    ALTERATION = "alteration"
    WATER = "water"
    SOIL = "soil"
    STRUCTURAL = "structural"
    THERMAL = "thermal"


@dataclass
class SpectralIndex:
    name: str
    short_name: str
    category: IndexCategory
    formula: str
    description: str
    bands_required: List[str]
    interpretation: Dict[str, str]
    mining_relevance: str


@dataclass
class IndexResult:
    index_name: str
    short_name: str
    category: IndexCategory
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    percentiles: Dict[int, float]
    interpretation: str
    anomaly_pixels: int
    total_pixels: int
    anomaly_percent: float
    mining_relevance: str


class SpectralIndices:
    """Complete library of spectral indices for mining remote sensing."""

    INDICES: Dict[str, SpectralIndex] = {}

    def __init__(self):
        self._register_indices()

    def _register_indices(self):
        """Register all available spectral indices."""

        # VEGETATION INDICES
        self._register(SpectralIndex(
            name="Normalized Difference Vegetation Index",
            short_name="NDVI",
            category=IndexCategory.VEGETATION,
            formula="(NIR - Red) / (NIR + Red)",
            description="Measures vegetation health and density. Healthy vegetation has high NDVI.",
            bands_required=["NIR", "Red"],
            interpretation={
                "high": "> 0.6 - Dense healthy vegetation",
                "moderate": "0.2 to 0.6 - Sparse or stressed vegetation",
                "low": "< 0.2 - Bare soil, rock, or water",
                "negative": "< 0 - Water bodies"
            },
            mining_relevance="Vegetation anomalies can indicate mineralization. Hydrothermal alteration zones often show reduced vegetation. Tailings and waste dumps show no vegetation."
        ))

        self._register(SpectralIndex(
            name="Enhanced Vegetation Index",
            short_name="EVI",
            category=IndexCategory.VEGETATION,
            formula="2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)",
            description="Enhanced vegetation index, less sensitive to atmospheric effects.",
            bands_required=["NIR", "Red", "Blue"],
            interpretation={
                "high": "> 0.5 - Dense vegetation",
                "moderate": "0.2 to 0.5 - Moderate vegetation",
                "low": "< 0.2 - Sparse or no vegetation"
            },
            mining_relevance="More robust than NDVI for detecting subtle vegetation changes over mining areas."
        ))

        self._register(SpectralIndex(
            name="Normalized Difference Moisture Index",
            short_name="NDMI",
            category=IndexCategory.VEGETATION,
            formula="(NIR - SWIR1) / (NIR + SWIR1)",
            description="Measures vegetation water content and moisture stress.",
            bands_required=["NIR", "SWIR1"],
            interpretation={
                "high": "> 0.4 - High moisture content",
                "moderate": "0.2 to 0.4 - Moderate moisture",
                "low": "< 0.2 - Water stress or bare ground"
            },
            mining_relevance="Hydrothermal alteration zones may show different moisture signatures. Useful for detecting clay minerals."
        ))

        # MINERAL / IRON OXIDE INDICES
        self._register(SpectralIndex(
            name="Band Ratio 4/2 (Iron Oxide)",
            short_name="BR42",
            category=IndexCategory.MINERAL,
            formula="Red / Blue",
            description="Detects iron oxide minerals (hematite, goethite) which absorb blue and reflect red.",
            bands_required=["Red", "Blue"],
            interpretation={
                "high": "> 1.5 - Strong iron oxide presence",
                "moderate": "1.0 to 1.5 - Moderate iron oxides",
                "low": "< 1.0 - Low iron oxide content"
            },
            mining_relevance="Iron oxide staining is a key indicator of gossans, weathered sulfide deposits, and hydrothermal alteration. Critical for gold exploration."
        ))

        self._register(SpectralIndex(
            name="Band Ratio 4/3 (Ferric Iron)",
            short_name="BR43",
            category=IndexCategory.MINERAL,
            formula="Red / Green",
            description="Detects ferric iron minerals.",
            bands_required=["Red", "Green"],
            interpretation={
                "high": "> 1.2 - High ferric iron",
                "moderate": "0.9 to 1.2 - Moderate ferric iron",
                "low": "< 0.9 - Low ferric iron"
            },
            mining_relevance="Ferric iron minerals are common in weathered and oxidized zones of mineral deposits."
        ))

        self._register(SpectralIndex(
            name="Ferrous Iron Index",
            short_name="FER",
            category=IndexCategory.MINERAL,
            formula="SWIR1 / NIR",
            description="Detects ferrous iron minerals (magnetite, pyrite).",
            bands_required=["SWIR1", "NIR"],
            interpretation={
                "high": "> 1.0 - High ferrous iron content",
                "moderate": "0.7 to 1.0 - Moderate",
                "low": "< 0.7 - Low ferrous iron"
            },
            mining_relevance="Ferrous iron minerals are associated with sulfide mineralization and magnetite-bearing deposits."
        ))

        # ALTERATION INDICES
        self._register(SpectralIndex(
            name="Clay Ratio (Alunite/Kaolinite)",
            short_name="CLAY",
            category=IndexCategory.ALTERATION,
            formula="SWIR1 / SWIR2",
            description="Detects clay minerals (kaolinite, alunite, montmorillonite) which have absorption at 2.2μm.",
            bands_required=["SWIR1", "SWIR2"],
            interpretation={
                "high": "> 1.3 - Strong clay alteration",
                "moderate": "1.0 to 1.3 - Moderate clay presence",
                "low": "< 1.0 - Low clay content"
            },
            mining_relevance="Clay alteration (argillic) is a key indicator of hydrothermal systems, especially porphyry copper and epithermal gold deposits."
        ))

        self._register(SpectralIndex(
            name="Alunite Index",
            short_name="ALUN",
            category=IndexCategory.ALTERATION,
            formula="(SWIR1 - SWIR2) / (SWIR1 + SWIR2)",
            description="Normalized index for alunite detection, common in advanced argillic alteration.",
            bands_required=["SWIR1", "SWIR2"],
            interpretation={
                "high": "> 0.15 - Strong alunite signature",
                "moderate": "0.05 to 0.15 - Moderate alunite",
                "low": "< 0.05 - Low alunite presence"
            },
            mining_relevance="Alunite is diagnostic of advanced argillic alteration, associated with high-sulfidation epithermal gold and porphyry copper systems."
        ))

        self._register(SpectralIndex(
            name="Sericite-Chlorite Index",
            short_name="SERC",
            category=IndexCategory.ALTERATION,
            formula="(B7 - B11) / (B7 + B11)",
            description="Detects sericite and chlorite alteration using red edge and SWIR bands.",
            bands_required=["B07", "B11"],
            interpretation={
                "high": "> 0.2 - Strong sericite/chlorite",
                "moderate": "0.0 to 0.2 - Moderate presence",
                "low": "< 0.0 - Low presence"
            },
            mining_relevance="Sericite (phyllic) alteration is a key indicator of porphyry copper and orogenic gold systems."
        ))

        self._register(SpectralIndex(
            name="Silica Index",
            short_name="SILICA",
            category=IndexCategory.ALTERATION,
            formula="SWIR2 / SWIR1",
            description="Detects silica-rich zones (quartz veining, silicification).",
            bands_required=["SWIR2", "SWIR1"],
            interpretation={
                "high": "> 1.0 - High silica content",
                "moderate": "0.8 to 1.0 - Moderate silica",
                "low": "< 0.8 - Low silica"
            },
            mining_relevance="Silicification is associated with quartz veining in vein-hosted gold deposits and the core of porphyry systems."
        ))

        self._register(SpectralIndex(
            name="Mica Index",
            short_name="MICA",
            category=IndexCategory.ALTERATION,
            formula="B10 / B11",
            description="Detects mica minerals (muscovite, biotite) using cirrus and SWIR bands.",
            bands_required=["B10", "B11"],
            interpretation={
                "high": "> 1.2 - Strong mica signature",
                "moderate": "0.8 to 1.2 - Moderate mica",
                "low": "< 0.8 - Low mica content"
            },
            mining_relevance="White mica (sericite) is a key alteration mineral in many gold and copper deposits."
        ))

        # HYDROTHERMAL ALTERATION ZONE DETECTION
        self._register(SpectralIndex(
            name="Hydrothermal Alteration Composite",
            short_name="HALT",
            category=IndexCategory.ALTERATION,
            formula="(Clay * Iron * Silica)^(1/3)",
            description="Composite index combining clay, iron oxide, and silica indicators for hydrothermal alteration detection.",
            bands_required=["Red", "Blue", "SWIR1", "SWIR2"],
            interpretation={
                "high": "> 0.3 - Strong hydrothermal alteration signature",
                "moderate": "0.15 to 0.3 - Moderate alteration",
                "low": "< 0.15 - Weak or no alteration"
            },
            mining_relevance="Combined alteration mineralogy increases confidence in identifying hydrothermal systems. High values indicate zones where multiple alteration minerals coexist."
        ))

        # WATER INDICES
        self._register(SpectralIndex(
            name="Normalized Difference Water Index",
            short_name="NDWI",
            category=IndexCategory.WATER,
            formula="(Green - NIR) / (Green + NIR)",
            description="Detects surface water bodies and moisture.",
            bands_required=["Green", "NIR"],
            interpretation={
                "high": "> 0.3 - Water bodies",
                "moderate": "0.0 to 0.3 - Moist areas",
                "low": "< 0.0 - Dry land"
            },
            mining_relevance="Useful for detecting water bodies, tailings pond extent, and moisture anomalies near mineralization."
        ))

        self._register(SpectralIndex(
            name="Modified Normalized Difference Water Index",
            short_name="MNDWI",
            category=IndexCategory.WATER,
            formula="(Green - SWIR1) / (Green + SWIR1)",
            description="Modified water index, better at discriminating water from built-up areas.",
            bands_required=["Green", "SWIR1"],
            interpretation={
                "high": "> 0.5 - Open water",
                "moderate": "0.0 to 0.5 - Wet soil/vegetation",
                "low": "< 0.0 - Non-water"
            },
            mining_relevance="Detects water accumulation in mine pits, tailings facilities, and natural water bodies."
        ))

        # SOIL / BARE EARTH INDICES
        self._register(SpectralIndex(
            name="Bare Soil Index",
            short_name="BSI",
            category=IndexCategory.SOIL,
            formula="((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))",
            description="Identifies exposed bare soil and rock surfaces.",
            bands_required=["SWIR1", "Red", "NIR", "Blue"],
            interpretation={
                "high": "> 0.1 - Exposed bare soil",
                "moderate": "-0.1 to 0.1 - Mixed soil/vegetation",
                "low": "< -0.1 - Vegetated or water"
            },
            mining_relevance="Detects mine dumps, waste rock piles, tailings, and exposed geological surfaces."
        ))

        # STRUCTURAL INDICES
        self._register(SpectralIndex(
            name="Thermal Anomaly Index",
            short_name="THERM",
            category=IndexCategory.STRUCTURAL,
            formula="(SWIR2 - SWIR1) / (SWIR2 + SWIR1)",
            description="Detects thermal anomalies that may indicate subsurface heat flow or combustion.",
            bands_required=["SWIR1", "SWIR2"],
            interpretation={
                "high": "> 0.1 - Potential thermal anomaly",
                "moderate": "-0.05 to 0.1 - Normal range",
                "low": "< -0.05 - Cool surface"
            },
            mining_relevance="Thermal anomalies can indicate coal fires, geothermal activity, or subsurface mineralization."
        ))

    def _register(self, index: SpectralIndex):
        """Register a spectral index."""
        self.INDICES[index.short_name] = index

    def get_index(self, short_name: str) -> Optional[SpectralIndex]:
        """Get a spectral index by short name."""
        return self.INDICES.get(short_name)

    def get_indices_by_category(self, category: IndexCategory) -> List[SpectralIndex]:
        """Get all indices in a category."""
        return [idx for idx in self.INDICES.values() if idx.category == category]

    def get_mining_relevant_indices(self) -> List[SpectralIndex]:
        """Get indices most relevant for mineral exploration."""
        priority = ["NDVI", "BR42", "CLAY", "HALT", "SILICA", "BSI", "FER", "ALUN", "SERC"]
        return [self.INDICES[name] for name in priority if name in self.INDICES]

    def list_all(self) -> List[Dict[str, Any]]:
        """List all available indices."""
        return [
            {
                "name": idx.name,
                "short_name": idx.short_name,
                "category": idx.category.value,
                "formula": idx.formula,
                "description": idx.description,
                "bands_required": idx.bands_required,
                "mining_relevance": idx.mining_relevance
            }
            for idx in self.INDICES.values()
        ]


class SpectralCalculator:
    """Calculates spectral indices from band data."""

    def __init__(self):
        self.library = SpectralIndices()

    def calculate_index(self, short_name: str, band_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate a spectral index from band data.

        band_data: dict of band_name -> numpy array or list of values
        """
        index = self.library.get_index(short_name)
        if not index:
            return {"error": f"Unknown index: {short_name}"}

        try:
            import numpy as np
        except ImportError:
            return self._calculate_simple(short_name, band_data)

        try:
            result = self._compute_index(index, band_data, np)
            return result
        except Exception as e:
            logger.error(f"Index calculation failed: {e}")
            return {"error": str(e)}

    def _compute_index(self, index: SpectralIndex, band_data: Dict[str, Any], np) -> Dict[str, Any]:
        """Compute the spectral index using numpy."""
        band_arrays = {}
        for band_name in index.bands_required:
            if band_name in band_data:
                band_arrays[band_name] = np.array(band_data[band_name], dtype=np.float32)
            else:
                alt_names = self._get_alternate_names(band_name)
                found = False
                for alt in alt_names:
                    if alt in band_data:
                        band_arrays[band_name] = np.array(band_data[alt], dtype=np.float32)
                        found = True
                        break
                if not found:
                    return {"error": f"Missing required band: {band_name}"}

        B = band_arrays
        result_array = None

        if index.short_name == "NDVI":
            nir, red = B["NIR"], B["Red"]
            result_array = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)
        elif index.short_name == "EVI":
            nir, red, blue = B["NIR"], B["Red"], B["Blue"]
            denom = nir + 6 * red - 7.5 * blue + 1
            result_array = np.where(denom > 0, 2.5 * (nir - red) / denom, 0)
        elif index.short_name == "NDMI":
            nir, swir1 = B["NIR"], B["SWIR1"]
            result_array = np.where((nir + swir1) > 0, (nir - swir1) / (nir + swir1), 0)
        elif index.short_name == "BR42":
            red, blue = B["Red"], B["Blue"]
            result_array = np.where(blue > 0, red / blue, 0)
        elif index.short_name == "BR43":
            red, green = B["Red"], B["Green"]
            result_array = np.where(green > 0, red / green, 0)
        elif index.short_name == "FER":
            swir1, nir = B["SWIR1"], B["NIR"]
            result_array = np.where(nir > 0, swir1 / nir, 0)
        elif index.short_name == "CLAY":
            swir1, swir2 = B["SWIR1"], B["SWIR2"]
            result_array = np.where(swir2 > 0, swir1 / swir2, 0)
        elif index.short_name == "ALUN":
            swir1, swir2 = B["SWIR1"], B["SWIR2"]
            result_array = np.where((swir1 + swir2) > 0, (swir1 - swir2) / (swir1 + swir2), 0)
        elif index.short_name == "SILICA":
            swir2, swir1 = B["SWIR2"], B["SWIR1"]
            result_array = np.where(swir1 > 0, swir2 / swir1, 0)
        elif index.short_name == "NDWI":
            green, nir = B["Green"], B["NIR"]
            result_array = np.where((green + nir) > 0, (green - nir) / (green + nir), 0)
        elif index.short_name == "MNDWI":
            green, swir1 = B["Green"], B["SWIR1"]
            result_array = np.where((green + swir1) > 0, (green - swir1) / (green + swir1), 0)
        elif index.short_name == "BSI":
            swir1, red, nir, blue = B["SWIR1"], B["Red"], B["NIR"], B["Blue"]
            num = (swir1 + red) - (nir + blue)
            den = (swir1 + red) + (nir + blue)
            result_array = np.where(den > 0, num / den, 0)
        elif index.short_name == "THERM":
            swir1, swir2 = B["SWIR1"], B["SWIR2"]
            result_array = np.where((swir2 + swir1) > 0, (swir2 - swir1) / (swir2 + swir1), 0)
        elif index.short_name == "SERC":
            b7, b11 = B.get("B07"), B.get("B11")
            if b7 is not None and b11 is not None:
                result_array = np.where((b7 + b11) > 0, (b7 - b11) / (b7 + b11), 0)
            else:
                return {"error": "B07 and B11 bands required for SERC index"}
        elif index.short_name == "MICA":
            b10, b11 = B.get("B10"), B.get("B11")
            if b10 is not None and b11 is not None:
                result_array = np.where(b11 > 0, b10 / b11, 0)
            else:
                return {"error": "B10 and B11 bands required for MICA index"}
        elif index.short_name == "HALT":
            clay = np.where(B["SWIR2"] > 0, B["SWIR1"] / B["SWIR2"], 0)
            iron = np.where(B["Blue"] > 0, B["Red"] / B["Blue"], 0)
            silica = np.where(B["SWIR1"] > 0, B["SWIR2"] / B["SWIR1"], 0)
            result_array = np.power(np.clip(clay * iron * silica, 0, None), 1/3)

        if result_array is None:
            return {"error": f"Index {index.short_name} not implemented in calculator"}

        flat = result_array.flatten()
        flat_valid = flat[np.isfinite(flat)]

        if len(flat_valid) == 0:
            return {"error": "No valid pixels in result"}

        percentiles = {
            int(p): float(np.percentile(flat_valid, p)) for p in [5, 25, 50, 75, 95]
        }

        high_threshold = percentiles.get(75, 0) + 1.5 * (percentiles.get(75, 0) - percentiles.get(25, 0))
        anomaly_count = int(np.sum(flat_valid > high_threshold))

        interpretation = self._interpret_value(float(np.mean(flat_valid)), index)

        return {
            "index_name": index.name,
            "short_name": index.short_name,
            "category": index.category.value,
            "formula": index.formula,
            "min_value": float(np.min(flat_valid)),
            "max_value": float(np.max(flat_valid)),
            "mean_value": float(np.mean(flat_valid)),
            "std_value": float(np.std(flat_valid)),
            "percentiles": percentiles,
            "anomaly_pixels": anomaly_count,
            "total_pixels": len(flat_valid),
            "anomaly_percent": (anomaly_count / len(flat_valid) * 100) if len(flat_valid) > 0 else 0,
            "interpretation": interpretation,
            "mining_relevance": index.mining_relevance,
            "shape": list(result_array.shape) if hasattr(result_array, 'shape') else None
        }

    def _calculate_simple(self, short_name: str, band_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simple calculation without numpy for environments without it."""
        index = self.library.get_index(short_name)

        def safe_div(a, b):
            return a / b if b != 0 else 0

        results = []
        num_pixels = 0

        if isinstance(list(band_data.values())[0], (list, tuple)):
            num_pixels = len(list(band_data.values())[0])
            for i in range(num_pixels):
                bands = {k: v[i] if isinstance(v, (list, tuple)) else v for k, v in band_data.items()}
                val = self._calc_single(short_name, bands)
                if val is not None:
                    results.append(val)
        else:
            val = self._calc_single(short_name, band_data)
            if val is not None:
                results.append(val)
            num_pixels = 1

        if not results:
            return {"error": "No valid results"}

        mean_val = sum(results) / len(results)
        min_val = min(results)
        max_val = max(results)
        interpretation = self._interpret_value(mean_val, index)

        return {
            "index_name": index.name,
            "short_name": index.short_name,
            "category": index.category.value,
            "mean_value": mean_val,
            "min_value": min_val,
            "max_value": max_val,
            "total_pixels": num_pixels,
            "valid_pixels": len(results),
            "interpretation": interpretation,
            "mining_relevance": index.mining_relevance
        }

    def _calc_single(self, short_name: str, bands: Dict[str, Any]) -> Optional[float]:
        """Calculate index for a single pixel."""
        def safe(v):
            return float(v) if v is not None else 0

        try:
            if short_name == "NDVI":
                nir, red = safe(bands.get("NIR")), safe(bands.get("Red"))
                return (nir - red) / (nir + red) if (nir + red) != 0 else 0
            elif short_name == "BR42":
                return safe(bands.get("Red")) / safe(bands.get("Blue")) if safe(bands.get("Blue")) != 0 else 0
            elif short_name == "CLAY":
                return safe(bands.get("SWIR1")) / safe(bands.get("SWIR2")) if safe(bands.get("SWIR2")) != 0 else 0
            elif short_name == "NDWI":
                green, nir = safe(bands.get("Green")), safe(bands.get("NIR"))
                return (green - nir) / (green + nir) if (green + nir) != 0 else 0
            elif short_name == "BSI":
                swir1, red = safe(bands.get("SWIR1")), safe(bands.get("Red"))
                nir, blue = safe(bands.get("NIR")), safe(bands.get("Blue"))
                num = (swir1 + red) - (nir + blue)
                den = (swir1 + red) + (nir + blue)
                return num / den if den != 0 else 0
        except Exception:
            return None
        return None

    def _get_alternate_names(self, band_name: str) -> List[str]:
        """Get alternate names for a band."""
        alternates = {
            "NIR": ["B08", "B08A", "B5", "nir"],
            "Red": ["B04", "B4", "red"],
            "Green": ["B03", "B3", "green"],
            "Blue": ["B02", "B2", "blue"],
            "SWIR1": ["B11", "B6", "swir1"],
            "SWIR2": ["B12", "B7", "swir2"],
            "B07": ["B7"],
            "B10": ["B10"],
            "B11": ["B11"],
        }
        return alternates.get(band_name, [])

    def _interpret_value(self, value: float, index: SpectralIndex) -> str:
        """Interpret an index value."""
        interp = index.interpretation
        if value > 0.5:
            return interp.get("high", "High value")
        elif value > 0.2:
            return interp.get("moderate", "Moderate value")
        elif value > 0:
            return interp.get("low", "Low value")
        else:
            return interp.get("negative", "Negative value") if "negative" in interp else interp.get("low", "Low value")

    def calculate_all_indices(self, band_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate all applicable indices from available bands."""
        results = {}
        for short_name, index in self.library.INDICES.items():
            available = all(
                b in band_data or any(alt in band_data for alt in self._get_alternate_names(b))
                for b in index.bands_required
            )
            if available:
                result = self.calculate_index(short_name, band_data)
                if "error" not in result:
                    results[short_name] = result
        return results

    def get_exploration_assessment(self, band_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive exploration assessment from spectral data."""
        all_results = self.calculate_all_indices(band_data)

        indicators = {
            "alteration": {
                "clay": all_results.get("CLAY", {}).get("mean_value", 0),
                "iron_oxide": all_results.get("BR42", {}).get("mean_value", 0),
                "silica": all_results.get("SILICA", {}).get("mean_value", 0),
                "alunite": all_results.get("ALUN", {}).get("mean_value", 0),
            },
            "vegetation": {
                "ndvi": all_results.get("NDVI", {}).get("mean_value", 0),
                "moisture": all_results.get("NDMI", {}).get("mean_value", 0),
            },
            "surface": {
                "bare_soil": all_results.get("BSI", {}).get("mean_value", 0),
                "water": all_results.get("NDWI", {}).get("mean_value", 0),
            }
        }

        alteration_score = 0
        if indicators["alteration"]["clay"] > 1.0:
            alteration_score += 25
        if indicators["alteration"]["iron_oxide"] > 1.3:
            alteration_score += 25
        if indicators["alteration"]["silica"] > 0.8:
            alteration_score += 25
        if indicators["alteration"]["alunite"] > 0.05:
            alteration_score += 25

        confidence = len(all_results) / len(self.library.INDICES) * 100

        assessment = {
            "alteration_score": alteration_score,
            "alteration_level": "high" if alteration_score >= 75 else "moderate" if alteration_score >= 50 else "low" if alteration_score >= 25 else "none",
            "confidence": confidence,
            "indices_calculated": len(all_results),
            "indicators": indicators,
            "indices": all_results,
            "recommendation": self._generate_recommendation(alteration_score, indicators)
        }

        return assessment

    def _generate_recommendation(self, score: float, indicators: Dict) -> str:
        """Generate exploration recommendation based on spectral analysis."""
        if score >= 75:
            return "Strong spectral indicators of hydrothermal alteration. Recommend detailed field mapping, soil/rock sampling, and further remote sensing analysis. Consider follow-up drilling."
        elif score >= 50:
            return "Moderate spectral indicators present. Recommend systematic soil/rock chip sampling program and structural mapping. Additional imagery acquisition recommended."
        elif score >= 25:
            return "Some spectral indicators detected. Recommend reconnaissance field visit and stream sediment sampling. Compare with regional geological data."
        else:
            return "Weak spectral alteration indicators. Continue regional screening. Consider acquiring higher-resolution or hyperspectral imagery for detailed analysis."
