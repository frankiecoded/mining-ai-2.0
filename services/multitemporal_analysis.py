"""
Multi-Temporal Analysis for Mining Remote Sensing
Change detection, time series analysis, and temporal pattern recognition.
"""

import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class TemporalImage:
    date: datetime
    bands: Dict[str, Any]
    cloud_cover: float = 0.0
    quality_score: float = 1.0


@dataclass
class ChangeResult:
    band: str
    change_magnitude: float
    change_type: str
    confidence: float
    pixels_affected: int
    description: str


class MultiTemporalAnalyzer:
    """Multi-temporal satellite analysis for mining monitoring."""

    def __init__(self):
        self.images: List[TemporalImage] = []

    def add_image(self, image: TemporalImage):
        self.images.append(image)
        self.images.sort(key=lambda x: x.date)

    def detect_changes(self, band: str, threshold: float = 0.2) -> Dict[str, Any]:
        """Detect changes between consecutive images for a band."""
        try:
            import numpy as np

            if len(self.images) < 2:
                return {"error": "Need at least 2 images for change detection"}

            changes = []
            for i in range(len(self.images) - 1):
                earlier = self.images[i]
                later = self.images[i + 1]

                if band not in earlier.bands or band not in later.bands:
                    continue

                arr1 = np.array(earlier.bands[band], dtype=np.float64)
                arr2 = np.array(later.bands[band], dtype=np.float64)

                if arr1.shape != arr2.shape:
                    arr2 = np.resize(arr2, arr1.shape)

                diff = arr2 - arr1
                magnitude = float(np.mean(np.abs(diff)))
                changed_pixels = int(np.sum(np.abs(diff) > threshold))
                total_pixels = diff.size

                change_type = "stable"
                if np.mean(diff) > threshold:
                    change_type = "increase"
                elif np.mean(diff) < -threshold:
                    change_type = "decrease"

                changes.append({
                    "from_date": earlier.date.isoformat(),
                    "to_date": later.date.isoformat(),
                    "change_magnitude": round(magnitude, 4),
                    "change_type": change_type,
                    "changed_pixels": changed_pixels,
                    "total_pixels": total_pixels,
                    "change_percent": round(changed_pixels / total_pixels * 100, 2) if total_pixels > 0 else 0,
                    "mean_diff": float(np.mean(diff)),
                    "max_change": float(np.max(np.abs(diff)))
                })

            return {
                "band": band,
                "threshold": threshold,
                "temporal_changes": changes,
                "overall_trend": self._compute_trend(changes),
                "image_count": len(self.images)
            }
        except ImportError:
            return {"error": "Change detection requires numpy"}

    def compute_ndvi_timeseries(self) -> Dict[str, Any]:
        """Compute NDVI time series across all images."""
        try:
            import numpy as np

            ndvi_values = []
            for img in self.images:
                if "NIR" in img.bands and "Red" in img.bands:
                    nir = np.array(img.bands["NIR"], dtype=np.float64)
                    red = np.array(img.bands["Red"], dtype=np.float64)
                    ndvi = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)
                    ndvi_values.append({
                        "date": img.date.isoformat(),
                        "mean_ndvi": float(np.mean(ndvi)),
                        "max_ndvi": float(np.max(ndvi)),
                        "min_ndvi": float(np.min(ndvi)),
                        "std_ndvi": float(np.std(ndvi)),
                        "cloud_cover": img.cloud_cover
                    })

            if len(ndvi_values) >= 2:
                values = [v["mean_ndvi"] for v in ndvi_values]
                trend = "stable"
                slope = (values[-1] - values[0]) / len(values)
                if slope > 0.01:
                    trend = "increasing"
                elif slope < -0.01:
                    trend = "decreasing"

                anomaly_images = [v for v in ndvi_values if v["mean_ndvi"] < np.mean(values) - 2 * np.std(values)]

                return {
                    "time_series": ndvi_values,
                    "trend": trend,
                    "slope_per_image": float(slope),
                    "overall_mean": float(np.mean(values)),
                    "overall_std": float(np.std(values)),
                    "anomalies_detected": len(anomaly_images),
                    "anomaly_dates": [a["date"] for a in anomaly_images]
                }

            return {"time_series": ndvi_values}
        except ImportError:
            return {"error": "NDVI time series requires numpy"}

    def detect_vegetation_stress(self) -> Dict[str, Any]:
        """Detect vegetation stress across the time series."""
        try:
            import numpy as np

            stress_maps = []
            for i, img in enumerate(self.images):
                if "NIR" in img.bands and "Red" in img.bands and "SWIR1" in img.bands:
                    nir = np.array(img.bands["NIR"], dtype=np.float64)
                    red = np.array(img.bands["Red"], dtype=np.float64)
                    swir1 = np.array(img.bands["SWIR1"], dtype=np.float64)

                    ndvi = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)
                    ndmi = np.where((nir + swir1) > 0, (nir - swir1) / (nir + swir1), 0)

                    stressed = (ndvi < 0.3) & (ndmi < 0.1)

                    stress_maps.append({
                        "date": img.date.isoformat(),
                        "stress_percent": float(np.sum(stressed) / stressed.size * 100),
                        "mean_ndvi": float(np.mean(ndvi)),
                        "mean_ndmi": float(np.mean(ndmi))
                    })

            if stress_maps:
                stress_pcts = [s["stress_percent"] for s in stress_maps]
                avg_stress = np.mean(stress_pcts)
                max_stress_date = stress_maps[stress_pcts.index(max(stress_pcts))]

                return {
                    "temporal_stress": stress_maps,
                    "average_stress_percent": float(avg_stress),
                    "max_stress": {
                        "date": max_stress_date["date"],
                        "percent": max_stress_date["stress_percent"]
                    },
                    "stress_trend": "worsening" if len(stress_pcts) > 1 and stress_pcts[-1] > stress_pcts[0] else "improving"
                }

            return {"error": "No images with required bands for vegetation stress analysis"}
        except ImportError:
            return {"error": "Vegetation stress requires numpy"}

    def detect_mining_impact(self) -> Dict[str, Any]:
        """Detect mining-related land cover changes."""
        try:
            import numpy as np

            if len(self.images) < 2:
                return {"error": "Need at least 2 images for mining impact detection"}

            first = self.images[0]
            last = self.images[-1]

            impacts = {}
            for band in ["NIR", "Red", "SWIR1", "SWIR2"]:
                if band in first.bands and band in last.bands:
                    arr1 = np.array(first.bands[band], dtype=np.float64)
                    arr2 = np.array(last.bands[band], dtype=np.float64)
                    diff = arr2 - arr1
                    impacts[band] = {
                        "mean_change": float(np.mean(diff)),
                        "percent_changed": float(np.sum(np.abs(diff) > 0.1) / diff.size * 100)
                    }

            if "NIR" in first.bands and "Red" in first.bands:
                nir1 = np.array(first.bands["NIR"], dtype=np.float64)
                red1 = np.array(first.bands["Red"], dtype=np.float64)
                ndvi1 = np.where((nir1 + red1) > 0, (nir1 - red1) / (nir1 + red1), 0)

                nir2 = np.array(last.bands["NIR"], dtype=np.float64)
                red2 = np.array(last.bands["Red"], dtype=np.float64)
                ndvi2 = np.where((nir2 + red2) > 0, (nir2 - red2) / (nir2 + red2), 0)

                vegetation_loss = np.sum((ndvi1 > 0.4) & (ndvi2 < 0.2))
                vegetation_gain = np.sum((ndvi1 < 0.2) & (ndvi2 > 0.4))
                total_pixels = ndvi1.size

                impacts["vegetation"] = {
                    "loss_pixels": int(vegetation_loss),
                    "gain_pixels": int(vegetation_gain),
                    "loss_percent": float(vegetation_loss / total_pixels * 100),
                    "gain_percent": float(vegetation_gain / total_pixels * 100)
                }

            return {
                "period": f"{first.date.isoformat()} to {last.date.isoformat()}",
                "impacts": impacts,
                "reclamation_status": self._assess_reclamation(impacts)
            }
        except ImportError:
            return {"error": "Mining impact requires numpy"}

    def _compute_trend(self, changes: List[Dict]) -> str:
        if not changes:
            return "insufficient_data"
        magnitudes = [c["change_magnitude"] for c in changes]
        if len(magnitudes) < 2:
            return "single_interval"
        slope = (magnitudes[-1] - magnitudes[0]) / len(magnitudes)
        if slope > 0.01:
            return "accelerating_change"
        elif slope < -0.01:
            return "decelerating_change"
        return "stable"

    def _assess_reclamation(self, impacts: Dict) -> str:
        if "vegetation" in impacts:
            veg = impacts["vegetation"]
            if veg["gain_percent"] > veg["loss_percent"] * 1.5:
                return "active_reclamation"
            elif veg["loss_percent"] > veg["gain_percent"] * 1.5:
                return "active_disturbance"
            elif veg["gain_percent"] > 0 and veg["loss_percent"] > 0:
                return "mixed"
            else:
                return "stable"
        return "insufficient_data"


