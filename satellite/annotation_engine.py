"""Adapter: bridges main.py annotation endpoints to services/annotation_engine.py."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SatelliteAnnotationEngine:
    """Thin wrapper around services.annotation_engine.AnnotationEngine that matches
    the interface expected by the FastAPI endpoints in main.py."""

    def __init__(self):
        from services.annotation_engine import AnnotationEngine as _AE
        self._engine = _AE()

    def create_annotation(
        self,
        image_id: str,
        annotation_type: str,
        coordinates: list[dict],
        properties: dict[str, Any],
        style: Optional[dict] = None,
        author: str = "user",
    ) -> dict[str, Any]:
        from services.annotation_engine import (
            AnnotationType, Coordinate, _build_style, _generate_id, _now_iso, Annotation
        )

        type_map = {t.value: t for t in AnnotationType}
        atype = type_map.get(annotation_type.upper(), AnnotationType.POINT)

        coords = [Coordinate(x=c.get("x", 0), y=c.get("y", 0), z=c.get("z")) for c in coordinates]

        ann = Annotation(
            annotation_id=_generate_id(),
            annotation_type=atype,
            image_id=image_id,
            coordinates=coords,
            properties=properties,
            style=_build_style(atype),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            author=author or properties.get("author", "user"),
            tags=properties.get("tags", []),
        )
        stored = self._engine._store(ann)
        return stored.to_dict()

    def auto_annotate(
        self,
        image_id: str,
        analysis_type: str,
        results: dict[str, Any],
    ) -> dict[str, Any]:
        if analysis_type in ("spectral", "exploration"):
            anns = self._engine.auto_annotate_spectral(results, image_id)
        elif analysis_type == "terrain":
            anns = self._engine.auto_annotate_terrain(results, image_id)
        elif analysis_type == "features":
            anns = self._engine.auto_annotate_features(results, image_id)
        else:
            anns = []

        return {
            "image_id": image_id,
            "analysis_type": analysis_type,
            "annotations_created": len(anns),
            "annotations": [a.to_dict() for a in anns],
        }

    def get_annotations(self, image_id: str) -> dict[str, Any]:
        anns = self._engine.list_annotations(image_id)
        return {
            "image_id": image_id,
            "count": len(anns),
            "annotations": [a.to_dict() for a in anns],
            "geojson": self._engine.get_annotations_geojson(image_id),
        }

    def delete_annotation(self, image_id: str, annotation_id: str) -> dict[str, Any]:
        deleted = self._engine.delete_annotation(image_id, annotation_id)
        return {"deleted": deleted}

    def get_annotation_types(self) -> dict[str, Any]:
        from services.annotation_engine import AnnotationType
        types = []
        for t in AnnotationType:
            types.append({
                "value": t.value,
                "name": t.name,
            })
        return {"types": types, "count": len(types)}


AnnotationEngine = SatelliteAnnotationEngine
