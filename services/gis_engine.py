"""
GIS Spatial Engine for Mining Operations
Spatial queries, coordinate systems, proximity analysis, and map algebra.
"""

import math
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SpatialOperation(Enum):
    BUFFER = "buffer"
    INTERSECT = "intersect"
    UNION = "union"
    CLIP = "clip"
    NEAREST = "nearest"
    WITHIN_DISTANCE = "within_distance"
    CONTAINS = "contains"


@dataclass
class SpatialPoint:
    x: float
    y: float
    z: Optional[float] = None
    crs: str = "EPSG:4326"
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialLine:
    points: List[SpatialPoint]
    length_m: Optional[float] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialPolygon:
    vertices: List[SpatialPoint]
    area_km2: Optional[float] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialResult:
    operation: SpatialOperation
    input_count: int
    result_count: int
    result: Any
    metadata: Dict[str, Any]


class CoordinateTransformer:
    """Transform coordinates between different CRS."""

    @staticmethod
    def wgs84_to_utm(longitude: float, latitude: float) -> Tuple[str, float, float]:
        """Convert WGS84 lon/lat to UTM coordinates."""
        zone = int((longitude + 180) / 6) + 1
        hemisphere = "north" if latitude >= 0 else "south"

        lat_rad = math.radians(latitude)
        long_rad = math.radians(longitude)

        k0 = 0.9996
        e = 0.00669438
        e2 = e * e
        ep2 = e2 / (1 - e2)
        N = 6378137 / math.sqrt(1 - e * math.sin(lat_rad)**2)
        T = math.tan(lat_rad)**2
        C = ep2 * math.cos(lat_rad)**2
        A = math.cos(lat_rad) * (long_rad - math.radians((zone - 1) * 6 - 180))

        M = 6378137 * (
            (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_rad -
            (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_rad) +
            (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_rad) -
            (35*e2**3/3072) * math.sin(6*lat_rad)
        )

        x = k0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58*ep2)*A**5/120) + 500000
        y = k0 * (M + N * math.tan(lat_rad) * (A**2/2 + (5-T+9*C+4*C**2)*A**4/24 + (61-58*T+T**2+600*C-330*ep2)*A**6/720))

        if hemisphere == "south":
            y += 10000000

        return f"EPSG:{32600 + zone if hemisphere == 'north' else 32700 + zone}", x, y

    @staticmethod
    def utm_to_wgs84(easting: float, northing: float, zone: int, hemisphere: str = "north") -> Tuple[float, float]:
        """Convert UTM to WGS84 lon/lat."""
        k0 = 0.9996
        e = 0.00669438
        e2 = e * e
        ep2 = e2 / (1 - e2)

        if hemisphere == "south":
            northing -= 10000000

        M = northing / k0
        mu = M / (6378137 * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))

        e1 = (1 - math.sqrt(1-e2)) / (1 + math.sqrt(1-e2))
        phi1 = mu + (3*e1/2 - 27*e1**3/32) * math.sin(2*mu) + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu)

        N1 = 6378137 / math.sqrt(1 - e * math.sin(phi1)**2)
        T1 = math.tan(phi1)**2
        C1 = ep2 * math.cos(phi1)**2
        R1 = 6378137 * (1 - e2) / (1 - e * math.sin(phi1)**2)**1.5
        D = (easting - 500000) / (N1 * k0)

        latitude = phi1 - (N1 * math.tan(phi1) / R1) * (D**2/2 - (5+3*T1+10*C1-4*C1**2-9*ep2)*D**4/24 + (61+90*T1+298*C1+45*T1**2-252*ep2-3*C1**2)*D**6/720)
        longitude = (zone - 1) * 6 - 180 + (D - (1+2*T1+C1)*D**3/6 + (5-2*C1+28*T1-3*C1**2+8*ep2+24*T1**2)*D**5/120) / math.cos(phi1)

        return math.degrees(longitude), math.degrees(latitude)


