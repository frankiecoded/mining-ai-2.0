"""
Export Engine for Satellite Analysis Results
GeoJSON, KML, CSV, and report generation for satellite data.
"""

import json
import csv
import logging
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GeoFeature:
    geometry_type: str
    coordinates: Any
    properties: Dict[str, Any]


class GeoJSONExporter:
    """Export analysis results as GeoJSON."""

    def create_point_feature(self, lon: float, lat: float, properties: Dict[str, Any]) -> Dict:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": properties
        }

    def create_polygon_feature(self, vertices: List[List[float]], properties: Dict[str, Any]) -> Dict:
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [vertices + [vertices[0]]]
            },
            "properties": properties
        }

    def create_line_feature(self, coordinates: List[List[float]], properties: Dict[str, Any]) -> Dict:
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": properties
        }

    def create_feature_collection(self, features: List[Dict]) -> Dict:
        return {
            "type": "FeatureCollection",
            "features": features
        }

    def export_exploration_targets(self, targets: List[Dict], crs: str = "EPSG:4326") -> Dict:
        features = []
        for t in targets:
            props = {k: v for k, v in t.items() if k not in ["location"]}
            features.append(self.create_point_feature(
                t.get("location", {}).get("lon", 0),
                t.get("location", {}).get("lat", 0),
                props
            ))
        return self.create_feature_collection(features)

    def export_drill_grid(self, grid_points: List[Dict], properties: Dict = None) -> Dict:
        features = []
        for pt in grid_points:
            props = {**pt, **(properties or {})}
            features.append(self.create_point_feature(pt["longitude"], pt["latitude"], props))
        return self.create_feature_collection(features)

    def export_lineaments(self, lineaments: List[Dict]) -> Dict:
        features = []
        for lm in lineaments:
            coords = []
            for pt in lm.get("points", []):
                if isinstance(pt, dict):
                    coords.append([pt.get("x", 0), pt.get("y", 0)])
                elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    coords.append([pt[0], pt[1]])

            if coords:
                props = {k: v for k, v in lm.items() if k != "points"}
                features.append(self.create_line_feature(coords, props))
        return self.create_feature_collection(features)

    def export_alteration_zones(self, zones: List[Dict]) -> Dict:
        features = []
        for z in zones:
            center = z.get("center", {})
            props = {k: v for k, v in z.items() if k != "center"}
            features.append(self.create_point_feature(
                center.get("lon", 0),
                center.get("lat", 0),
                props
            ))
        return self.create_feature_collection(features)

    def export_drainage_network(self, drainage: Dict) -> Dict:
        features = []
        if "stream_network" in drainage:
            for stream in drainage["stream_network"]:
                coords = [[s[0], s[1]] for s in stream.get("flow_path", [])]
                if coords:
                    features.append(self.create_line_feature(coords, {
                        "stream_id": stream.get("stream_id"),
                        "length": stream.get("length"),
                        "order": stream.get("order")
                    }))

        if "high_points" in drainage:
            for pt in drainage["high_points"]:
                features.append(self.create_point_feature(pt["x"], pt["y"], {
                    "height": pt["height"],
                    "rank": pt["rank"]
                }))

        return self.create_feature_collection(features)

    def export_terrain_zones(self, terrain: Dict) -> Dict:
        features = []
        if "zones" in terrain:
            for zone_name, zone_data in terrain["zones"].items():
                features.append(self.create_point_feature(0, 0, {
                    "zone": zone_name,
                    "count": zone_data,
                    "product": terrain.get("product", "unknown")
                }))
        return self.create_feature_collection(features)

    def export_to_file(self, geojson: Dict, filepath: str) -> str:
        with open(filepath, 'w') as f:
            json.dump(geojson, f, indent=2)
        return filepath


