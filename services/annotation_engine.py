"""
Satellite Image Annotation & Drawing Engine
Production backend service for the Mining AI Platform.

Provides 18 annotation types with GeoJSON export, auto-annotation pipelines,
and full CRUD operations per image.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AnnotationType(str, Enum):
    POINT = "POINT"
    LINE = "LINE"
    POLYGON = "POLYGON"
    RECTANGLE = "RECTANGLE"
    CIRCLE = "CIRCLE"
    ARROW = "ARROW"
    TEXT = "TEXT"
    MEASUREMENT = "MEASUREMENT"
    PROSPECT_ZONE = "PROSPECT_ZONE"
    HAZARD_ZONE = "HAZARD_ZONE"
    DRILL_TARGET = "DRILL_TARGET"
    LINEAMENT = "LINEAMENT"
    ALTERATION = "ALTERATION"
    WATER_BODY = "WATER_BODY"
    TAILINGS = "TAILINGS"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    VEGETATION_ANOMALY = "VEGETATION_ANOMALY"
    GEOLOGICAL_CONTACT = "GEOLOGICAL_CONTACT"


class HazardType(str, Enum):
    LANDSLIDE = "landslide"
    FLOOD = "flood"
    SUBSIDENCE = "subsidence"
    ACID_MINE_DRAINAGE = "acid_mine_drainage"
    DAM_FAILURE = "dam_failure"
    TOXIC_CONTAMINATION = "toxic_contamination"
    RADIOACTIVE = "radioactive"
    DUST_POLLUTION = "dust_pollution"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MeasurementUnit(str, Enum):
    METERS = "m"
    KILOMETERS = "km"
    FEET = "ft"
    MILES = "mi"


# ---------------------------------------------------------------------------
# Color palette per annotation type (hex + alpha)
# ---------------------------------------------------------------------------

ANNOTATION_COLORS: dict[AnnotationType, dict[str, str]] = {
    AnnotationType.POINT:                {"fill": "#FF0000", "stroke": "#CC0000", "alpha": "0.8"},
    AnnotationType.LINE:                 {"fill": "#FFFFFF", "stroke": "#FFFFFF", "alpha": "1.0"},
    AnnotationType.POLYGON:              {"fill": "#CCCCCC", "stroke": "#999999", "alpha": "0.4"},
    AnnotationType.RECTANGLE:            {"fill": "#3399FF", "stroke": "#3399FF", "alpha": "0.3"},
    AnnotationType.CIRCLE:               {"fill": "#FF9900", "stroke": "#FF9900", "alpha": "0.3"},
    AnnotationType.ARROW:                {"fill": "#00FF00", "stroke": "#00FF00", "alpha": "1.0"},
    AnnotationType.TEXT:                 {"fill": "#FFFFFF", "stroke": "#FFFFFF", "alpha": "1.0"},
    AnnotationType.MEASUREMENT:          {"fill": "#00FFFF", "stroke": "#00FFFF", "alpha": "1.0"},
    AnnotationType.PROSPECT_ZONE:        {"fill": "#FF0000", "stroke": "#CC0000", "alpha": "0.35"},
    AnnotationType.HAZARD_ZONE:          {"fill": "#FF4500", "stroke": "#CC3700", "alpha": "0.4"},
    AnnotationType.DRILL_TARGET:         {"fill": "#00CC00", "stroke": "#009900", "alpha": "0.6"},
    AnnotationType.LINEAMENT:            {"fill": "#FFD700", "stroke": "#CCB000", "alpha": "1.0"},
    AnnotationType.ALTERATION:           {"fill": "#FF00FF", "stroke": "#CC00CC", "alpha": "0.35"},
    AnnotationType.WATER_BODY:           {"fill": "#0066FF", "stroke": "#0052CC", "alpha": "0.45"},
    AnnotationType.TAILINGS:             {"fill": "#FF6633", "stroke": "#CC5229", "alpha": "0.4"},
    AnnotationType.INFRASTRUCTURE:       {"fill": "#888888", "stroke": "#666666", "alpha": "0.5"},
    AnnotationType.VEGETATION_ANOMALY:   {"fill": "#33CC33", "stroke": "#29A629", "alpha": "0.4"},
    AnnotationType.GEOLOGICAL_CONTACT:   {"fill": "#CC66FF", "stroke": "#A652CC", "alpha": "0.7"},
}

DEFAULT_STYLE = {"fill": "#CCCCCC", "stroke": "#999999", "strokeWidth": "2", "alpha": "0.5"}


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

@dataclass
class Coordinate:
    x: float
    y: float
    z: float | None = None

    def to_geojson(self) -> list[float]:
        coords: list[float] = [self.x, self.y]
        if self.z is not None:
            coords.append(self.z)
        return coords

    def to_dict(self) -> dict[str, float]:
        d: dict[str, float] = {"x": self.x, "y": self.y}
        if self.z is not None:
            d["z"] = self.z
        return d


@dataclass
class Style:
    fill_color: str = "#CCCCCC"
    stroke_color: str = "#999999"
    stroke_width: float = 2.0
    opacity: float = 0.5
    dash_array: str | None = None
    font_size: int = 14
    font_family: str = "Arial"
    icon: str | None = None
    icon_size: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "fill": self.fill_color,
            "stroke": self.stroke_color,
            "strokeWidth": self.stroke_width,
            "opacity": self.opacity,
            "fontSize": self.font_size,
            "fontFamily": self.font_family,
        }
        if self.dash_array is not None:
            d["dashArray"] = self.dash_array
        if self.icon is not None:
            d["icon"] = self.icon
            d["iconSize"] = self.icon_size
        return d


# ---------------------------------------------------------------------------
# Annotation
# ---------------------------------------------------------------------------

@dataclass
class Annotation:
    annotation_id: str
    annotation_type: AnnotationType
    image_id: str
    coordinates: list[Coordinate]
    properties: dict[str, Any]
    style: Style
    created_at: str
    updated_at: str
    author: str = "system"
    visible: bool = True
    locked: bool = False
    tags: list[str] = field(default_factory=list)

    # ---- serialisation helpers ------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotationId": self.annotation_id,
            "annotationType": self.annotation_type.value,
            "imageId": self.image_id,
            "coordinates": [c.to_dict() for c in self.coordinates],
            "properties": self.properties,
            "style": self.style.to_dict(),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "author": self.author,
            "visible": self.visible,
            "locked": self.locked,
            "tags": self.tags,
        }

    def to_geojson(self) -> dict[str, Any]:
        """Convert annotation to a GeoJSON Feature."""
        geom_type = _geojson_geometry_type(self.annotation_type)
        coords = _geojson_coordinates(self.annotation_type, self.coordinates)

        feature: dict[str, Any] = {
            "type": "Feature",
            "id": self.annotation_id,
            "geometry": {
                "type": geom_type,
                "coordinates": coords,
            },
            "properties": {
                **self.properties,
                "annotationType": self.annotation_type.value,
                "imageId": self.image_id,
                "author": self.author,
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
                "style": self.style.to_dict(),
                "visible": self.visible,
                "locked": self.locked,
                "tags": self.tags,
            },
        }
        return feature


def _geojson_geometry_type(atype: AnnotationType) -> str:
    mapping: dict[AnnotationType, str] = {
        AnnotationType.POINT: "Point",
        AnnotationType.LINE: "LineString",
        AnnotationType.POLYGON: "Polygon",
        AnnotationType.RECTANGLE: "Polygon",
        AnnotationType.CIRCLE: "Polygon",
        AnnotationType.ARROW: "LineString",
        AnnotationType.TEXT: "Point",
        AnnotationType.MEASUREMENT: "LineString",
        AnnotationType.PROSPECT_ZONE: "Polygon",
        AnnotationType.HAZARD_ZONE: "Polygon",
        AnnotationType.DRILL_TARGET: "Point",
        AnnotationType.LINEAMENT: "LineString",
        AnnotationType.ALTERATION: "Polygon",
        AnnotationType.WATER_BODY: "Polygon",
        AnnotationType.TAILINGS: "Polygon",
        AnnotationType.INFRASTRUCTURE: "Point",
        AnnotationType.VEGETATION_ANOMALY: "Polygon",
        AnnotationType.GEOLOGICAL_CONTACT: "LineString",
    }
    return mapping.get(atype, "Point")


def _geojson_coordinates(atype: AnnotationType, coords: list[Coordinate]) -> Any:
    if atype == AnnotationType.CIRCLE and len(coords) >= 2:
        center = coords[0]
        edge = coords[1]
        radius = math.hypot(edge.x - center.x, edge.y - center.y)
        return _circle_to_polygon(center.x, center.y, radius, segments=64)

    if atype == AnnotationType.RECTANGLE and len(coords) >= 2:
        return _rectangle_to_polygon(coords)

    if atype in (AnnotationType.POLYGON, AnnotationType.PROSPECT_ZONE,
                 AnnotationType.HAZARD_ZONE, AnnotationType.ALTERATION,
                 AnnotationType.WATER_BODY, AnnotationType.TAILINGS,
                 AnnotationType.VEGETATION_ANOMALY):
        ring = [c.to_geojson() for c in coords]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return [ring]

    if len(coords) == 1:
        return coords[0].to_geojson()

    return [c.to_geojson() for c in coords]


def _circle_to_polygon(cx: float, cy: float, radius: float, segments: int = 64) -> list[list[list[float]]]:
    points: list[list[float]] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        points.append([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
    points.append(points[0])
    return [points]


def _rectangle_to_polygon(coords: list[Coordinate]) -> list[list[list[float]]]:
    if len(coords) >= 4:
        ring = [c.to_geojson() for c in coords[:4]]
    else:
        c1 = coords[0]
        c2 = coords[1]
        ring = [
            [c1.x, c1.y],
            [c2.x, c1.y],
            [c2.x, c2.y],
            [c1.x, c2.y],
        ]
    ring.append(ring[0])
    return [ring]


def _build_style(type_: AnnotationType, overrides: dict[str, Any] | None = None) -> Style:
    palette = ANNOTATION_COLORS.get(type_, DEFAULT_STYLE)
    s = Style(
        fill_color=palette.get("fill", DEFAULT_STYLE["fill"]),
        stroke_color=palette.get("stroke", DEFAULT_STYLE["stroke"]),
        stroke_width=float(palette.get("strokeWidth", DEFAULT_STYLE["strokeWidth"])),
        opacity=float(palette.get("alpha", DEFAULT_STYLE["alpha"])),
    )
    if overrides:
        if "fill" in overrides:
            s.fill_color = overrides["fill"]
        if "stroke" in overrides:
            s.stroke_color = overrides["stroke"]
        if "strokeWidth" in overrides:
            s.stroke_width = float(overrides["strokeWidth"])
        if "opacity" in overrides:
            s.opacity = float(overrides["opacity"])
        if "dashArray" in overrides:
            s.dash_array = overrides["dashArray"]
        if "fontSize" in overrides:
            s.font_size = int(overrides["fontSize"])
        if "fontFamily" in overrides:
            s.font_family = overrides["fontFamily"]
        if "icon" in overrides:
            s.icon = overrides["icon"]
        if "iconSize" in overrides:
            s.icon_size = float(overrides["iconSize"])
    return s


def _generate_id() -> str:
    raw = f"{uuid.uuid4().hex}{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# AnnotationEngine
# ---------------------------------------------------------------------------

class AnnotationEngine:
    """Core annotation engine – stores annotations per image and provides
    CRUD, GeoJSON export, and auto-annotation pipelines."""

    def __init__(self) -> None:
        self._annotations: dict[str, list[Annotation]] = {}  # image_id -> list

    # ---- internal helpers -----------------------------------------------------

    def _store(self, annotation: Annotation) -> Annotation:
        self._annotations.setdefault(annotation.image_id, []).append(annotation)
        logger.info(
            "Stored %s annotation %s for image %s",
            annotation.annotation_type.value,
            annotation.annotation_id,
            annotation.image_id,
        )
        return annotation

    def _get_image_annotations(self, image_id: str) -> list[Annotation]:
        return self._annotations.get(image_id, [])

    # ---- CRUD ----------------------------------------------------------------

    def list_annotations(self, image_id: str) -> list[Annotation]:
        return list(self._get_image_annotations(image_id))

    def get_annotation(self, image_id: str, annotation_id: str) -> Annotation | None:
        for a in self._get_image_annotations(image_id):
            if a.annotation_id == annotation_id:
                return a
        return None

    def delete_annotation(self, image_id: str, annotation_id: str) -> bool:
        anns = self._annotations.get(image_id, [])
        for i, a in enumerate(anns):
            if a.annotation_id == annotation_id:
                anns.pop(i)
                logger.info("Deleted annotation %s from image %s", annotation_id, image_id)
                return True
        return False

    def update_annotation_properties(
        self, image_id: str, annotation_id: str, properties: dict[str, Any]
    ) -> Annotation | None:
        ann = self.get_annotation(image_id, annotation_id)
        if ann is None:
            return None
        ann.properties.update(properties)
        ann.updated_at = _now_iso()
        return ann

    def update_annotation_style(
        self, image_id: str, annotation_id: str, style_overrides: dict[str, Any]
    ) -> Annotation | None:
        ann = self.get_annotation(image_id, annotation_id)
        if ann is None:
            return None
        new_style = _build_style(ann.annotation_type, style_overrides)
        ann.style = new_style
        ann.updated_at = _now_iso()
        return ann

    def toggle_visibility(self, image_id: str, annotation_id: str) -> Annotation | None:
        ann = self.get_annotation(image_id, annotation_id)
        if ann is None:
            return None
        ann.visible = not ann.visible
        ann.updated_at = _now_iso()
        return ann

    def toggle_lock(self, image_id: str, annotation_id: str) -> Annotation | None:
        ann = self.get_annotation(image_id, annotation_id)
        if ann is None:
            return None
        ann.locked = not ann.locked
        ann.updated_at = _now_iso()
        return ann

    def add_tag(self, image_id: str, annotation_id: str, tag: str) -> Annotation | None:
        ann = self.get_annotation(image_id, annotation_id)
        if ann is None:
            return None
        if tag not in ann.tags:
            ann.tags.append(tag)
            ann.updated_at = _now_iso()
        return ann

    def remove_tag(self, image_id: str, annotation_id: str, tag: str) -> Annotation | None:
        ann = self.get_annotation(image_id, annotation_id)
        if ann is None:
            return None
        if tag in ann.tags:
            ann.tags.remove(tag)
            ann.updated_at = _now_iso()
        return ann

    def filter_by_type(self, image_id: str, annotation_type: AnnotationType) -> list[Annotation]:
        return [a for a in self._get_image_annotations(image_id) if a.annotation_type == annotation_type]

    def filter_by_tag(self, image_id: str, tag: str) -> list[Annotation]:
        return [a for a in self._get_image_annotations(image_id) if tag in a.tags]

    # ---- GeoJSON export -------------------------------------------------------

    def get_annotations_geojson(self, image_id: str) -> dict[str, Any]:
        anns = self._get_image_annotations(image_id)
        return {
            "type": "FeatureCollection",
            "features": [a.to_geojson() for a in anns],
        }

    def export_all(self) -> dict[str, Any]:
        all_features: list[dict[str, Any]] = []
        for image_id, anns in self._annotations.items():
            for a in anns:
                feature = a.to_geojson()
                feature["properties"]["imageId"] = image_id
                all_features.append(feature)
        return {"type": "FeatureCollection", "features": all_features}

    def export_as_json(self, image_id: str) -> str:
        return json.dumps(self.get_annotations_geojson(image_id), indent=2)

    def export_as_base64(self, image_id: str) -> str:
        payload = json.dumps(self.get_annotations_geojson(image_id)).encode()
        return base64.b64encode(payload).decode()

    # ===================================================================
    # Creator methods — mining-specific annotation types
    # ===================================================================

    def create_prospect_zone(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        minerals: list[str],
        confidence: float,
        rationale: str,
        source_method: str = "spectral_analysis",
        estimated_grade: float | None = None,
        depth_estimate: str | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "minerals": minerals,
            "confidence": confidence,
            "rationale": rationale,
            "sourceMethod": source_method,
            "estimatedGrade": estimated_grade,
            "depthEstimate": depth_estimate,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.PROSPECT_ZONE,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.PROSPECT_ZONE, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_drill_target(
        self,
        image_id: str,
        coordinate: Coordinate,
        minerals: list[str],
        confidence: float,
        rationale: str,
        proposed_depth: str | None = None,
        drill_method: str | None = None,
        priority: str = "medium",
        estimated_cost: float | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "minerals": minerals,
            "confidence": confidence,
            "rationale": rationale,
            "proposedDepth": proposed_depth,
            "drillMethod": drill_method,
            "priority": priority,
            "estimatedCost": estimated_cost,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.DRILL_TARGET,
            image_id=image_id,
            coordinates=[coordinate],
            properties=props,
            style=_build_style(AnnotationType.DRILL_TARGET, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_lineament(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        length: float | None = None,
        orientation: float | None = None,
        confidence: float = 0.5,
        description: str = "",
        source: str = "visual_interpretation",
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        if orientation is None and len(coordinates) >= 2:
            dx = coordinates[1].x - coordinates[0].x
            dy = coordinates[1].y - coordinates[0].y
            orientation = math.degrees(math.atan2(dy, dx)) % 360.0
        if length is None and len(coordinates) >= 2:
            length = math.hypot(
                coordinates[1].x - coordinates[0].x,
                coordinates[1].y - coordinates[0].y,
            )
        props: dict[str, Any] = {
            "length": length,
            "orientation": orientation,
            "confidence": confidence,
            "description": description,
            "source": source,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.LINEAMENT,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.LINEAMENT, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_alteration_zone(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        alteration_type: str,
        minerals: list[str],
        confidence: float,
        intensity: str = "moderate",
        description: str = "",
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "alterationType": alteration_type,
            "minerals": minerals,
            "confidence": confidence,
            "intensity": intensity,
            "description": description,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.ALTERATION,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.ALTERATION, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_measurement(
        self,
        image_id: str,
        start: Coordinate,
        end: Coordinate,
        label: str = "",
        unit: MeasurementUnit = MeasurementUnit.METERS,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        dist = math.hypot(end.x - start.x, end.y - start.y)
        unit_value = unit.value
        if unit == MeasurementUnit.KILOMETERS:
            dist_km = dist / 1000.0
            display = f"{dist_km:.2f} km"
        elif unit == MeasurementUnit.FEET:
            display = f"{dist * 3.28084:.1f} ft"
        elif unit == MeasurementUnit.MILES:
            display = f"{dist / 1609.34:.2f} mi"
        else:
            display = f"{dist:.2f} m"

        final_label = label if label else display
        props: dict[str, Any] = {
            "label": final_label,
            "distance": dist,
            "unit": unit_value,
            "displayValue": display,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.MEASUREMENT,
            image_id=image_id,
            coordinates=[start, end],
            properties=props,
            style=_build_style(AnnotationType.MEASUREMENT, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_hazard_zone(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        hazard_type: HazardType,
        risk_level: RiskLevel,
        description: str = "",
        affected_area: float | None = None,
        recommended_action: str = "",
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "hazardType": hazard_type.value,
            "riskLevel": risk_level.value,
            "description": description,
            "affectedArea": affected_area,
            "recommendedAction": recommended_action,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.HAZARD_ZONE,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.HAZARD_ZONE, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_geological_contact(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        rock_type_1: str,
        rock_type_2: str,
        contact_type: str = "sharp",
        confidence: float = 0.5,
        description: str = "",
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "rockType1": rock_type_1,
            "rockType2": rock_type_2,
            "contactType": contact_type,
            "confidence": confidence,
            "description": description,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.GEOLOGICAL_CONTACT,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.GEOLOGICAL_CONTACT, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_vegetation_anomaly(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        anomaly_type: str,
        ndvi_value: float | None = None,
        confidence: float = 0.5,
        possible_cause: str = "",
        area_hectares: float | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "anomalyType": anomaly_type,
            "ndviValue": ndvi_value,
            "confidence": confidence,
            "possibleCause": possible_cause,
            "areaHectares": area_hectares,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.VEGETATION_ANOMALY,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.VEGETATION_ANOMALY, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_tailings_boundary(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        dam_status: str = "active",
        estimated_volume: float | None = None,
        water_content: float | None = None,
        containment_risk: str = "low",
        description: str = "",
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "damStatus": dam_status,
            "estimatedVolume": estimated_volume,
            "waterContent": water_content,
            "containmentRisk": containment_risk,
            "description": description,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.TAILINGS,
            image_id=image_id,
            coordinates=coordinates,
            properties=props,
            style=_build_style(AnnotationType.TAILINGS, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_infrastructure_marker(
        self,
        image_id: str,
        coordinate: Coordinate,
        infrastructure_type: str,
        name: str = "",
        status: str = "active",
        capacity: str | None = None,
        description: str = "",
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        props: dict[str, Any] = {
            "infrastructureType": infrastructure_type,
            "name": name,
            "status": status,
            "capacity": capacity,
            "description": description,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.INFRASTRUCTURE,
            image_id=image_id,
            coordinates=[coordinate],
            properties=props,
            style=_build_style(AnnotationType.INFRASTRUCTURE, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_text_label(
        self,
        image_id: str,
        coordinate: Coordinate,
        text: str,
        font_size: int = 14,
        color: str = "#FFFFFF",
        background: bool = False,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        overrides = dict(style_overrides or {})
        overrides.setdefault("fontSize", font_size)
        overrides["fill"] = color
        props: dict[str, Any] = {
            "text": text,
            "fontSize": font_size,
            "color": color,
            "background": background,
        }
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.TEXT,
            image_id=image_id,
            coordinates=[coordinate],
            properties=props,
            style=_build_style(AnnotationType.TEXT, overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    # ---- custom generic creators ----------------------------------------------

    def create_custom_point(
        self,
        image_id: str,
        coordinate: Coordinate,
        properties: dict[str, Any] | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.POINT,
            image_id=image_id,
            coordinates=[coordinate],
            properties=properties or {},
            style=_build_style(AnnotationType.POINT, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_custom_polygon(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        properties: dict[str, Any] | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.POLYGON,
            image_id=image_id,
            coordinates=coordinates,
            properties=properties or {},
            style=_build_style(AnnotationType.POLYGON, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_custom_line(
        self,
        image_id: str,
        coordinates: list[Coordinate],
        properties: dict[str, Any] | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.LINE,
            image_id=image_id,
            coordinates=coordinates,
            properties=properties or {},
            style=_build_style(AnnotationType.LINE, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_custom_rectangle(
        self,
        image_id: str,
        top_left: Coordinate,
        bottom_right: Coordinate,
        properties: dict[str, Any] | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.RECTANGLE,
            image_id=image_id,
            coordinates=[top_left, bottom_right],
            properties=properties or {},
            style=_build_style(AnnotationType.RECTANGLE, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_custom_circle(
        self,
        image_id: str,
        center: Coordinate,
        radius: float,
        properties: dict[str, Any] | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        edge_point = Coordinate(x=center.x + radius, y=center.y)
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.CIRCLE,
            image_id=image_id,
            coordinates=[center, edge_point],
            properties={**(properties or {}), "radius": radius},
            style=_build_style(AnnotationType.CIRCLE, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    def create_custom_arrow(
        self,
        image_id: str,
        start: Coordinate,
        end: Coordinate,
        properties: dict[str, Any] | None = None,
        author: str = "system",
        style_overrides: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Annotation:
        dx = end.x - start.x
        dy = end.y - start.y
        annotation = Annotation(
            annotation_id=_generate_id(),
            annotation_type=AnnotationType.ARROW,
            image_id=image_id,
            coordinates=[start, end],
            properties={**(properties or {}), "direction": math.degrees(math.atan2(dy, dx)) % 360},
            style=_build_style(AnnotationType.ARROW, style_overrides),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author,
            tags=tags or [],
        )
        return self._store(annotation)

    # ===================================================================
    # Auto-annotation pipelines
    # ===================================================================

    def auto_annotate_spectral(
        self,
        spectral_results: dict[str, Any],
        image_id: str,
        author: str = "auto_spectral",
    ) -> list[Annotation]:
        """Create annotations from spectral analysis band-ratio / PCA results.

        Expected ``spectral_results`` shape::

            {
                "anomalies": [
                    {
                        "type": "ferric_oxide|clay|hydroxyl|...",
                        "confidence": 0.0-1.0,
                        "bbox": [x1, y1, x2, y2],
                        "centroid": [cx, cy],
                        "polygon": [[x,y], ...],   # optional
                        "minerals": [...],
                        "ndvi": ...,                # optional
                    }
                ],
                "method": "...",
            }
        """
        annotations: list[Annotation] = []
        method = spectral_results.get("method", "spectral_analysis")
        for anomaly in spectral_results.get("anomalies", []):
            confidence = float(anomaly.get("confidence", 0.5))
            minerals: list[str] = anomaly.get("minerals", [])
            anomaly_type: str = anomaly.get("type", "unknown")

            polygon_pts = anomaly.get("polygon")
            centroid = anomaly.get("centroid")
            bbox = anomaly.get("bbox")

            if polygon_pts and len(polygon_pts) >= 3:
                coords = [Coordinate(x=p[0], y=p[1]) for p in polygon_pts]
            elif centroid:
                coords = [Coordinate(x=centroid[0], y=centroid[1])]
            elif bbox and len(bbox) == 4:
                coords = [
                    Coordinate(x=bbox[0], y=bbox[1]),
                    Coordinate(x=bbox[2], y=bbox[3]),
                ]
            else:
                continue

            ndvi = anomaly.get("ndvi")
            tags = ["auto_spectral", anomaly_type]
            if ndvi is not None and ndvi < 0.2:
                tags.append("low_vegetation")

            if len(coords) >= 3:
                ann = self.create_alteration_zone(
                    image_id=image_id,
                    coordinates=coords,
                    alteration_type=anomaly_type,
                    minerals=minerals,
                    confidence=confidence,
                    intensity="strong" if confidence > 0.8 else "moderate" if confidence > 0.5 else "weak",
                    description=f"Auto-detected {anomaly_type} anomaly via {method}",
                    author=author,
                    tags=tags,
                )
            else:
                center = coords[0]
                ann = self.create_prospect_zone(
                    image_id=image_id,
                    coordinates=coords,
                    minerals=minerals,
                    confidence=confidence,
                    rationale=f"Spectral anomaly ({anomaly_type}) via {method}",
                    source_method=method,
                    author=author,
                    tags=tags,
                )
            annotations.append(ann)

        logger.info("Spectral auto-annotation produced %d annotations for image %s", len(annotations), image_id)
        return annotations

    def auto_annotate_terrain(
        self,
        terrain_results: dict[str, Any],
        image_id: str,
        author: str = "auto_terrain",
    ) -> list[Annotation]:
        """Create annotations from DEM / slope / aspect analysis.

        Expected ``terrain_results`` shape::

            {
                "lineaments": [
                    {"start": [x,y], "end": [x,y], "confidence": 0.0-1.0, "orientation": deg}
                ],
                "hazards": [
                    {"type": "landslide|subsidence|...", "polygon": [[x,y],...], "risk": "low|medium|high|critical"}
                ],
                "drainage": [
                    {"path": [[x,y], ...], "order": int}
                ]
            }
        """
        annotations: list[Annotation] = []

        for lin in terrain_results.get("lineaments", []):
            start = Coordinate(x=lin["start"][0], y=lin["start"][1])
            end = Coordinate(x=lin["end"][0], y=lin["end"][1])
            confidence = float(lin.get("confidence", 0.5))
            orientation = lin.get("orientation")
            ann = self.create_lineament(
                image_id=image_id,
                coordinates=[start, end],
                confidence=confidence,
                orientation=orientation,
                description="Auto-detected terrain lineament",
                source="dem_analysis",
                author=author,
                tags=["auto_terrain", "lineament"],
            )
            annotations.append(ann)

        risk_map = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM,
                    "high": RiskLevel.HIGH, "critical": RiskLevel.CRITICAL}
        hazard_map = {"landslide": HazardType.LANDSLIDE, "subsidence": HazardType.SUBSIDENCE,
                      "flood": HazardType.FLOOD, "acid_mine_drainage": HazardType.ACID_MINE_DRAINAGE,
                      "dam_failure": HazardType.DAM_FAILURE}

        for haz in terrain_results.get("hazards", []):
            poly = haz.get("polygon", [])
            if not poly:
                continue
            coords = [Coordinate(x=p[0], y=p[1]) for p in poly]
            htype = hazard_map.get(haz.get("type", ""), HazardType.LANDSLIDE)
            risk = risk_map.get(haz.get("risk", "medium"), RiskLevel.MEDIUM)
            ann = self.create_hazard_zone(
                image_id=image_id,
                coordinates=coords,
                hazard_type=htype,
                risk_level=risk,
                description=f"Auto-detected terrain hazard ({htype.value})",
                author=author,
                tags=["auto_terrain", "hazard"],
            )
            annotations.append(ann)

        for drain in terrain_results.get("drainage", []):
            path = drain.get("path", [])
            if len(path) < 2:
                continue
            coords = [Coordinate(x=p[0], y=p[1]) for p in path]
            ann = self.create_custom_line(
                image_id=image_id,
                coordinates=coords,
                properties={
                    "category": "drainage",
                    "streamOrder": drain.get("order", 1),
                },
                author=author,
                style_overrides={"fill": "#0066FF", "stroke": "#0066FF"},
                tags=["auto_terrain", "drainage"],
            )
            annotations.append(ann)

        logger.info("Terrain auto-annotation produced %d annotations for image %s", len(annotations), image_id)
        return annotations

    def auto_annotate_features(
        self,
        feature_results: dict[str, Any],
        image_id: str,
        author: str = "auto_features",
    ) -> list[Annotation]:
        """Create annotations from object-detection / feature-extraction results.

        Expected ``feature_results`` shape::

            {
                "features": [
                    {
                        "type": "infrastructure|water|vegetation_anomaly|tailings|...",
                        "bbox": [x1, y1, x2, y2] | null,
                        "polygon": [[x,y],...] | null,
                        "centroid": [cx, cy],
                        "confidence": 0.0-1.0,
                        "label": "...",
                        "metadata": {...}
                    }
                ]
            }
        """
        annotations: list[Annotation] = []

        for feat in feature_results.get("features", []):
            feat_type: str = feat.get("type", "unknown")
            confidence = float(feat.get("confidence", 0.5))
            label = feat.get("label", feat_type)
            meta = feat.get("metadata", {})
            polygon_pts = feat.get("polygon")
            bbox = feat.get("bbox")
            centroid = feat.get("centroid")

            if polygon_pts and len(polygon_pts) >= 3:
                coords = [Coordinate(x=p[0], y=p[1]) for p in polygon_pts]
            elif centroid:
                coords = [Coordinate(x=centroid[0], y=centroid[1])]
            elif bbox and len(bbox) == 4:
                coords = [
                    Coordinate(x=bbox[0], y=bbox[1]),
                    Coordinate(x=bbox[2], y=bbox[3]),
                ]
            else:
                continue

            if feat_type == "water" or feat_type == "water_body":
                ann = self.create_custom_polygon(
                    image_id=image_id,
                    coordinates=coords,
                    properties={"label": label, "confidence": confidence, **meta},
                    author=author,
                    style_overrides={"fill": "#0066FF", "stroke": "#0052CC", "opacity": 0.45},
                    tags=["auto_features", "water"],
                )
            elif feat_type == "tailings":
                ann = self.create_tailings_boundary(
                    image_id=image_id,
                    coordinates=coords,
                    description=label,
                    author=author,
                    tags=["auto_features", "tailings"],
                )
            elif feat_type == "vegetation_anomaly" or feat_type == "vegetation":
                ann = self.create_vegetation_anomaly(
                    image_id=image_id,
                    coordinates=coords,
                    anomaly_type=label,
                    confidence=confidence,
                    possible_cause=meta.get("cause", ""),
                    author=author,
                    tags=["auto_features", "vegetation"],
                )
            elif feat_type == "infrastructure":
                center = coords[0] if len(coords) == 1 else coords[len(coords) // 2]
                ann = self.create_infrastructure_marker(
                    image_id=image_id,
                    coordinate=center,
                    infrastructure_type=label,
                    name=meta.get("name", ""),
                    author=author,
                    tags=["auto_features", "infrastructure"],
                )
            elif feat_type in ("mineral_outcrop", "prospect"):
                ann = self.create_prospect_zone(
                    image_id=image_id,
                    coordinates=coords,
                    minerals=meta.get("minerals", []),
                    confidence=confidence,
                    rationale=label,
                    source_method="feature_detection",
                    author=author,
                    tags=["auto_features", "prospect"],
                )
            else:
                if len(coords) >= 3:
                    ann = self.create_custom_polygon(
                        image_id=image_id,
                        coordinates=coords,
                        properties={"label": label, "confidence": confidence, **meta},
                        author=author,
                        tags=["auto_features", feat_type],
                    )
                elif len(coords) == 1:
                    ann = self.create_custom_point(
                        image_id=image_id,
                        coordinate=coords[0],
                        properties={"label": label, "confidence": confidence, **meta},
                        author=author,
                        tags=["auto_features", feat_type],
                    )
                else:
                    ann = self.create_custom_line(
                        image_id=image_id,
                        coordinates=coords,
                        properties={"label": label, "confidence": confidence, **meta},
                        author=author,
                        tags=["auto_features", feat_type],
                    )
            annotations.append(ann)

        logger.info("Feature auto-annotation produced %d annotations for image %s", len(annotations), image_id)
        return annotations

    def auto_annotate_from_exploration_assessment(
        self,
        assessment: dict[str, Any],
        image_id: str,
        author: str = "auto_exploration",
    ) -> list[Annotation]:
        """Translate the structured output of ``spectral_analysis.py`` exploration
        assessment into a full set of mining annotations.

        Expected ``assessment`` shape (matching spectral_analysis output)::

            {
                "prospect_zones": [
                    {
                        "polygon": [[x,y], ...],
                        "minerals": [...],
                        "confidence": 0.0-1.0,
                        "rationale": "...",
                        "source_method": "...",
                        "estimated_grade": ... | null,
                        "depth_estimate": "..." | null
                    }
                ],
                "drill_targets": [
                    {
                        "centroid": [x, y],
                        "minerals": [...],
                        "confidence": 0.0-1.0,
                        "rationale": "...",
                        "proposed_depth": "..." | null,
                        "drill_method": "..." | null,
                        "priority": "low|medium|high|critical"
                    }
                ],
                "alteration_zones": [
                    {
                        "polygon": [[x,y], ...],
                        "alteration_type": "...",
                        "minerals": [...],
                        "confidence": 0.0-1.0,
                        "intensity": "weak|moderate|strong"
                    }
                ],
                "lineaments": [
                    {
                        "start": [x, y],
                        "end": [x, y],
                        "confidence": 0.0-1.0,
                        "description": "..."
                    }
                ],
                "hazard_zones": [
                    {
                        "polygon": [[x,y], ...],
                        "hazard_type": "landslide|flood|subsidence|...",
                        "risk_level": "low|medium|high|critical",
                        "description": "...",
                        "recommended_action": "..."
                    }
                ],
                "spectral_summary": { ... },
                "terrain_summary": { ... }
            }
        """
        annotations: list[Annotation] = []
        risk_map = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM,
                    "high": RiskLevel.HIGH, "critical": RiskLevel.CRITICAL}
        hazard_map = {
            "landslide": HazardType.LANDSLIDE, "flood": HazardType.FLOOD,
            "subsidence": HazardType.SUBSIDENCE,
            "acid_mine_drainage": HazardType.ACID_MINE_DRAINAGE,
            "dam_failure": HazardType.DAM_FAILURE,
            "toxic_contamination": HazardType.TOXIC_CONTAMINATION,
            "radioactive": HazardType.RADIOACTIVE,
            "dust_pollution": HazardType.DUST_POLLUTION,
        }

        # ---- prospect zones ---------------------------------------------------
        for pz in assessment.get("prospect_zones", []):
            poly = pz.get("polygon", [])
            if not poly:
                continue
            coords = [Coordinate(x=p[0], y=p[1]) for p in poly]
            ann = self.create_prospect_zone(
                image_id=image_id,
                coordinates=coords,
                minerals=pz.get("minerals", []),
                confidence=float(pz.get("confidence", 0.5)),
                rationale=pz.get("rationale", ""),
                source_method=pz.get("source_method", "exploration_assessment"),
                estimated_grade=pz.get("estimated_grade"),
                depth_estimate=pz.get("depth_estimate"),
                author=author,
                tags=["exploration_assessment", "prospect_zone"],
            )
            annotations.append(ann)

        # ---- drill targets ----------------------------------------------------
        for dt in assessment.get("drill_targets", []):
            centroid = dt.get("centroid")
            if not centroid:
                continue
            coord = Coordinate(x=centroid[0], y=centroid[1])
            ann = self.create_drill_target(
                image_id=image_id,
                coordinate=coord,
                minerals=dt.get("minerals", []),
                confidence=float(dt.get("confidence", 0.5)),
                rationale=dt.get("rationale", ""),
                proposed_depth=dt.get("proposed_depth"),
                drill_method=dt.get("drill_method"),
                priority=dt.get("priority", "medium"),
                author=author,
                tags=["exploration_assessment", "drill_target"],
            )
            annotations.append(ann)

        # ---- alteration zones -------------------------------------------------
        for az in assessment.get("alteration_zones", []):
            poly = az.get("polygon", [])
            if not poly:
                continue
            coords = [Coordinate(x=p[0], y=p[1]) for p in poly]
            ann = self.create_alteration_zone(
                image_id=image_id,
                coordinates=coords,
                alteration_type=az.get("alteration_type", "unknown"),
                minerals=az.get("minerals", []),
                confidence=float(az.get("confidence", 0.5)),
                intensity=az.get("intensity", "moderate"),
                description=f"Alteration zone from exploration assessment",
                author=author,
                tags=["exploration_assessment", "alteration"],
            )
            annotations.append(ann)

        # ---- lineaments -------------------------------------------------------
        for lm in assessment.get("lineaments", []):
            start_pt = lm.get("start")
            end_pt = lm.get("end")
            if not start_pt or not end_pt:
                continue
            coords = [Coordinate(x=start_pt[0], y=start_pt[1]),
                       Coordinate(x=end_pt[0], y=end_pt[1])]
            ann = self.create_lineament(
                image_id=image_id,
                coordinates=coords,
                confidence=float(lm.get("confidence", 0.5)),
                description=lm.get("description", "Lineament from exploration assessment"),
                source="exploration_assessment",
                author=author,
                tags=["exploration_assessment", "lineament"],
            )
            annotations.append(ann)

        # ---- hazard zones -----------------------------------------------------
        for hz in assessment.get("hazard_zones", []):
            poly = hz.get("polygon", [])
            if not poly:
                continue
            coords = [Coordinate(x=p[0], y=p[1]) for p in poly]
            htype = hazard_map.get(hz.get("hazard_type", ""), HazardType.LANDSLIDE)
            risk = risk_map.get(hz.get("risk_level", ""), RiskLevel.MEDIUM)
            ann = self.create_hazard_zone(
                image_id=image_id,
                coordinates=coords,
                hazard_type=htype,
                risk_level=risk,
                description=hz.get("description", ""),
                recommended_action=hz.get("recommended_action", ""),
                author=author,
                tags=["exploration_assessment", "hazard"],
            )
            annotations.append(ann)

        logger.info(
            "Exploration-assessment auto-annotation produced %d annotations for image %s",
            len(annotations),
            image_id,
        )
        return annotations

    # ---- utility ---------------------------------------------------------------

    def clear_image(self, image_id: str) -> int:
        count = len(self._annotations.get(image_id, []))
        self._annotations.pop(image_id, None)
        logger.info("Cleared %d annotations for image %s", count, image_id)
        return count

    def annotation_count(self, image_id: str | None = None) -> int:
        if image_id is not None:
            return len(self._get_image_annotations(image_id))
        return sum(len(v) for v in self._annotations.values())

    def image_ids(self) -> list[str]:
        return list(self._annotations.keys())

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for anns in self._annotations.values():
            for a in anns:
                counts[a.annotation_type.value] = counts.get(a.annotation_type.value, 0) + 1
        return {
            "totalAnnotations": self.annotation_count(),
            "totalImages": len(self._annotations),
            "byType": counts,
        }