class SpatialEngine:
    """GIS spatial operations engine."""

    def __init__(self):
        self.transformer = CoordinateTransformer()

    def haversine_distance(self, point1: SpatialPoint, point2: SpatialPoint) -> float:
        """Calculate distance between two WGS84 points in meters."""
        R = 6371000

        lat1 = math.radians(point1.y)
        lat2 = math.radians(point2.y)
        dlat = math.radians(point2.y - point1.y)
        dlon = math.radians(point2.x - point1.x)

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def buffer_point(self, center: SpatialPoint, radius_m: float, num_vertices: int = 32) -> SpatialPolygon:
        """Create a circular buffer around a point."""
        vertices = []
        for i in range(num_vertices):
            angle = 2 * math.pi * i / num_vertices
            dx = radius_m * math.cos(angle)
            dy = radius_m * math.sin(angle)

            lat_offset = dy / 111320
            lon_offset = dx / (111320 * math.cos(math.radians(center.y)))

            vertices.append(SpatialPoint(
                x=center.x + lon_offset,
                y=center.y + lat_offset,
                crs=center.crs
            ))

        return SpatialPolygon(
            vertices=vertices,
            area_km2=math.pi * (radius_m/1000)**2,
            properties={"center": (center.x, center.y), "radius_m": radius_m}
        )

    def find_nearest_points(self, target: SpatialPoint, points: List[SpatialPoint], k: int = 1) -> List[Dict]:
        """Find k nearest points to target."""
        distances = []
        for p in points:
            dist = self.haversine_distance(target, p)
            distances.append({"point": p, "distance_m": dist})

        distances.sort(key=lambda d: d["distance_m"])
        return distances[:k]

    def points_within_distance(self, center: SpatialPoint, points: List[SpatialPoint],
                               distance_m: float) -> List[Dict]:
        """Find all points within a distance of center."""
        results = []
        for p in points:
            dist = self.haversine_distance(center, p)
            if dist <= distance_m:
                results.append({"point": p, "distance_m": dist})
        results.sort(key=lambda d: d["distance_m"])
        return results

    def line_length(self, line: SpatialLine) -> float:
        """Calculate length of a polyline in meters."""
        total = 0
        for i in range(len(line.points) - 1):
            total += self.haversine_distance(line.points[i], line.points[i+1])
        return total

    def polygon_area(self, polygon: SpatialPolygon) -> float:
        """Calculate area of a polygon in km² using Shoelace formula."""
        n = len(polygon.vertices)
        if n < 3:
            return 0

        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += polygon.vertices[i].x * polygon.vertices[j].y
            area -= polygon.vertices[j].x * polygon.vertices[i].y

        area = abs(area) / 2

        avg_lat = sum(v.y for v in polygon.vertices) / n
        area_km2 = area * (111.32 ** 2) * math.cos(math.radians(avg_lat))
        return area_km2

    def point_in_polygon(self, point: SpatialPoint, polygon: SpatialPolygon) -> bool:
        """Check if point is inside polygon using ray casting algorithm."""
        n = len(polygon.vertices)
        inside = False

        j = n - 1
        for i in range(n):
            vi = polygon.vertices[i]
            vj = polygon.vertices[j]

            if ((vi.y > point.y) != (vj.y > point.y)) and \
               (point.x < (vj.x - vi.x) * (point.y - vi.y) / (vj.y - vi.y) + vi.x):
                inside = not inside
            j = i

        return inside

    def calculate_azimuth(self, point1: SpatialPoint, point2: SpatialPoint) -> float:
        """Calculate azimuth (bearing) from point1 to point2 in degrees."""
        lat1 = math.radians(point1.y)
        lat2 = math.radians(point2.y)
        dlon = math.radians(point2.x - point1.x)

        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

        azimuth = math.degrees(math.atan2(y, x))
        return (azimuth + 360) % 360

    def generate_grid(self, bbox: 'BoundingBox', cell_size_m: float = 1000) -> List[SpatialPoint]:
        """Generate a regular grid of points within a bounding box."""
        points = []

        lat_step = cell_size_m / 111320
        lon_step = cell_size_m / (111320 * math.cos(math.radians((bbox.north + bbox.south) / 2)))

        y = bbox.south
        while y <= bbox.north:
            x = bbox.west
            while x <= bbox.east:
                points.append(SpatialPoint(x=x, y=y))
                x += lon_step
            y += lat_step

        return points

    def calculate_zonal_statistics(self, values: List[float], zones: List[int]) -> Dict[int, Dict[str, float]]:
        """Calculate statistics for each zone."""
        import statistics

        zone_values = {}
        for val, zone in zip(values, zones):
            if zone not in zone_values:
                zone_values[zone] = []
            zone_values[zone].append(val)

        stats = {}
        for zone, vals in zone_values.items():
            if vals:
                stats[zone] = {
                    "count": len(vals),
                    "mean": statistics.mean(vals),
                    "median": statistics.median(vals),
                    "min": min(vals),
                    "max": max(vals),
                    "std": statistics.stdev(vals) if len(vals) > 1 else 0
                }

        return stats

    def format_spatial_results(self, results: Dict[str, Any]) -> str:
        """Format spatial analysis results for display."""
        lines = ["## Spatial Analysis Results\n"]

        if "distance" in results:
            lines.append(f"**Distance:** {results['distance']:.1f} m ({results['distance']/1000:.2f} km)")
        if "nearest" in results:
            nearest = results["nearest"]
            lines.append(f"**Nearest Point:** {nearest['distance_m']:.1f} m away")
        if "within_distance" in results:
            count = results["within_distance"]
            lines.append(f"**Points within range:** {count}")
        if "area_km2" in results:
            lines.append(f"**Area:** {results['area_km2']:.2f} km²")

        return "\n".join(lines)


