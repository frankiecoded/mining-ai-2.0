"""
Feature Extraction Engine for Mining Remote Sensing
Detects lineaments, structural features, drainage patterns, and surface disturbances.
"""

import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    LINEAMENT = "lineament"
    FAULT = "fault"
    FRACTURE = "fracture"
    CONTACT = "contact"
    DRAINAGE = "drainage"
    RIDGELINE = "ridgeline"
    VALLEY = "valley"
    CIRCULAR = "circular"
    DISTURBANCE = "disturbance"
    VEGETATION_BOUNDARY = "vegetation_boundary"
    THERMAL_ANOMALY = "thermal_anomaly"


@dataclass
class ExtractedFeature:
    feature_type: FeatureType
    confidence: float
    length_m: Optional[float]
    azimuth_deg: Optional[float]
    start_point: Optional[Tuple[float, float]]
    end_point: Optional[Tuple[float, float]]
    description: str
    geological_significance: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralAnalysis:
    total_features: int
    by_type: Dict[str, int]
    dominant_orientation: float
    orientation玫瑰: Dict[str, int]
    lineament_density: float
    intersection_density: float
    interpretation: str
    mining_relevance: str


class FeatureExtractor:
    """Extracts geological and structural features from remote sensing data."""

    def __init__(self):
        self.min_lineament_length = 100
        self.max_lineament_gap = 3
        self.edge_threshold = 20

    def extract_lineaments(self, dem: Any, hillshade: Any = None) -> Dict[str, Any]:
        """Extract lineaments from DEM or hillshade data."""
        try:
            import numpy as np
            from scipy import ndimage

            if isinstance(dem, (list, list)):
                dem = np.array(dem, dtype=np.float64)

            if hillshade is None:
                from services.terrain_analysis import TerrainAnalyzer
                ta = TerrainAnalyzer()
                hs_result = ta.compute_hillshade(dem)
                data = dem
            else:
                data = np.array(hillshade, dtype=np.float64)

            edges_h = np.abs(np.gradient(data, axis=1))
            edges_v = np.abs(np.gradient(data, axis=0))
            edges_diag1 = np.abs(np.gradient(np.gradient(data, axis=0), axis=1))
            edges_diag2 = np.abs(np.gradient(np.gradient(data, axis=0), axis=1)[:, ::-1])

            combined = np.maximum(np.maximum(edges_h, edges_v), np.maximum(edges_diag1, edges_diag2))

            threshold = np.percentile(combined, 90)
            binary = (combined > threshold).astype(int)

            labeled, num_features = ndimage.label(binary)

            orientations = []
            lengths = []
            features = []

            for i in range(1, min(num_features + 1, 100)):
                coords = np.argwhere(labeled == i)
                if len(coords) < 5:
                    continue

                y_coords = coords[:, 0]
                x_coords = coords[:, 1]

                dy = np.max(y_coords) - np.min(y_coords)
                dx = np.max(x_coords) - np.min(x_coords)

                length = math.sqrt((dx * 30)**2 + (dy * 30)**2)
                azimuth = math.degrees(math.atan2(dx, dy)) % 360

                if length >= self.min_lineament_length:
                    orientations.append(azimuth)
                    lengths.append(length)

                    feature = ExtractedFeature(
                        feature_type=FeatureType.LINEAMENT,
                        confidence=min(0.9, len(coords) / 20),
                        length_m=length,
                        azimuth_deg=azimuth,
                        start_point=(float(x_coords[0] * 30), float(y_coords[0] * 30)),
                        end_point=(float(x_coords[-1] * 30), float(y_coords[-1] * 30)),
                        description=f"Linear feature, {length:.0f}m, {azimuth:.0f}°",
                        geological_significance="May represent fault, fracture zone, or lithological contact."
                    )
                    features.append(feature)

            orientation_hist = self._orientation_histogram(orientations)

            lineament_density = len(orientations) / (data.size * 900 / 1e6) if data.size > 0 else 0

            dominant = max(orientation_hist, key=orientation_hist.get) if orientation_hist else "N/A"

            return {
                "total_features": len(features),
                "features": [self._feature_to_dict(f) for f in features[:50]],
                "orientations": orientation_hist,
                "dominant_orientation": dominant,
                "statistics": {
                    "mean_length": sum(lengths) / len(lengths) if lengths else 0,
                    "max_length": max(lengths) if lengths else 0,
                    "min_length": min(lengths) if lengths else 0,
                    "lineament_density_per_km2": lineament_density
                },
                "interpretation": f"Extracted {len(features)} lineaments. Dominant orientation: {dominant}",
                "mining_relevance": "Lineaments indicate structural controls on mineralization. Dense lineament intersections are high-priority exploration targets."
            }
        except ImportError:
            return {"error": "Feature extraction requires numpy and scipy", "total_features": 0}

    def extract_from_multispectral(self, bands: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from multispectral band data."""
        try:
            import numpy as np
            from scipy import ndimage

            features = []

            if "Red" in bands and "Blue" in bands:
                red = np.array(bands["Red"], dtype=np.float64)
                blue = np.array(bands["Blue"], dtype=np.float64)

                iron = np.where(blue > 0, red / blue, 0)
                iron_binary = (iron > 1.5).astype(int)
                labeled, n_iron = ndimage.label(iron_binary)

                for i in range(1, min(n_iron + 1, 20)):
                    coords = np.argwhere(labeled == i)
                    if len(coords) > 10:
                        features.append(ExtractedFeature(
                            feature_type=FeatureType.VEGETATION_BOUNDARY,
                            confidence=0.7,
                            length_m=len(coords) * 900,
                            azimuth_deg=None,
                            start_point=None,
                            end_point=None,
                            description=f"Iron oxide anomaly zone ({len(coords)} pixels)",
                            geological_significance="Iron oxide staining indicates weathered sulfide or hydrothermal alteration.",
                            metadata={"mineral": "iron_oxide", "pixel_count": len(coords)}
                        ))

            if "NIR" in bands and "Red" in bands:
                nir = np.array(bands["NIR"], dtype=np.float64)
                red = np.array(bands["Red"], dtype=np.float64)
                ndvi = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)

                ndvi_binary = ((ndvi < 0.1) & (ndvi > -0.5)).astype(int)
                labeled, n_bare = ndimage.label(ndvi_binary)

                for i in range(1, min(n_bare + 1, 10)):
                    coords = np.argwhere(labeled == i)
                    if len(coords) > 20:
                        features.append(ExtractedFeature(
                            feature_type=FeatureType.DISTURBANCE,
                            confidence=0.6,
                            length_m=0,
                            azimuth_deg=None,
                            start_point=None,
                            end_point=None,
                            description=f"Bare soil/disturbed area ({len(coords)} pixels)",
                            geological_significance="May indicate mine workings, waste dumps, or natural exposures.",
                            metadata={"type": "bare_soil", "pixel_count": len(coords)}
                        ))

            return {
                "total_features": len(features),
                "features": [self._feature_to_dict(f) for f in features],
                "interpretation": f"Extracted {len(features)} features from multispectral data",
                "mining_relevance": "Multispectral features indicate surface mineralogy, alteration, and disturbance."
            }
        except ImportError:
            return {"error": "Multispectral extraction requires numpy and scipy", "total_features": 0}

    def analyze_structural_patterns(self, lineaments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze structural patterns from extracted lineaments."""
        orientations = lineaments.get("orientations", {})
        total = lineaments.get("total_features", 0)

        if not orientations:
            return {"error": "No orientation data available"}

        sorted_dirs = sorted(orientations.items(), key=lambda x: x[1], reverse=True)

        conjugate_pairs = []
        dirs = list(orientations.keys())
        for i in range(len(dirs)):
            for j in range(i + 1, len(dirs)):
                angle_diff = abs(self._direction_to_angle(dirs[i]) - self._direction_to_angle(dirs[j]))
                if 60 <= angle_diff <= 120:
                    conjugate_pairs.append({
                        "direction_1": dirs[i],
                        "direction_2": dirs[j],
                        "angle_difference": angle_diff,
                        "type": "conjugate_shear"
                    })

        intersection_count = 0
        if total > 1:
            intersection_count = total * (total - 1) // 4

        return {
            "total_lineaments": total,
            "dominant_set_1": sorted_dirs[0][0] if sorted_dirs else None,
            "dominant_set_2": sorted_dirs[1][0] if len(sorted_dirs) > 1 else None,
            "conjugate_pairs": conjugate_pairs,
            "estimated_intersections": intersection_count,
            "structural_complexity": "high" if total > 20 else "moderate" if total > 10 else "low",
            "interpretation": self._interpret_structure(sorted_dirs, conjugate_pairs, total),
            "mining_relevance": "Structural intersections are primary controls on ore deposition in many deposit types."
        }

    def detect_circular_features(self, dem: Any) -> Dict[str, Any]:
        """Detect circular features that might indicate intrusions or collapse structures."""
        try:
            import numpy as np
            from scipy import ndimage

            if isinstance(dem, (list, list)):
                dem = np.array(dem, dtype=np.float64)

            smoothed = ndimage.gaussian_filter(dem, sigma=5)

            from services.terrain_analysis import TerrainAnalyzer
            ta = TerrainAnalyzer()
            tpi_result = ta.compute_tpi(dem)

            local_max = ndimage.maximum_filter(smoothed, size=20)
            peaks = (smoothed == local_max) & (smoothed > np.percentile(smoothed, 90))

            labeled, n_peaks = ndimage.label(peaks)

            circular_features = []
            for i in range(1, min(n_peaks + 1, 10)):
                coords = np.argwhere(labeled == i)
                if len(coords) > 0:
                    cy, cx = coords.mean(axis=0)
                    y_range = np.max(np.abs(coords[:, 0] - cy)) * 30
                    x_range = np.max(np.abs(coords[:, 1] - cx)) * 30
                    radius = max(x_range, y_range)
                    circularity = min(x_range, y_range) / max(x_range, y_range) if max(x_range, y_range) > 0 else 0

                    if circularity > 0.7 and radius > 500:
                        circular_features.append({
                            "center": (float(cx * 30), float(cy * 30)),
                            "radius_m": radius,
                            "circularity": circularity,
                            "elevation": float(smoothed[int(cy), int(cx)]),
                            "confidence": circularity * 0.8,
                            "geological_significance": "May indicate intrusive body, caldera, or structural dome."
                        })

            return {
                "total_circular_features": len(circular_features),
                "features": circular_features,
                "interpretation": f"Identified {len(circular_features)} circular features that may indicate intrusions or domes.",
                "mining_relevance": "Circular features can indicate igneous intrusions associated with porphyry deposits or volcanic calderas."
            }
        except ImportError:
            return {"error": "Circular feature detection requires numpy and scipy", "total_circular_features": 0}

    def extract_all_features(self, dem: Any, bands: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract all features from available data."""
        results = {}

        lineaments = self.extract_lineaments(dem)
        results["lineaments"] = lineaments

        if "error" not in lineaments:
            results["structural"] = self.analyze_structural_patterns(lineaments)

        results["circular"] = self.detect_circular_features(dem)

        if bands:
            results["multispectral"] = self.extract_from_multispectral(bands)

        return results

    def get_exploration_targets(self, all_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify priority exploration targets from extracted features."""
        targets = []

        lineaments = all_features.get("lineaments", {})
        if lineaments.get("total_features", 0) > 15:
            structural = all_features.get("structural", {})
            intersections = structural.get("estimated_intersections", 0)
            if intersections > 50:
                targets.append({
                    "target_type": "structuralIntersection",
                    "priority": "high",
                    "description": f"Dense structural intersection zone with {intersections} estimated intersections",
                    "evidence": [
                        f"{lineaments['total_features']} lineaments detected",
                        f"Dominant orientations: {structural.get('dominant_set_1', 'N/A')} and {structural.get('dominant_set_2', 'N/A')}",
                        "Structural intersections are primary ore controls"
                    ],
                    "recommendation": "Ground truthing with mapping, soil/rock sampling"
                })

        circular = all_features.get("circular", {})
        if circular.get("total_circular_features", 0) > 0:
            for feature in circular.get("features", []):
                if feature.get("confidence", 0) > 0.6:
                    targets.append({
                        "target_type": "circularFeature",
                        "priority": "medium",
                        "description": f"Circular feature, radius {feature.get('radius_m', 0):.0f}m",
                        "evidence": [
                            f"Center: {feature.get('center', 'N/A')}",
                            f"Circularity: {feature.get('circularity', 0):.2f}",
                            "May indicate intrusive body or structural dome"
                        ],
                        "recommendation": "Geophysical survey and drill testing"
                    })

        multispec = all_features.get("multispectral", {})
        if multispec.get("total_features", 0) > 0:
            targets.append({
                "target_type": "spectralAnomaly",
                "priority": "medium",
                "description": f"{multispec['total_features']} spectral anomalies detected",
                "evidence": multispec.get("interpretation", ""),
                "recommendation": "Detailed spectral analysis and ground verification"
            })

        return sorted(targets, key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t["priority"], 3))

    def _orientation_histogram(self, orientations: List[float], bin_size: float = 22.5) -> Dict[str, int]:
        """Create orientation histogram in 16 compass directions."""
        directions = [
            (0, "N"), (22.5, "NNE"), (45, "NE"), (67.5, "ENE"),
            (90, "E"), (112.5, "ESE"), (135, "SE"), (157.5, "SSE"),
            (180, "S"), (202.5, "SSW"), (225, "SW"), (247.5, "WSW"),
            (270, "W"), (292.5, "WNW"), (315, "NW"), (337.5, "NNW")
        ]

        hist = {d[1]: 0 for d in directions}

        for angle in orientations:
            closest = min(directions, key=lambda d: abs(d[0] - angle))
            hist[closest[1]] += 1

        return {k: v for k, v in hist.items() if v > 0}

    def _direction_to_angle(self, direction: str) -> float:
        """Convert compass direction to angle."""
        direction_map = {
            "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
            "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
            "S": 180, "SSW": 202.5, "SW": 247.5, "WSW": 270,
            "W": 292.5, "WNW": 315, "NW": 337.5, "NNW": 360
        }
        return direction_map.get(direction, 0)

    def _feature_to_dict(self, feature: ExtractedFeature) -> Dict[str, Any]:
        """Convert feature to dictionary."""
        return {
            "type": feature.feature_type.value,
            "confidence": feature.confidence,
            "length_m": feature.length_m,
            "azimuth_deg": feature.azimuth_deg,
            "description": feature.description,
            "geological_significance": feature.geological_significance
        }

    def _interpret_structure(self, sorted_dirs: List, conjugate_pairs: List, total: int) -> str:
        """Interpret structural analysis results."""
        if total < 5:
            return "Limited structural features detected. Higher resolution imagery may reveal more structures."

        dominant = sorted_dirs[0][0] if sorted_dirs else "N/A"

        if len(conjugate_pairs) > 0:
            pair = conjugate_pairs[0]
            return (
                f"Dominant structural trend: {dominant}. "
                f"Conjugate shear system detected: {pair['direction_1']}-{pair['direction_2']} "
                f"({pair['angle_difference']:.0f}°). "
                f"This structural pattern is favorable for structurally-controlled mineralization."
            )

        return (
            f"Dominant structural trend: {dominant} with {total} lineaments. "
            f"Structural complexity: {'high' if total > 20 else 'moderate' if total > 10 else 'low'}."
        )
