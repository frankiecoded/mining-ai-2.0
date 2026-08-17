"""Satellite Image Reading, Understanding, and Visual Analysis Engine.

Production-grade backend for loading, processing, and analyzing multi-band
satellite imagery with support for multiple input formats and comprehensive
band statistics, index computation, and feature detection.
"""

import base64
import hashlib
import io
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ImageBand:
    """Represents a single spectral band from a satellite image."""

    name: str
    data: np.ndarray
    wavelength: Optional[float] = None
    resolution: Optional[float] = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError(f"Band data must be 2D, got {self.data.ndim}D")


@dataclass
class ImageMetadata:
    """Metadata describing a satellite image."""

    filename: str = ""
    width: int = 0
    height: int = 0
    bands: int = 0
    crs: str = "EPSG:4326"
    bounds: Optional[dict] = None
    resolution: Optional[float] = None
    capture_date: Optional[datetime] = None
    satellite: str = ""
    cloud_cover: float = 0.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "bands": self.bands,
            "crs": self.crs,
            "bounds": self.bounds,
            "resolution": self.resolution,
            "capture_date": self.capture_date.isoformat() if self.capture_date else None,
            "satellite": self.satellite,
            "cloud_cover": self.cloud_cover,
            "extra": self.extra,
        }
        return d


