"""
Terrain and DEM Analysis Engine for Mining
Processes Digital Elevation Models for topographic, drainage, and structural analysis.
"""

import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TerrainProduct(Enum):
    SLOPE = "slope"
    ASPECT = "aspect"
    CURVATURE = "curvature"
    TPI = "tpi"
    TRI = "tri"
    HILLSHADE = "hillshade"
    DRAINAGE = "drainage"
    WATERSHED = "watershed"
    RIDGELINE = "ridgeline"
    VALLEY = "valley"
    FLATNESS = "flatness"


@dataclass
class TerrainResult:
    product: TerrainProduct
    description: str
    statistics: Dict[str, float]
    interpretation: str
    mining_relevance: str
    zones: Optional[Dict[str, Any]] = None


@dataclass
class DrainageZone:
    zone_id: int
    area_cells: int
    mean_elevation: float
    max_elevation: float
    min_elevation: float
    drainage_density: float


class TerrainAnalyzer:
    """Complete terrain analysis engine for mining operations."""

    def __init__(self):
        self.cell_size = 30.0
        self.no_data = -9999.0

    def compute_slope(self, dem: Any) -> Dict[str, Any]:
        """Compute slope from DEM in degrees."""
        try:
            import numpy as np

            if isinstance(dem, (list, tuple)):
                dem = np.array(dem, dtype=np.float64)

            dzdx = np.gradient(dem, self.cell_size, axis=1)
            dzdy = np.gradient(dem, self.cell_size, axis=0)
            slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
            slope_deg = np.degrees(slope_rad)

            flat = slope_deg.flatten()
            flat = flat[np.isfinite(flat)]

            zones = {
                "flat": int(np.sum(flat < 2)),
                "gentle": int(np.sum((flat >= 2) & (flat < 10))),
                "moderate": int(np.sum((flat >= 10) & (flat < 25))),
                "steep": int(np.sum((flat >= 25) & (flat < 45))),
                "very_steep": int(np.sum(flat >= 45))
            }

            return {
                "product": "slope",
                "description": "Terrain slope in degrees",
                "statistics": {
                    "min": float(np.min(flat)),
                    "max": float(np.max(flat)),
                    "mean": float(np.mean(flat)),
                    "median": float(np.median(flat)),
                    "std": float(np.std(flat)),
                    "p95": float(np.percentile(flat, 95))
                },
                "zones": zones,
                "interpretation": self._interpret_slope(float(np.mean(flat))),
                "mining_relevance": "Slope controls access roads, waste dump stability, pit wall angles, and infrastructure placement."
            }
        except ImportError:
            return self._slope_simple(dem)

    def _slope_simple(self, dem) -> Dict[str, Any]:
        """Simple slope calculation without numpy."""
        if not isinstance(dem, (list, list)):
            return {"error": "DEM must be a 2D array"}

        rows = len(dem)
        cols = len(dem[0]) if rows > 0 else 0
        slopes = []

        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                dzdx = (dem[r][c+1] - dem[r][c-1]) / (2 * self.cell_size)
                dzdy = (dem[r+1][c] - dem[r-1][c]) / (2 * self.cell_size)
                slope = math.degrees(math.atan(math.sqrt(dzdx**2 + dzdy**2)))
                slopes.append(slope)

        if not slopes:
            return {"error": "Could not compute slopes"}

        mean_slope = sum(slopes) / len(slopes)
        return {
            "product": "slope",
            "description": "Terrain slope in degrees",
            "statistics": {
                "min": min(slopes),
                "max": max(slopes),
                "mean": mean_slope,
                "count": len(slopes)
            },
            "interpretation": self._interpret_slope(mean_slope),
            "mining_relevance": "Slope controls access roads, waste dump stability, pit wall angles, and infrastructure placement."
        }

    def compute_aspect(self, dem: Any) -> Dict[str, Any]:
        """Compute aspect (slope direction) from DEM."""
        try:
            import numpy as np

            if isinstance(dem, (list, tuple)):
                dem = np.array(dem, dtype=np.float64)

            dzdx = np.gradient(dem, self.cell_size, axis=1)
            dzdy = np.gradient(dem, self.cell_size, axis=0)
            aspect_rad = np.arctan2(-dzdy, dzdx)
            aspect_deg = np.degrees(aspect_rad)
            aspect_deg = (aspect_deg + 360) % 360

            flat = aspect_deg.flatten()
            flat = flat[np.isfinite(flat)]

            direction_counts = {
                "north": int(np.sum((flat >= 337.5) | (flat < 22.5))),
                "northeast": int(np.sum((flat >= 22.5) & (flat < 67.5))),
                "east": int(np.sum((flat >= 67.5) & (flat < 112.5))),
                "southeast": int(np.sum((flat >= 112.5) & (flat < 157.5))),
                "south": int(np.sum((flat >= 157.5) & (flat < 202.5))),
                "southwest": int(np.sum((flat >= 202.5) & (flat < 247.5))),
                "west": int(np.sum((flat >= 247.5) & (flat < 292.5))),
                "northwest": int(np.sum((flat >= 292.5) & (flat < 337.5)))
            }

            dominant = max(direction_counts, key=direction_counts.get)

            return {
                "product": "aspect",
                "description": "Slope direction (aspect) in degrees",
                "statistics": {
                    "mean": float(np.mean(flat)),
                    "circular_variance": float(1 - np.abs(np.mean(np.exp(1j * np.radians(flat))))),
                    "dominant_direction": dominant
                },
                "zones": direction_counts,
                "interpretation": f"Dominant slope aspect is {dominant}",
                "mining_relevance": "Aspect affects solar exposure, vegetation patterns, drainage, and can indicate structural trends."
            }
        except ImportError:
            return {"product": "aspect", "description": "Aspect requires numpy", "statistics": {}}

    def compute_curvature(self, dem: Any) -> Dict[str, Any]:
        """Compute plan and profile curvature."""
        try:
            import numpy as np

            if isinstance(dem, (list, tuple)):
                dem = np.array(dem, dtype=np.float64)

            dzdx = np.gradient(dem, self.cell_size, axis=1)
            dzdy = np.gradient(dem, self.cell_size, axis=0)
            d2zdx2 = np.gradient(dzdx, self.cell_size, axis=1)
            d2zdy2 = np.gradient(dzdy, self.cell_size, axis=0)
            d2zdxdy = np.gradient(dzdx, self.cell_size, axis=0)

            p = dzdx**2 + dzdy**2
            plan_curv = np.where(p > 0, -(d2zdy2 * dzdx**2 - 2 * d2zdxdy * dzdx * dzdy + d2zdx2 * dzdy**2) / (p**1.5), 0)
            profile_curv = np.where(p > 0, -(d2zdx2 * dzdx**2 + 2 * d2zdxdy * dzdx * dzdy + d2zdy2 * dzdy**2) / (p**1.5), 0)

            pc_flat = plan_curv.flatten()
            pc_flat = pc_flat[np.isfinite(pc_flat)]

            prc_flat = profile_curv.flatten()
            prc_flat = prc_flat[np.isfinite(prc_flat)]

            return {
                "product": "curvature",
                "description": "Plan and profile curvature",
                "statistics": {
                    "plan_curvature_mean": float(np.mean(pc_flat)) if len(pc_flat) > 0 else 0,
                    "profile_curvature_mean": float(np.mean(prc_flat)) if len(prc_flat) > 0 else 0,
                    "plan_curvature_std": float(np.std(pc_flat)) if len(pc_flat) > 0 else 0,
                },
                "interpretation": "Curvature identifies convergent/divergent terrain which controls water flow and sediment accumulation.",
                "mining_relevance": "Curvature helps identify valley floors (accumulation zones) and ridgelines (erosion zones) important for mine planning."
            }
        except ImportError:
            return {"product": "curvature", "description": "Curvature requires numpy", "statistics": {}}

    def compute_tpi(self, dem: Any) -> Dict[str, Any]:
        """Compute Topographic Position Index."""
        try:
            import numpy as np

            if isinstance(dem, (list, tuple)):
                dem = np.array(dem, dtype=np.float64)

            from scipy.ndimage import uniform_filter
            mean_neighbors = uniform_filter(dem, size=3)
            tpi = dem - mean_neighbors

            flat = tpi.flatten()
            flat = flat[np.isfinite(flat)]

            zones = {
                "valley_floor": int(np.sum(flat < -2)),
                "lower_slope": int(np.sum((flat >= -2) & (flat < -0.5))),
                "mid_slope": int(np.sum((flat >= -0.5) & (flat < 0.5))),
                "upper_slope": int(np.sum((flat >= 0.5) & (flat < 2))),
                "ridgetop": int(np.sum(flat >= 2))
            }

            return {
                "product": "tpi",
                "description": "Topographic Position Index - relative topographic position",
                "statistics": {
                    "min": float(np.min(flat)),
                    "max": float(np.max(flat)),
                    "mean": float(np.mean(flat)),
                    "std": float(np.std(flat))
                },
                "zones": zones,
                "interpretation": "TPI classifies terrain into ridges, slopes, and valleys.",
                "mining_relevance": "TPI identifies landforms important for exploration: ridges (structural highs), valleys (drainage), and slopes (access)."
            }
        except ImportError:
            return {"product": "tpi", "description": "TPI requires numpy and scipy", "statistics": {}}

    def compute_hillshade(self, dem: Any, azimuth: float = 315, altitude: float = 45) -> Dict[str, Any]:
        """Compute hillshade for visualization."""
        try:
            import numpy as np

            if isinstance(dem, (list, tuple)):
                dem = np.array(dem, dtype=np.float64)

            dzdx = np.gradient(dem, self.cell_size, axis=1)
            dzdy = np.gradient(dem, self.cell_size, axis=0)

            az_rad = np.radians(azimuth)
            alt_rad = np.radians(altitude)

            slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
            aspect_rad = np.arctan2(-dzdy, dzdx)

            hs = np.cos(alt_rad) * np.cos(slope_rad) + np.sin(alt_rad) * np.sin(slope_rad) * np.cos(az_rad - aspect_rad)
            hs = np.clip(hs * 255, 0, 255)

            flat = hs.flatten()

            return {
                "product": "hillshade",
                "description": f"Hillshade (azimuth={azimuth}, altitude={altitude})",
                "statistics": {
                    "min": float(np.min(flat)),
                    "max": float(np.max(flat)),
                    "mean": float(np.mean(flat))
                },
                "interpretation": "Hillshade provides terrain visualization and highlights topographic features.",
                "mining_relevance": "Hillshade reveals structural lineaments, fault scarps, and geological features hidden in raw DEM data."
            }
        except ImportError:
            return {"product": "hillshade", "description": "Hillshade requires numpy", "statistics": {}}

    def analyze_drainage(self, dem: Any) -> Dict[str, Any]:
        """Analyze drainage patterns from DEM."""
        try:
            import numpy as np
            from scipy.ndimage import uniform_filter, label

            if isinstance(dem, (list, tuple)):
                dem = np.array(dem, dtype=np.float64)

            dzdx = np.gradient(dem, self.cell_size, axis=1)
            dzdy = np.gradient(dem, self.cell_size, axis=0)
            slope = np.sqrt(dzdx**2 + dzdy**2)

            flow_acc = np.ones_like(dem)
            threshold = np.percentile(dem, 30)

            valley_mask = (dem < threshold + np.std(dem) * 0.5).astype(int)

            labeled, num_features = label(valley_mask)

            drainage_density = num_features / (dem.size * self.cell_size**2 / 1e6)

            return {
                "product": "drainage",
                "description": "Drainage pattern analysis from DEM",
                "statistics": {
                    "num_drainage_lines": num_features,
                    "drainage_density_km_per_km2": float(drainage_density),
                    "mean_slope": float(np.mean(slope)),
                    "elevation_range": float(np.max(dem) - np.min(dem))
                },
                "interpretation": f"Identified {num_features} drainage features. Density: {drainage_density:.2f} km/km²",
                "mining_relevance": "Drainage patterns reveal structural trends, fault orientations, and water management requirements for mining."
            }
        except ImportError:
            return {"product": "drainage", "description": "Drainage analysis requires numpy and scipy", "statistics": {}}

    def compute_all_products(self, dem: Any) -> Dict[str, Any]:
        """Compute all terrain products."""
        results = {}

        results["slope"] = self.compute_slope(dem)
        results["aspect"] = self.compute_aspect(dem)
        results["curvature"] = self.compute_curvature(dem)
        results["tpi"] = self.compute_tpi(dem)
        results["hillshade"] = self.compute_hillshade(dem)
        results["drainage"] = self.analyze_drainage(dem)

        return results

    def get_terrain_assessment(self, dem: Any) -> Dict[str, Any]:
        """Generate comprehensive terrain assessment."""
        all_products = self.compute_all_products(dem)

        slope_data = all_products.get("slope", {})
        aspect_data = all_products.get("aspect", {})
        drainage_data = all_products.get("drainage", {})

        slope_stats = slope_data.get("statistics", {})
        mean_slope = slope_stats.get("mean", 0)

        accessibility = "good" if mean_slope < 10 else "moderate" if mean_slope < 25 else "poor"
        pit_wall_stability = "stable" if mean_slope < 20 else "moderate_risk" if mean_slope < 35 else "high_risk"

        zones = slope_data.get("zones", {})
        flat_area_percent = 0
        total = sum(zones.values()) if zones else 1
        if total > 0:
            flat_area_percent = (zones.get("flat", 0) + zones.get("gentle", 0)) / total * 100

        return {
            "summary": {
                "mean_slope": mean_slope,
                "accessibility": accessibility,
                "pit_wall_stability": pit_wall_stability,
                "flat_area_percent": flat_area_percent,
                "dominant_aspect": aspect_data.get("statistics", {}).get("dominant_direction", "unknown"),
                "drainage_features": drainage_data.get("statistics", {}).get("num_drainage_lines", 0)
            },
            "products": all_products,
            "recommendations": self._generate_terrain_recommendations(mean_slope, flat_area_percent, accessibility),
            "mining_considerations": self._generate_mining_considerations(all_products)
        }

    def _interpret_slope(self, mean_slope: float) -> str:
        """Interpret mean slope value."""
        if mean_slope < 2:
            return "Very flat terrain - ideal for infrastructure and waste dumps"
        elif mean_slope < 5:
            return "Gently undulating - good for mining operations"
        elif mean_slope < 15:
            return "Moderate slopes - may require cut and fill"
        elif mean_slope < 30:
            return "Steep terrain - significant earthworks required"
        else:
            return "Very steep terrain - challenging for mining access"

    def _generate_terrain_recommendations(self, mean_slope: float, flat_percent: float, accessibility: str) -> List[str]:
        """Generate terrain-based recommendations."""
        recs = []

        if mean_slope > 20:
            recs.append("Steep terrain detected. Consider switchback access roads and terracing for waste dumps.")
        if flat_percent < 10:
            recs.append("Limited flat areas. Consider landform optimization and progressive rehabilitation.")
        if accessibility == "poor":
            recs.append("Poor accessibility. Evaluate conveyor vs truck haulage economics.")
        if mean_slope < 5:
            recs.append("Flat terrain suitable for process plant and infrastructure placement.")
        if flat_percent > 50:
            recs.append("Extensive flat areas available for waste storage and facilities.")

        return recs

    def _generate_mining_considerations(self, products: Dict) -> Dict[str, str]:
        """Generate mining-specific considerations from terrain analysis."""
        considerations = {}

        slope = products.get("slope", {})
        slope_mean = slope.get("statistics", {}).get("mean", 0)

        if slope_mean > 30:
            considerations["wall_stability"] = "High slopes detected. Detailed geotechnical investigation recommended."
        if slope_mean < 5:
            considerations["infrastructure"] = "Flat terrain suitable for major infrastructure placement."

        drainage = products.get("drainage", {})
        density = drainage.get("statistics", {}).get("drainage_density_km_per_km2", 0)
        if density > 2:
            considerations["water_management"] = "High drainage density. Robust water management infrastructure required."
        if density < 0.5:
            considerations["water_management"] = "Low drainage density. Limited natural drainage - assess water supply."

        return considerations