class SpatialQueryBuilder:
    """Builds and executes spatial queries."""

    def __init__(self, engine: SpatialEngine):
        self.engine = engine

    def nearest_deposit(self, target: SpatialPoint, deposits: List[Dict],
                        distance_key: str = "distance_m") -> Dict:
        """Find nearest mineral deposit to a target point."""
        points = [
            SpatialPoint(x=d["longitude"], y=d["latitude"], properties=d)
            for d in deposits if "longitude" in d and "latitude" in d
        ]

        nearest = self.engine.find_nearest_points(target, points, k=5)

        return {
            "target": {"longitude": target.x, "latitude": target.y},
            "nearest_deposits": [
                {
                    "name": n["point"].properties.get("name", "Unknown"),
                    "distance_m": n["distance_m"],
                    "type": n["point"].properties.get("type", "Unknown"),
                    "grade": n["point"].properties.get("grade", None)
                }
                for n in nearest
            ]
        }

    def exploration_area_assessment(self, center: SpatialPoint, radius_km: float,
                                   geological_features: List[Dict]) -> Dict:
        """Assess exploration area within radius of center."""
        radius_m = radius_km * 1000
        buffer = self.engine.buffer_point(center, radius_m)

        nearby_features = []
        for feature in geological_features:
            fp = SpatialPoint(x=feature["longitude"], y=feature["latitude"])
            dist = self.engine.haversine_distance(center, fp)
            if dist <= radius_m:
                nearby_features.append({
                    "name": feature.get("name", "Unknown"),
                    "type": feature.get("type", "Unknown"),
                    "distance_m": dist,
                    "azimuth": self.engine.calculate_azimuth(center, fp)
                })

        nearby_features.sort(key=lambda f: f["distance_m"])

        return {
            "center": {"longitude": center.x, "latitude": center.y},
            "radius_km": radius_km,
            "area_km2": buffer.area_km2,
            "features_within_area": len(nearby_features),
            "features": nearby_features,
            "summary": f"Found {len(nearby_features)} geological features within {radius_km} km radius"
        }

    def drill_hole_grid(self, bbox: 'BoundingBox', spacing_m: float = 100) -> List[Dict]:
        """Generate a regular drill hole grid within a bounding box."""
        grid_points = self.engine.generate_grid(bbox, spacing_m)

        drill_holes = []
        for i, point in enumerate(grid_points):
            drill_holes.append({
                "hole_id": f"DH-{i+1:04d}",
                "longitude": point.x,
                "latitude": point.y,
                "proposed_depth_m": 100,
                "grid_x": int((point.x - bbox.west) / (spacing_m / (111320 * math.cos(math.radians(point.y))))),
                "grid_y": int((point.y - bbox.south) / (spacing_m / 111320))
            })

        return {
            "spacing_m": spacing_m,
            "total_holes": len(drill_holes),
            "area_km2": bbox.area_km2(),
            "holes": drill_holes
        }
