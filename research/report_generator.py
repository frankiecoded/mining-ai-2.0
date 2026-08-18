"""Satellite analysis report generator."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates comprehensive satellite analysis reports from multiple analysis results."""

    def generate_satellite_report(
        self,
        spectral: dict[str, Any],
        terrain: dict[str, Any],
        features: dict[str, Any],
        annotations: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        sections = []

        sections.append({
            "title": "Executive Summary",
            "content": self._generate_summary(spectral, terrain, features, annotations),
        })

        spectral_section = self._analyze_spectral(spectral)
        if spectral_section:
            sections.append({"title": "Spectral Analysis", "content": spectral_section})

        terrain_section = self._analyze_terrain(terrain)
        if terrain_section:
            sections.append({"title": "Terrain Analysis", "content": terrain_section})

        feature_section = self._analyze_features(features)
        if feature_section:
            sections.append({"title": "Feature Detection", "content": feature_section})

        annotation_section = self._analyze_annotations(annotations)
        if annotation_section:
            sections.append({"title": "Annotations", "content": annotation_section})

        mining_potential = self._assess_mining_potential(spectral, terrain, features)
        sections.append({"title": "Mining Potential Assessment", "content": mining_potential})

        return {
            "title": "Satellite Image Analysis Report",
            "sections": sections,
            "metadata": metadata,
        }

    def _generate_summary(self, spectral, terrain, features, annotations) -> str:
        parts = ["Satellite image analysis completed successfully."]

        if spectral and not spectral.get("error"):
            band_count = spectral.get("total_bands", 0)
            parts.append(f"Analyzed {band_count} spectral bands.")

            indices = spectral.get("spectral_indices", {})
            if "NDVI" in indices:
                ndvi_mean = indices["NDVI"]["mean"]
                parts.append(f"Mean NDVI: {ndvi_mean:.3f} ({self._ndvi_interpretation(ndvi_mean)}).")

        if terrain and not terrain.get("error"):
            elev = terrain.get("elevation", {})
            if elev:
                parts.append(
                    f"Elevation range: {elev.get('min', 0):.0f}m - {elev.get('max', 0):.0f}m "
                    f"(mean: {elev.get('mean', 0):.0f}m)."
                )

        if features and not features.get("error"):
            detections = features.get("detections", {})
            for det_type, det_data in detections.items():
                if isinstance(det_data, dict) and "percentage" in det_data:
                    parts.append(f"{det_type.replace('_', ' ').title()}: {det_data['percentage']:.1f}% coverage.")

        if annotations and not annotations.get("error"):
            count = annotations.get("count", 0)
            parts.append(f"{count} annotations created/loaded.")

        return " ".join(parts)

    def _analyze_spectral(self, spectral: dict) -> str:
        if spectral.get("error"):
            return f"Spectral analysis failed: {spectral['error']}"

        parts = []
        stats = spectral.get("band_statistics", {})
        for band, data in stats.items():
            parts.append(
                f"  {band}: range [{data.get('min', 0):.4f}, {data.get('max', 0):.4f}], "
                f"mean={data.get('mean', 0):.4f}"
            )

        indices = spectral.get("spectral_indices", {})
        if indices:
            parts.append("\nSpectral Indices:")
            for name, vals in indices.items():
                parts.append(f"  {name}: mean={vals.get('mean', 0):.4f}")

        return "\n".join(parts) if parts else "No spectral data available."

    def _analyze_terrain(self, terrain: dict) -> str:
        if terrain.get("error"):
            return f"Terrain analysis failed: {terrain['error']}"

        parts = []
        for key in ("elevation", "slope", "aspect"):
            data = terrain.get(key, {})
            if data:
                parts.append(f"  {key.title()}: {', '.join(f'{k}={v:.2f}' for k, v in data.items())}")

        return "\n".join(parts) if parts else "No terrain data available."

    def _analyze_features(self, features: dict) -> str:
        if features.get("error"):
            return f"Feature detection failed: {features['error']}"

        parts = []
        for det_type, det_data in features.get("detections", {}).items():
            if isinstance(det_data, dict) and "percentage" in det_data:
                parts.append(f"  {det_type}: {det_data['percentage']:.1f}% ({det_data.get('pixel_count', 0):,} pixels)")

        return "\n".join(parts) if parts else "No features detected."

    def _analyze_annotations(self, annotations: dict) -> str:
        if annotations.get("error"):
            return f"Annotations unavailable: {annotations['error']}"

        count = annotations.get("count", 0)
        if count == 0:
            return "No annotations present."

        parts = [f"Total annotations: {count}"]
        ann_list = annotations.get("annotations", [])
        type_counts: dict[str, int] = {}
        for ann in ann_list:
            t = ann.get("annotationType", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            parts.append(f"  {t}: {c}")

        return "\n".join(parts)

    def _assess_mining_potential(self, spectral, terrain, features) -> str:
        score = 0
        reasons = []

        if spectral and not spectral.get("error"):
            ndvi = spectral.get("spectral_indices", {}).get("NDVI", {})
            ndvi_mean = ndvi.get("mean", 0.5)
            if ndvi_mean < 0.2:
                score += 2
                reasons.append("Low vegetation (NDVI < 0.2) indicates exposed bedrock/saprolite")
            elif ndvi_mean < 0.4:
                score += 1
                reasons.append("Moderate vegetation with potential for geological exposure")

            bsi = spectral.get("spectral_indices", {}).get("BSI", {})
            bsi_mean = bsi.get("mean", 0)
            if bsi_mean > 0.1:
                score += 1
                reasons.append("Elevated bare soil index suggests mineral exposure")

        if terrain and not terrain.get("error"):
            slope = terrain.get("slope", {})
            slope_mean = slope.get("mean", 0)
            if slope_mean > 15:
                score += 1
                reasons.append("Moderate to steep terrain may indicate structural controls")

        if score >= 3:
            level = "HIGH"
        elif score >= 2:
            level = "MODERATE"
        elif score >= 1:
            level = "LOW"
        else:
            level = "VERY LOW"

        parts = [f"Overall Assessment: {level} potential"]
        parts.append(f"Score: {score}/4")
        if reasons:
            parts.append("Key findings:")
            for r in reasons:
                parts.append(f"  - {r}")
        parts.append("\nRecommendation: Ground-truthing recommended for all areas of interest.")

        return "\n".join(parts)

    @staticmethod
    def _ndvi_interpretation(value: float) -> str:
        if value > 0.6:
            return "dense vegetation"
        elif value > 0.4:
            return "moderate vegetation"
        elif value > 0.2:
            return "sparse vegetation"
        elif value > 0.0:
            return "bare soil/rock"
        else:
            return "water/cloud/shadow"