class KMLExporter:
    """Export analysis results as KML."""

    def create_kml(self, name: str, features: List[Dict], description: str = "") -> str:
        placemarks = []
        for f in features:
            geom_type = f.get("geometry", {}).get("type", "")
            coords = f.get("geometry", {}).get("coordinates", [])
            props = f.get("properties", {})
            desc_parts = [f"{k}: {v}" for k, v in props.items() if v is not None]
            desc_text = "\\n".join(desc_parts)

            if geom_type == "Point":
                lon, lat = coords[0], coords[1] if len(coords) > 1 else 0
                placemarks.append(f"""
    <Placemark>
      <name>{props.get('name', 'Feature')}</name>
      <description><![CDATA[{desc_text}]]></description>
      <Point><coordinates>{lon},{lat},0</coordinates></Point>
    </Placemark>""")

            elif geom_type == "LineString":
                coord_str = " ".join(f"{c[0]},{c[1]},0" for c in coords)
                placemarks.append(f"""
    <Placemark>
      <name>{props.get('name', 'Line')}</name>
      <description><![CDATA[{desc_text}]]></description>
      <LineString><coordinates>{coord_str}</coordinates></LineString>
    </Placemark>""")

            elif geom_type == "Polygon":
                ring = coords[0] if coords else []
                coord_str = " ".join(f"{c[0]},{c[1]},0" for c in ring)
                placemarks.append(f"""
    <Placemark>
      <name>{props.get('name', 'Area')}</name>
      <description><![CDATA[{desc_text}]]></description>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>{coord_str}</coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>""")

        placemarks_xml = "\n".join(placemarks)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <description>{description}</description>
    {placemarks_xml}
  </Document>