class SatelliteImageReader:
    """Core engine for loading, analyzing, and visualizing satellite imagery.

    All internal band data is stored as numpy arrays for efficient computation.
    Supports loading from raw arrays, base64-encoded data, and file paths.
    """

    SPECTRAL_BANDS = {
        "B01": {"wavelength": 443, "description": "Coastal aerosol"},
        "B02": {"wavelength": 490, "description": "Blue"},
        "B03": {"wavelength": 560, "description": "Green"},
        "B04": {"wavelength": 665, "description": "Red"},
        "B05": {"wavelength": 705, "description": "Red edge 1"},
        "B06": {"wavelength": 740, "description": "Red edge 2"},
        "B07": {"wavelength": 783, "description": "Red edge 3"},
        "B08": {"wavelength": 842, "description": "NIR"},
        "B09": {"wavelength": 945, "description": "Water vapour"},
        "B10": {"wavelength": 1375, "description": "SWIR Cirrus"},
        "B11": {"wavelength": 1610, "description": "SWIR 1"},
        "B12": {"wavelength": 2190, "description": "SWIR 2"},
    }

    def __init__(self, metadata: Optional[ImageMetadata] = None) -> None:
        self._bands: dict[str, ImageBand] = {}
        self._metadata = metadata or ImageMetadata()
        self._computed_indices: dict[str, np.ndarray] = {}
        self._image_id: str = hashlib.sha256(
            f"{self._metadata.filename}_{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

    @property
    def image_id(self) -> str:
        return self._image_id

    @property
    def metadata(self) -> ImageMetadata:
        return self._metadata

    @property
    def band_names(self) -> list[str]:
        return list(self._bands.keys())

    @property
    def shape(self) -> tuple[int, int]:
        if not self._bands:
            return (0, 0)
        first_band = next(iter(self._bands.values()))
        return (first_band.data.shape[0], first_band.data.shape[1])

    def load_from_arrays(
        self,
        band_data: dict[str, np.ndarray],
        metadata: Optional[ImageMetadata] = None,
    ) -> None:
        """Load multi-band image from a dict of band name to 2D numpy arrays."""
        if not band_data:
            raise ValueError("band_data must not be empty")

        shapes = {name: arr.shape for name, arr in band_data.items()}
        unique_shapes = set(shapes.values())
        if len(unique_shapes) != 1:
            raise ValueError(
                f"All bands must have the same shape, got: {shapes}"
            )

        shape = next(iter(unique_shapes))
        if len(shape) != 2:
            raise ValueError(f"Band arrays must be 2D, got shape {shape}")

        for name, arr in band_data.items():
            band_info = self.SPECTRAL_BANDS.get(name, {})
            self._bands[name] = ImageBand(
                name=name,
                data=arr.astype(np.float64),
                wavelength=band_info.get("wavelength"),
                resolution=band_info.get("resolution"),
                description=band_info.get("description", ""),
            )

        if metadata:
            self._metadata = metadata
        else:
            self._metadata.width = shape[1]
            self._metadata.height = shape[0]
            self._metadata.bands = len(band_data)

        self._computed_indices.clear()
        logger.info(
            "Loaded image with %d bands, shape (%d, %d)",
            len(band_data),
            shape[0],
            shape[1],
        )

    def load_from_base64(
        self,
        b64_data: str,
        metadata: Optional[ImageMetadata] = None,
        band_names: Optional[list[str]] = None,
    ) -> None:
        """Decode base64 data and load as single-band or multi-band image.

        Expects raw bytes representing a numpy array saved with np.save or
        a single-band image. For multi-band, provide band_names and encode
        each band sequentially separated by a 4-byte length prefix.
        """
        if not b64_data:
            raise ValueError("b64_data must not be empty")

        decoded = base64.b64decode(b64_data)
        buf = io.BytesIO(decoded)

        if band_names and len(band_names) > 1:
            self._load_multi_band_from_bytes(buf, band_names)
        else:
            arr = np.load(buf, allow_pickle=False)
            if arr.ndim == 2:
                name = band_names[0] if band_names else "B04"
                self.load_from_arrays({name: arr}, metadata)
            elif arr.ndim == 3:
                n_bands = arr.shape[2] if arr.ndim == 3 else 1
                names = band_names or [f"B{i+1:02d}" for i in range(n_bands)]
                band_dict = {}
                for i, nm in enumerate(names):
                    band_dict[nm] = arr[:, :, i] if arr.ndim == 3 else arr
                self.load_from_arrays(band_dict, metadata)
            else:
                raise ValueError(f"Unsupported array shape: {arr.shape}")

    def _load_multi_band_from_bytes(
        self, buf: io.BytesIO, band_names: list[str]
    ) -> None:
        """Load multiple bands from a byte stream with length-prefixed arrays."""
        band_dict: dict[str, np.ndarray] = {}
        for name in band_names:
            length_bytes = buf.read(4)
            if len(length_bytes) < 4:
                raise ValueError(f"Unexpected end of stream reading band {name}")
            length = int.from_bytes(length_bytes, byteorder="big")
            arr_bytes = buf.read(length)
            if len(arr_bytes) != length:
                raise ValueError(f"Incomplete data for band {name}")
            arr = np.load(io.BytesIO(arr_bytes), allow_pickle=False)
            band_dict[name] = arr
        self.load_from_arrays(band_dict)

    def _get_band_array(self, band_name: str) -> np.ndarray:
        if band_name not in self._bands:
            raise KeyError(f"Band '{band_name}' not found. Available: {self.band_names}")
        return self._bands[band_name].data

    def _safe_divide(
        self,
        numerator: np.ndarray,
        denominator: np.ndarray,
        fill: float = 0.0,
    ) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            result = np.where(denominator != 0, numerator / denominator, fill)
        return np.nan_to_num(result, nan=fill, posinf=fill, neginf=fill)

    def get_band_stats(self, band_name: str) -> dict[str, Any]:
        """Compute statistics for a single band."""
        arr = self._get_band_array(band_name)
        flat = arr.ravel()
        valid = flat[np.isfinite(flat)]

        if valid.size == 0:
            return {
                "band": band_name,
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "std": 0.0,
                "percentiles": {"p5": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p95": 0.0},
                "histogram": {"counts": [], "bins": []},
                "valid_pixels": 0,
                "total_pixels": int(flat.size),
            }

        pcts = np.percentile(valid, [5, 25, 50, 75, 95])
        counts, bin_edges = np.histogram(valid, bins=256)

        return {
            "band": band_name,
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "mean": float(np.mean(valid)),
            "std": float(np.std(valid)),
            "percentiles": {
                "p5": float(pcts[0]),
                "p25": float(pcts[1]),
                "p50": float(pcts[2]),
                "p75": float(pcts[3]),
                "p95": float(pcts[4]),
            },
            "histogram": {
                "counts": counts.tolist(),
                "bins": bin_edges.tolist(),
            },
            "valid_pixels": int(valid.size),
            "total_pixels": int(flat.size),
        }

    def get_image_stats(self) -> dict[str, dict]:
        """Compute statistics for all bands."""
        return {name: self.get_band_stats(name) for name in self.band_names}

    def compute_band_ratio(
        self, numerator_band: str, denominator_band: str
    ) -> np.ndarray:
        """Compute element-wise ratio of two bands."""
        num = self._get_band_array(numerator_band)
        den = self._get_band_array(denominator_band)
        return self._safe_divide(num, den)

    def _get_rgb(
        self,
        r_band: str,
        g_band: str,
        b_band: str,
        percentile_stretch: tuple[float, float] = (2.0, 98.0),
    ) -> dict[str, np.ndarray]:
        """Build an RGB composite with percentile contrast stretching."""
        r = self._get_band_array(r_band)
        g = self._get_band_array(g_band)
        b = self._get_band_array(b_band)

        def stretch(arr: np.ndarray) -> np.ndarray:
            valid = arr[np.isfinite(arr)]
            if valid.size == 0:
                return np.zeros_like(arr, dtype=np.uint8)
            p_low, p_high = np.percentile(valid, percentile_stretch)
            if p_high <= p_low:
                p_high = p_low + 1.0
            scaled = np.clip((arr - p_low) / (p_high - p_low) * 255.0, 0, 255)
            return scaled.astype(np.uint8)

        return {"red": stretch(r), "green": stretch(g), "blue": stretch(b)}

    def get_true_color_composite(self) -> dict[str, np.ndarray]:
        """True color composite from B04 (R), B03 (G), B02 (B)."""
        return self._get_rgb("B04", "B03", "B02")

    def get_false_color_composite(self) -> dict[str, np.ndarray]:
        """False color composite from B08 (R), B04 (G), B03 (B)."""
        return self._get_rgb("B08", "B04", "B03")

    def get_mineral_composite(self) -> dict[str, np.ndarray]:
        """Mineral/composite from iron oxide ratio, alteration index, vegetation."""
        iron = self._compute_iron_oxide()
        alteration = self._compute_alteration()
        veg = self._compute_ndvi()

        def normalize(arr: np.ndarray) -> np.ndarray:
            valid = arr[np.isfinite(arr)]
            if valid.size == 0:
                return np.zeros_like(arr, dtype=np.uint8)
            p2, p98 = np.percentile(valid, [2, 98])
            if p98 <= p2:
                p98 = p2 + 1.0
            return np.clip((arr - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)

        return {"red": normalize(iron), "green": normalize(alteration), "blue": normalize(veg)}

    def _compute_ndvi(self) -> np.ndarray:
        nir = self._get_band_array("B08")
        red = self._get_band_array("B04")
        return self._safe_divide(nir - red, nir + red, fill=0.0)

    def _compute_ndwi(self) -> np.ndarray:
        green = self._get_band_array("B03")
        nir = self._get_band_array("B08")
        return self._safe_divide(green - nir, green + nir, fill=0.0)

    def _compute_bsi(self) -> np.ndarray:
        swir1 = self._get_band_array("B11")
        red = self._get_band_array("B04")
        nir = self._get_band_array("B08")
        blue = self._get_band_array("B02")
        numerator = (swir1 + red) - (nir + blue)
        denominator = (swir1 + red) + (nir + blue)
        return self._safe_divide(numerator, denominator, fill=0.0)

    def _compute_iron_oxide(self) -> np.ndarray:
        red = self._get_band_array("B04")
        blue = self._get_band_array("B02")
        return self._safe_divide(red, blue, fill=0.0)

    def _compute_alteration(self) -> np.ndarray:
        swir2 = self._get_band_array("B12")
        nir = self._get_band_array("B08")
        return self._safe_divide(swir2, nir, fill=0.0)

    def detect_clouds(self, threshold: float = 0.4) -> np.ndarray:
        """Simple cloud detection using brightness thresholding on visible bands.

        Returns a boolean mask where True indicates cloud pixels.
        """
        if "B02" not in self._bands or "B04" not in self._bands:
            raise KeyError("Cloud detection requires B02 and B04 bands")

        b02 = self._get_band_array("B02")
        b04 = self._get_band_array("B04")
        b03 = self._get_band_array("B03") if "B03" in self._bands else b04

        brightness = (b02 + b03 + b04) / 3.0
        valid = brightness[np.isfinite(brightness)]
        if valid.size == 0:
            return np.zeros(self.shape, dtype=bool)

        p90 = float(np.percentile(valid, 90))
        cloud_threshold = max(p90 * threshold, threshold * 1000.0 if np.mean(valid) > 1000 else threshold)
        mask = brightness > cloud_threshold

        logger.info(
            "Cloud detection: %.1f%% pixels classified as cloud",
            100.0 * np.sum(mask) / mask.size,
        )
        return mask

    def detect_water(self, threshold: float = 0.0) -> np.ndarray:
        """Water detection using NDWI. Returns boolean mask (True = water)."""
        ndwi = self._compute_ndwi()
        mask = ndwi > threshold
        logger.info(
            "Water detection: %.1f%% pixels classified as water",
            100.0 * np.sum(mask) / mask.size,
        )
        return mask

    def detect_vegetation(self, threshold: float = 0.2) -> np.ndarray:
        """Vegetation detection using NDVI. Returns boolean mask (True = vegetation)."""
        ndvi = self._compute_ndvi()
        mask = ndvi > threshold
        logger.info(
            "Vegetation detection: %.1f%% pixels classified as vegetation",
            100.0 * np.sum(mask) / mask.size,
        )
        return mask

    def detect_bare_soil(self, threshold: float = 0.0) -> np.ndarray:
        """Bare soil detection using BSI. Returns boolean mask (True = bare soil)."""
        bsi = self._compute_bsi()
        mask = bsi > threshold
        logger.info(
            "Bare soil detection: %.1f%% pixels classified as bare soil",
            100.0 * np.sum(mask) / mask.size,
        )
        return mask

    def generate_thumbnail(
        self,
        width: int = 256,
        height: int = 256,
        band_names: Optional[list[str]] = None,
    ) -> str:
        """Generate a base64-encoded PNG thumbnail.

        Uses nearest-neighbor resampling for speed. Returns RGB PNG bytes
        encoded as base64 string.
        """
        names = band_names or (["B04", "B03", "B02"] if "B04" in self._bands else self.band_names[:3])
        if len(names) < 3:
            names = list(names) + ["B04"] * (3 - len(names))

        composite = self._get_rgb(names[0], names[1], names[2])
        rgb = np.stack([composite["red"], composite["green"], composite["blue"]], axis=-1)

        h, w = rgb.shape[:2]
        if h == 0 or w == 0:
            rgb = np.zeros((height, width, 3), dtype=np.uint8)
        else:
            row_idx = np.linspace(0, h - 1, height).astype(int)
            col_idx = np.linspace(0, w - 1, width).astype(int)
            rgb = rgb[np.ix_(row_idx, col_idx)]

        png_data = self._encode_png_bytes(rgb)
        return base64.b64encode(png_data).decode("ascii")

    def _encode_png_bytes(self, rgb: np.ndarray) -> bytes:
        """Encode RGB array as minimal PNG using raw deflate.

        Falls back to a simple BMP if no PNG encoder is available.
        """
        try:
            import zlib

            def _chunk(chunk_type: bytes, data: bytes) -> bytes:
                c = chunk_type + data
                crc = zlib.crc32(c) & 0xFFFFFFFF
                return len(data).to_bytes(4, "big") + c + crc.to_bytes(4, "big")

            sig = b"\x89PNG\r\n\x1a\n"
            ihdr_data = (
                rgb.shape[1].to_bytes(4, "big")
                + rgb.shape[0].to_bytes(4, "big")
                + b"\x08\x02\x00\x00\x00"
            )
            ihdr = _chunk(b"IHDR", ihdr_data)

            raw_rows = []
            for row in rgb:
                raw_rows.append(b"\x00" + row.tobytes())
            raw = b"".join(raw_rows)
            compressed = zlib.compress(raw, 6)
            idat = _chunk(b"IDAT", compressed)
            iend = _chunk(b"IEND", b"")

            return sig + ihdr + idat + iend
        except Exception:
            return self._encode_bmp_bytes(rgb)

    def _encode_bmp_bytes(self, rgb: np.ndarray) -> bytes:
        """Fallback BMP encoder when PNG is unavailable."""
        h, w, _ = rgb.shape
        row_size = (w * 3 + 3) & ~3
        pixel_data_size = row_size * h
        file_size = 54 + pixel_data_size

        header = bytearray(54)
        header[0:2] = b"BM"
        header[2:6] = file_size.to_bytes(4, "little")
        header[10:14] = (54).to_bytes(4, "little")
        header[14:18] = (40).to_bytes(4, "little")
        header[18:22] = w.to_bytes(4, "little")
        header[22:26] = h.to_bytes(4, "little")
        header[26:28] = (1).to_bytes(2, "little")
        header[28:30] = (24).to_bytes(2, "little")
        header[34:38] = pixel_data_size.to_bytes(4, "little")

        pixels = bytearray(pixel_data_size)
        offset = 0
        for y in range(h - 1, -1, -1):
            for x in range(w):
                pixels[offset] = int(rgb[y, x, 2])
                pixels[offset + 1] = int(rgb[y, x, 1])
                pixels[offset + 2] = int(rgb[y, x, 0])
                offset += 3
            offset += row_size - w * 3

        return bytes(header) + bytes(pixels)

    def generate_annotated_overlay(
        self,
        annotations: list[dict],
        width: int = 512,
        height: int = 512,
    ) -> str:
        """Render GeoJSON-style annotations as a base64-encoded overlay image.

        Each annotation dict should be a GeoJSON Feature with geometry and
        optional properties. Polygons are drawn as outlines, points as circles.
        """
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        h_orig, w_orig = self.shape

        if h_orig == 0 or w_orig == 0:
            return base64.b64encode(self._encode_png_bytes(np.zeros((height, width, 3), dtype=np.uint8))).decode("ascii")

        def to_pixel_coords(lon: float, lat: float) -> tuple[int, int]:
            if self._metadata.bounds:
                b = self._metadata.bounds
                x = int((lon - b.get("min_lon", 0)) / (b.get("max_lon", 1) - b.get("min_lon", 1)) * (width - 1))
                y = int((1 - (lat - b.get("min_lat", 0)) / (b.get("max_lat", 1) - b.get("min_lat", 1))) * (height - 1))
            else:
                x = int((lon + 180.0) / 360.0 * (width - 1))
                y = int((90.0 - lat) / 180.0 * (height - 1))
            return max(0, min(width - 1, x)), max(0, min(height - 1, y))

        colors = [
            (255, 0, 0, 200),
            (0, 255, 0, 200),
            (0, 0, 255, 200),
            (255, 255, 0, 200),
            (255, 0, 255, 200),
            (0, 255, 255, 200),
        ]

        for i, feature in enumerate(annotations):
            color = colors[i % len(colors)]
            geom = feature.get("geometry", feature)
            geom_type = geom.get("type", "Point")
            coords = geom.get("coordinates", [])

            if geom_type == "Point":
                px, py = to_pixel_coords(coords[0], coords[1])
                radius = 4
                y_lo = max(0, py - radius)
                y_hi = min(height, py + radius + 1)
                x_lo = max(0, px - radius)
                x_hi = min(width, px + radius + 1)
                yy, xx = np.ogrid[y_lo:y_hi, x_lo:x_hi]
                circle_mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius**2
                overlay[y_lo:y_hi, x_lo:x_hi][circle_mask] = color

            elif geom_type == "Polygon":
                ring = coords[0] if coords else []
                pixels = [to_pixel_coords(c[0], c[1]) for c in ring]
                for j in range(len(pixels) - 1):
                    self._draw_line_on_overlay(overlay, pixels[j], pixels[j + 1], color)

            elif geom_type == "MultiPolygon":
                for polygon in coords:
                    for ring in polygon:
                        pixels = [to_pixel_coords(c[0], c[1]) for c in ring]
                        for j in range(len(pixels) - 1):
                            self._draw_line_on_overlay(overlay, pixels[j], pixels[j + 1], color)

        rgb = overlay[:, :, :3]
        png_data = self._encode_png_bytes(rgb)
        return base64.b64encode(png_data).decode("ascii")

    def _draw_line_on_overlay(
        self,
        overlay: np.ndarray,
        p0: tuple[int, int],
        p1: tuple[int, int],
        color: tuple[int, int, int, int],
        thickness: int = 2,
    ) -> None:
        """Draw a line segment on the overlay using Bresenham's algorithm."""
        x0, y0 = p0
        x1, y1 = p1
        h, w = overlay.shape[:2]
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            for tx in range(-thickness // 2, thickness // 2 + 1):
                for ty in range(-thickness // 2, thickness // 2 + 1):
                    nx, ny = x0 + tx, y0 + ty
                    if 0 <= nx < w and 0 <= ny < h:
                        overlay[ny, nx] = color

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def get_pixel_value(self, lon: float, lat: float) -> dict[str, float]:
        """Get all band values at a geographic coordinate.

        If bounds are set, maps lon/lat to pixel coordinates. Otherwise treats
        lon/lat as direct indices (with wrapping).
        """
        h, w = self.shape
        if h == 0 or w == 0:
            raise ValueError("Image has no data")

        if self._metadata.bounds:
            b = self._metadata.bounds
            lon_range = b.get("max_lon", 1) - b.get("min_lon", 0)
            lat_range = b.get("max_lat", 1) - b.get("min_lat", 0)
            if lon_range == 0 or lat_range == 0:
                raise ValueError("Invalid bounds: zero range")
            col = int((lon - b.get("min_lon", 0)) / lon_range * (w - 1))
            row = int((1 - (lat - b.get("min_lat", 0)) / lat_range) * (h - 1))
        else:
            col = int(lon)
            row = int(lat)

        row = max(0, min(h - 1, row))
        col = max(0, min(w - 1, col))

        return {
            name: float(self._bands[name].data[row, col])
            for name in self.band_names
        }

    def get_area_stats(
        self,
        bounds: dict,
    ) -> dict[str, dict]:
        """Compute band statistics for a sub-region defined by geographic bounds.

        bounds should have keys: min_lon, max_lon, min_lat, max_lat.
        """
        h, w = self.shape
        if h == 0 or w == 0:
            raise ValueError("Image has no data")

        if self._metadata.bounds:
            mb = self._metadata.bounds
            lon_range = mb.get("max_lon", 1) - mb.get("min_lon", 0)
            lat_range = mb.get("max_lat", 1) - mb.get("min_lat", 0)
            if lon_range == 0 or lat_range == 0:
                raise ValueError("Invalid metadata bounds")

            col_min = max(0, int((bounds["min_lon"] - mb.get("min_lon", 0)) / lon_range * (w - 1)))
            col_max = min(w - 1, int((bounds["max_lon"] - mb.get("min_lon", 0)) / lon_range * (w - 1)))
            row_min = max(0, int((1 - (bounds["max_lat"] - mb.get("min_lat", 0)) / lat_range) * (h - 1)))
            row_max = min(h - 1, int((1 - (bounds["min_lat"] - mb.get("min_lat", 0)) / lat_range) * (h - 1)))
        else:
            col_min = max(0, int(bounds.get("min_lon", 0)))
            col_max = min(w - 1, int(bounds.get("max_lon", w - 1)))
            row_min = max(0, int(bounds.get("min_lat", 0)))
            row_max = min(h - 1, int(bounds.get("max_lat", h - 1)))

        if col_min >= col_max or row_min >= row_max:
            raise ValueError("Sub-region is empty or invalid")

        result = {}
        for name in self.band_names:
            sub = self._bands[name].data[row_min : row_max + 1, col_min : col_max + 1]
            valid = sub.ravel()
            valid = valid[np.isfinite(valid)]
            if valid.size == 0:
                result[name] = {
                    "min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0,
                    "pixel_count": 0,
                }
            else:
                result[name] = {
                    "min": float(np.min(valid)),
                    "max": float(np.max(valid)),
                    "mean": float(np.mean(valid)),
                    "std": float(np.std(valid)),
                    "pixel_count": int(valid.size),
                }

        return result

    def export_as_base64(self, band_name: str) -> str:
        """Export a single band as base64-encoded numpy array."""
        arr = self._get_band_array(band_name)
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def get_summary(self) -> str:
        """Generate a human-readable summary of the image."""
        h, w = self.shape
        lines = [
            f"Satellite Image Summary",
            f"{'=' * 40}",
            f"ID          : {self._image_id}",
            f"Filename    : {self._metadata.filename or 'N/A'}",
            f"Satellite   : {self._metadata.satellite or 'Unknown'}",
            f"Dimensions  : {w} x {h} pixels",
            f"Bands       : {len(self.band_names)} ({', '.join(self.band_names)})",
            f"CRS         : {self._metadata.crs}",
            f"Resolution  : {self._metadata.resolution or 'N/A'} m/px",
            f"Capture     : {self._metadata.capture_date.isoformat() if self._metadata.capture_date else 'N/A'}",
            f"Cloud Cover : {self._metadata.cloud_cover:.1f}%",
        ]

        if self._metadata.bounds:
            b = self._metadata.bounds
            lines.append(
                f"Bounds      : ({b.get('min_lon', '?')}, {b.get('min_lat', '?')}) "
                f"-> ({b.get('max_lon', '?')}, {b.get('max_lat', '?')})"
            )

        lines.append("")
        lines.append("Band Statistics:")
        lines.append(f"{'Band':<8} {'Min':>10} {'Max':>10} {'Mean':>10} {'Std':>10}")
        lines.append("-" * 52)
        for name in self.band_names:
            stats = self.get_band_stats(name)
            lines.append(
                f"{name:<8} {stats['min']:10.4f} {stats['max']:10.4f} "
                f"{stats['mean']:10.4f} {stats['std']:10.4f}"
            )

        total_pixels = h * w
        lines.append("")
        lines.append(f"Total pixels: {total_pixels:,}")
        lines.append(f"Memory usage: ~{self._estimate_memory_mb():.1f} MB")

        return "\n".join(lines)

    def _estimate_memory_mb(self) -> float:
        total_elements = sum(band.data.size for band in self._bands.values())
        bytes_per_element = 8  # float64
        return (total_elements * bytes_per_element) / (1024 * 1024)


class ImageCollection:
    """Manager for a collection of satellite images.

    Supports temporal operations, change detection, and multi-image queries.
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._images: dict[str, SatelliteImageReader] = {}
        self._order: list[str] = []

    @property
    def count(self) -> int:
        return len(self._images)

    def add_image(self, reader: SatelliteImageReader) -> str:
        """Add an image to the collection. Returns the image ID."""
        img_id = reader.image_id
        if img_id in self._images:
            logger.warning("Image %s already in collection, replacing", img_id)
        else:
            self._order.append(img_id)
        self._images[img_id] = reader
        logger.info("Added image %s to collection '%s'", img_id, self.name)
        return img_id

    def get_image(self, image_id: str) -> SatelliteImageReader:
        """Retrieve an image by ID."""
        if image_id not in self._images:
            raise KeyError(
                f"Image '{image_id}' not found. Available: {list(self._images.keys())}"
            )
        return self._images[image_id]

    def list_images(self) -> list[dict[str, Any]]:
        """List all images with basic metadata."""
        result = []
        for img_id in self._order:
            reader = self._images[img_id]
            result.append({
                "image_id": img_id,
                "filename": reader.metadata.filename,
                "satellite": reader.metadata.satellite,
                "capture_date": (
                    reader.metadata.capture_date.isoformat()
                    if reader.metadata.capture_date
                    else None
                ),
                "bands": reader.band_names,
                "shape": reader.shape,
            })
        return result

    def remove_image(self, image_id: str) -> None:
        """Remove an image from the collection."""
        if image_id not in self._images:
            raise KeyError(f"Image '{image_id}' not found")
        del self._images[image_id]
        self._order.remove(image_id)
        logger.info("Removed image %s from collection '%s'", image_id, self.name)

    def get_temporal_stack(self, band_name: str) -> list[dict[str, Any]]:
        """Stack a single band across all images sorted by capture date.

        Returns a list of dicts with image_id, date, and data array.
        """
        entries = []
        for img_id in self._order:
            reader = self._images[img_id]
            if band_name in reader.band_names:
                entries.append({
                    "image_id": img_id,
                    "date": reader.metadata.capture_date,
                    "data": reader._get_band_array(band_name),
                })

        entries.sort(key=lambda e: e["date"] or datetime.min)
        return entries

    def compute_change(
        self,
        image1_id: str,
        image2_id: str,
        band: str,
    ) -> np.ndarray:
        """Compute per-pixel change map between two images for a given band.

        Returns the difference array (image2 - image1).
        """
        reader1 = self.get_image(image1_id)
        reader2 = self.get_image(image2_id)

        arr1 = reader1._get_band_array(band)
        arr2 = reader2._get_band_array(band)

        if arr1.shape != arr2.shape:
            raise ValueError(
                f"Shape mismatch for change detection: {arr1.shape} vs {arr2.shape}"
            )

        change = arr2 - arr1
        logger.info(
            "Change map computed for band '%s': mean=%.4f, max=%.4f",
            band,
            float(np.mean(change[np.isfinite(change)])) if np.any(np.isfinite(change)) else 0.0,
            float(np.nanmax(np.abs(change))),
        )
        return change