class ImageClassifier:
    """Unsupervised image classification using k-means clustering."""

    def __init__(self, n_classes: int = 5):
        self.n_classes = n_classes

    def classify(self, bands: Dict[str, Any]) -> Dict[str, Any]:
        """K-means classification of multi-band satellite data."""
        try:
            import numpy as np

            band_names = sorted(bands.keys())
            pixel_vectors = []

            for name in band_names:
                arr = np.array(bands[name], dtype=np.float64).flatten()
                pixel_vectors.append(arr)

            X = np.column_stack(pixel_vectors)

            if len(X) > 100000:
                indices = np.random.choice(len(X), 100000, replace=False)
                X_sample = X[indices]
            else:
                X_sample = X
                indices = np.arange(len(X))

            centroids = X_sample[np.random.choice(len(X_sample), self.n_classes, replace=False)]
            prev_centroids = np.zeros_like(centroids)

            for iteration in range(50):
                distances = np.sqrt(((X_sample[:, np.newaxis] - centroids[np.newaxis, :]) ** 2).sum(axis=2))
                labels = np.argmin(distances, axis=1)

                prev_centroids = centroids.copy()
                for k in range(self.n_classes):
                    cluster_points = X_sample[labels == k]
                    if len(cluster_points) > 0:
                        centroids[k] = cluster_points.mean(axis=0)

                if np.allclose(centroids, prev_centroids, atol=1e-6):
                    break

            distances_full = np.sqrt(((X[:, np.newaxis] - centroids[np.newaxis, :]) ** 2).sum(axis=2))
            full_labels = np.argmin(distances_full, axis=1)

            class_stats = []
            for k in range(self.n_classes):
                mask = full_labels == k
                class_pixels = int(np.sum(mask))
                stats = {
                    "class_id": k,
                    "pixel_count": class_pixels,
                    "percent": round(class_pixels / len(X) * 100, 2),
                    "band_means": {}
                }
                for i, name in enumerate(band_names):
                    stats["band_means"][name] = float(centroids[k][i])
                class_stats.append(stats)

            class_stats.sort(key=lambda x: x["pixel_count"], reverse=True)

            labels_2d = full_labels.reshape(-1)
            shape_info = {}
            for name in band_names:
                arr = np.array(bands[name])
                shape_info[name] = list(arr.shape)

            return {
                "n_classes": self.n_classes,
                "class_statistics": class_stats,
                "shape": shape_info,
                "iterations": iteration + 1,
                "converged": iteration < 49
            }
        except ImportError:
            return {"error": "Classification requires numpy"}

    def identify_classes(self, class_stats: List[Dict]) -> Dict[str, Any]:
        """Attempt to identify class meanings based on spectral signatures."""
        classifications = {}

        for cls in class_stats:
            means = cls["band_means"]

            ndvi = None
            if "NIR" in means and "Red" in means:
                nir, red = means["NIR"], means["Red"]
                if (nir + red) > 0:
                    ndvi = (nir - red) / (nir + red)

            br42 = None
            if "Red" in means and "Blue" in means:
                if means["Blue"] > 0:
                    br42 = means["Red"] / means["Blue"]

            identification = "unknown"

            if ndvi is not None and ndvi > 0.4:
                identification = "dense_vegetation"
            elif ndvi is not None and ndvi > 0.2:
                identification = "sparse_vegetation"
            elif ndvi is not None and ndvi > 0.1:
                identification = "grassland_soil"
            elif br42 is not None and br42 > 1.5:
                identification = "iron_oxide_gossan"
            elif "SWIR1" in means and "SWIR2" in means and means["SWIR1"] > means["SWIR2"] * 1.3:
                identification = "clay_alteration"
            elif means.get("SWIR1", 0) > 0.3 and means.get("SWIR2", 0) > 0.2:
                identification = "bare_soil_rock"
            elif all(means.get(b, 0) < 0.1 for b in ["NIR", "Red", "Green", "Blue"]):
                identification = "water_shadow"
            else:
                identification = "mixed_surface"

            classifications[cls["class_id"]] = {
                "spectral_type": identification,
                "ndvi": ndvi,
                "iron_oxide_ratio": br42
            }

        return classifications


def format_temporal_results(results: Dict[str, Any]) -> str:
    """Format temporal analysis results for display."""
    lines = ["## Multi-Temporal Analysis Results\n"]

    if "overall_trend" in results:
        lines.append(f"**Overall Trend:** {results['overall_trend']}")
    if "image_count" in results:
        lines.append(f"**Images Analyzed:** {results['image_count']}")
    if "trend" in results:
        lines.append(f"**NDVI Trend:** {results['trend']}")
    if "anomalies_detected" in results:
        lines.append(f"**Anomalies Detected:** {results['anomalies_detected']}")

    if "temporal_changes" in results:
        lines.append("\n### Change Events")
        for change in results["temporal_changes"]:
            emoji = "⬆" if change["change_type"] == "increase" else "⬇" if change["change_type"] == "decrease" else "➡"
            lines.append(f"- {change['from_date']} → {change['to_date']}: {emoji} {change['change_type']} ({change['change_percent']:.1f}% pixels changed)")

    if "class_statistics" in results:
        lines.append("\n### Classification Results")
        for cls in results["class_statistics"]:
            lines.append(f"- **Class {cls['class_id']}:** {cls['pixel_count']} pixels ({cls['percent']:.1f}%)")

    return "\n".join(lines)