</kml>"""


class CSVExporter:
    """Export analysis results as CSV."""

    def export_feature_collection(self, geojson: Dict, filepath: str) -> str:
        features = geojson.get("features", [])
        if not features:
            return filepath

        all_keys = set()
        for f in features:
            all_keys.update(f.get("properties", {}).keys())
            geom = f.get("geometry", {})
            if geom.get("type") == "Point":
                all_keys.add("longitude")
                all_keys.add("latitude")

        fieldnames = sorted(all_keys)

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for feat in features:
                row = dict(feat.get("properties", {}))
                geom = feat.get("geometry", {})
                if geom.get("type") == "Point":
                    row["longitude"] = geom["coordinates"][0]
                    row["latitude"] = geom["coordinates"][1] if len(geom["coordinates"]) > 1 else 0
                writer.writerow(row)

        return filepath

    def export_time_series(self, time_series: List[Dict], filepath: str) -> str:
        if not time_series:
            return filepath

        fieldnames = list(time_series[0].keys())

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(time_series)

        return filepath


class ReportGenerator:
    """Generate formatted reports from satellite analysis results."""

    def generate_mineral_report(self, spectral: Dict, terrain: Dict, features: Dict, temporal: Dict = None) -> str:
        sections = []
        sections.append("# Satellite Remote Sensing Mineral Exploration Report\n")

        sections.append("## 1. Executive Summary\n")
        if "recommendation" in spectral:
            sections.append(f"**Recommendation:** {spectral['recommendation']}\n")
        if "alteration_level" in spectral:
            sections.append(f"**Alteration Intensity:** {spectral['alteration_level']} ({spectral.get('alteration_score', 0)}/100)")
        sections.append(f"**Confidence:** {spectral.get('confidence', 0):.1f}%\n")

        sections.append("## 2. Spectral Analysis\n")
        if "indices" in spectral:
            for name, idx in list(spectral["indices"].items())[:8]:
                interp = idx.get("interpretation", "N/A")
                sections.append(f"- **{idx.get('short_name', name)}:** {idx.get('mean_value', 0):.4f} ({interp})")
        sections.append("")

        sections.append("## 3. Terrain Analysis\n")
        if "statistics" in terrain:
            stats = terrain["statistics"]
            sections.append(f"- **Slope Range:** {stats.get('min', 0):.1f}° to {stats.get('max', 0):.1f}°")
            sections.append(f"- **Mean Slope:** {stats.get('mean', 0):.1f}°")
        if "zones" in terrain:
            zones = terrain["zones"]
            sections.append(f"- **Terrain Zones:** {json.dumps(zones)}")
        sections.append("")

        sections.append("## 4. Feature Extraction\n")
        if "lineaments" in features:
            lm = features["lineaments"]
            sections.append(f"- **Lineaments Detected:** {lm.get('count', 0)}")
            if "statistics" in lm:
                sections.append(f"  - Mean Length: {lm['statistics'].get('mean_length', 0):.0f}m")
                sections.append(f"  - Mean Orientation: {lm['statistics'].get('mean_orientation', 0):.1f}°")
        if "circular_features" in features:
            cf = features["circular_features"]
            sections.append(f"- **Circular Features:** {cf.get('count', 0)}")
        if "exploration_targets" in features:
            targets = features["exploration_targets"]
            sections.append(f"- **Exploration Targets:** {len(targets)}")
            for t in targets[:5]:
                sections.append(f"  - {t.get('type', 'unknown')}: {t.get('description', 'N/A')[:80]}")
        sections.append("")

        if temporal:
            sections.append("## 5. Temporal Analysis\n")
            if "overall_trend" in temporal:
                sections.append(f"- **Change Trend:** {temporal['overall_trend']}")
            if "temporal_changes" in temporal:
                for ch in temporal["temporal_changes"][:5]:
                    sections.append(f"- {ch.get('from_date', '')} → {ch.get('to_date', '')}: {ch.get('change_type', 'stable')} ({ch.get('change_percent', 0):.1f}% changed)")
            sections.append("")

        sections.append("## 6. Recommendations\n")
        sections.append("1. **Priority Drilling:** Target areas with high alteration scores + structural intersections")
        sections.append("2. **Ground Truthing:** Verify spectral anomalies with field mapping and rock/soil sampling")
        sections.append("3. **Follow-up Remote Sensing:** Higher resolution imagery for target areas")
        sections.append("4. **Geochemical Sampling:** Grid sampling in areas with clay/iron oxide anomalies")
        sections.append("5. **Structural Mapping:** Detailed mapping of lineament intersections\n")

        return "\n".join(sections)

    def generate_environmental_report(self, ndvi_timeseries: Dict, vegetation_stress: Dict, mining_impact: Dict) -> str:
        sections = []
        sections.append("# Environmental Monitoring Report - Satellite Analysis\n")

        sections.append("## 1. Vegetation Health\n")
        if "trend" in ndvi_timeseries:
            sections.append(f"**Overall Trend:** {ndvi_timeseries['trend']}")
        if "overall_mean" in ndvi_timeseries:
            sections.append(f"**Mean NDVI:** {ndvi_timeseries['overall_mean']:.4f}")
        if "anomalies_detected" in ndvi_timeseries:
            sections.append(f"**Anomaly Events:** {ndvi_timeseries['anomalies_detected']}")
        sections.append("")

        sections.append("## 2. Vegetation Stress\n")
        if "average_stress_percent" in vegetation_stress:
            sections.append(f"**Average Stress:** {vegetation_stress['average_stress_percent']:.1f}%")
        if "max_stress" in vegetation_stress:
            sections.append(f"**Peak Stress Date:** {vegetation_stress['max_stress'].get('date', 'N/A')}")
        if "stress_trend" in vegetation_stress:
            sections.append(f"**Stress Trend:** {vegetation_stress['stress_trend']}")
        sections.append("")

        sections.append("## 3. Mining Impact\n")
        if "period" in mining_impact:
            sections.append(f"**Monitoring Period:** {mining_impact['period']}")
        if "impacts" in mining_impact:
            veg = mining_impact["impacts"].get("vegetation", {})
            if veg:
                sections.append(f"- **Vegetation Loss:** {veg.get('loss_percent', 0):.2f}%")
                sections.append(f"- **Vegetation Gain:** {veg.get('gain_percent', 0):.2f}%")
        if "reclamation_status" in mining_impact:
            sections.append(f"**Reclamation Status:** {mining_impact['reclamation_status']}")
        sections.append("")

        sections.append("## 4. Recommendations\n")
        sections.append("1. Continue temporal monitoring to track vegetation recovery")
        sections.append("2. Investigate areas of significant vegetation loss")
        sections.append("3. Assess reclamation effectiveness with targeted sampling")
        sections.append("4. Compare with pre-mining baseline for impact quantification\n")

        return "\n".join(sections)

    def generate_terrain_report(self, terrain: Dict, drainage: Dict) -> str:
        sections = []
        sections.append("# Terrain and Drainage Analysis Report\n")

        sections.append("## 1. Terrain Characteristics\n")
        if "statistics" in terrain:
            stats = terrain["statistics"]
            sections.append(f"**Elevation Range:** {stats.get('min', 0):.1f}m to {stats.get('max', 0):.1f}m")
        if "interpretation" in terrain:
            sections.append(f"**Assessment:** {terrain['interpretation']}")
        sections.append("")

        sections.append("## 2. Drainage Network\n")
        if "stream_count" in drainage:
            sections.append(f"**Total Streams:** {drainage['stream_count']}")
        if "high_points" in drainage:
            sections.append(f"**Drainage Divides:** {len(drainage['high_points'])}")
        if "convergence_zones" in drainage:
            sections.append(f"**Convergence Zones:** {len(drainage['convergence_zones'])}")
        sections.append("")

        sections.append("## 3. Mining Implications\n")
        sections.append("- Slope stability assessment for pit walls and waste dumps")
        sections.append("- Access road planning and gradient requirements")
        sections.append("- Water management infrastructure placement")
        sections.append("- Tailings dam foundation assessment\n")

        return "\n".join(sections)
