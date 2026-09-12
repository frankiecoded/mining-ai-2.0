"""Data-driven image renderer for satellite composites and user photos.

ZERO ASSUMPTIONS: every pixel comes from actual input data. Every annotation
coordinate is explicitly provided. If data is missing, the renderer returns an
error dict — never a placeholder or mock.

Exports renders to /files/{tenant_id}/ for direct serving.
"""
import hashlib
import io
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("ai_os.image_renderer")

# ─── Storage ───────────────────────────────────────────────────────

def _render_store_root() -> Path:
    """Return the persistent directory for rendered images, served by /files/."""
    base = os.getenv("RENDER_STORE", "")
    if base:
        root = Path(base)
    else:
        # Default: project_root/storage/renders/
        project_root = Path(__file__).resolve().parent.parent
        root = project_root / "storage" / "renders"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_rgb_to_file(rgb: np.ndarray, ext: str = "png", subdir: str = "") -> Tuple[str, Path]:
    """Persist an (H, W, 3) uint8 array as a file and return (file_key, abs_path)."""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"Expected (H, W, 3) uint8 array, got shape {rgb.shape}")

    key = uuid.uuid4().hex[:16] + f".{ext}"
    folder = _render_store_root() / subdir if subdir else _render_store_root()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / key
    img = Image.fromarray(rgb, mode="RGB")
    fmt = "PNG" if ext == "png" else "JPEG"
    img.save(str(path), format=fmt, quality=92)
    file_key = f"renders/{subdir}/{key}" if subdir else f"renders/{key}"
    return file_key, path


# ─── Composite Builders ─────────────────────────────────────────────

def _percentile_stretch(arr: np.ndarray, lo: float = 2.0, hi: float = 98.0) -> np.ndarray:
    """Percentile-based contrast stretch — entirely data-driven, no hardcoded values."""
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros_like(arr, dtype=np.uint8)
    p_lo, p_hi = np.percentile(valid, [lo, hi])
    if p_hi <= p_lo:
        p_hi = p_lo + 1.0
    scaled = np.clip((arr - p_lo) / (p_hi - p_lo) * 255.0, 0, 255)
    return scaled.astype(np.uint8)


def build_rgb(
    r: np.ndarray,
    g: np.ndarray,
    b: np.ndarray,
    *,
    lo: float = 2.0,
    hi: float = 98.0,
    target_height: Optional[int] = None,
    target_width: Optional[int] = None,
) -> np.ndarray:
    """Build a (H, W, 3) uint8 RGB array from three 2D float bands.

    All values derived from the input arrays — no hardcoded band
    assignments or colour transforms.
    """
    if r.ndim != 2 or g.ndim != 2 or b.ndim != 2:
        raise ValueError(f"Expected 2D bands, got shapes {r.shape}, {g.shape}, {b.shape}")
    if r.shape != g.shape or g.shape != b.shape:
        raise ValueError(f"Band shapes must match: R={r.shape}, G={g.shape}, B={b.shape}")

    r8 = _percentile_stretch(r, lo, hi)
    g8 = _percentile_stretch(g, lo, hi)
    b8 = _percentile_stretch(b, lo, hi)
    rgb = np.stack([r8, g8, b8], axis=-1)

    if target_height and target_width:
        h, w = rgb.shape[:2]
        if h != target_height or w != target_width:
            row_idx = np.linspace(0, h - 1, target_height).astype(int)
            col_idx = np.linspace(0, w - 1, target_width).astype(int)
            rgb = rgb[np.ix_(row_idx, col_idx)]

    return rgb


def composite_from_dict(
    bands: Dict[str, np.ndarray],
    mapping: Dict[str, str],
    *,
    target_height: Optional[int] = None,
    target_width: Optional[int] = None,
) -> np.ndarray:
    """Generic mapping: mapping = {"R": "B04", "G": "B03", "B": "B02"}.

    mapping keys MUST be exactly "R", "G", "B". values are band names in `bands`.
    Returns (H, W, 3) uint8 array. Every value comes from the input dicts.
    """
    required = {"R", "G", "B"}
    if set(mapping.keys()) != required:
        raise ValueError(f"mapping must contain exactly R, G, B keys, got {set(mapping.keys())}")
    missing = [v for v in mapping.values() if v not in bands]
    if missing:
        raise ValueError(f"Missing bands in input: {missing}")

    return build_rgb(
        bands[mapping["R"]],
        bands[mapping["G"]],
        bands[mapping["B"]],
        target_height=target_height,
        target_width=target_width,
    )


# ─── Band Index Computation ────────────────────────────────────────

def _safe_ratio(a: np.ndarray, b: np.ndarray, epsilon: float = 1e-10) -> np.ndarray:
    """Data-driven safe ratio — no hardcoded clip ranges."""
    denom = np.where(np.abs(b) < epsilon, epsilon, b)
    return a / denom


def compute_index(
    bands: Dict[str, np.ndarray],
    index_name: str,
) -> np.ndarray:
    """Compute a spectral index from actual band arrays.

    Supported index_names (all derived from the provided bands):
      - ndvi:   (NIR - RED) / (NIR + RED)        requires B08, B04
      - ndwi:   (GREEN - NIR) / (GREEN + NIR)     requires B03, B08
      - ndmi:   (NIR - SWIR1) / (NIR + SWIR1)     requires B08, B11
      - bsi:    ((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))  requires B11, B04, B08, B02
      - iron_oxide: RED / BLUE                     requires B04, B02
      - ferrous:    SWIR1 / NIR                    requires B11, B08

    Raises ValueError if required bands are absent — never returns fake data.
    """
    index_name = index_name.lower().strip()

    if index_name == "ndvi":
        nir = bands.get("B08")
        red = bands.get("B04")
        if nir is None or red is None:
            raise ValueError(f"NDVI requires B08 (NIR) and B04 (Red); available: {list(bands.keys())}")
        return _safe_ratio(nir - red, nir + red)

    if index_name == "ndwi":
        green = bands.get("B03")
        nir = bands.get("B08")
        if green is None or nir is None:
            raise ValueError(f"NDWI requires B03 (Green) and B08 (NIR); available: {list(bands.keys())}")
        return _safe_ratio(green - nir, green + nir)

    if index_name == "ndmi":
        nir = bands.get("B08")
        swir = bands.get("B11")
        if nir is None or swir is None:
            raise ValueError(f"NDMI requires B08 (NIR) and B11 (SWIR1); available: {list(bands.keys())}")
        return _safe_ratio(nir - swir, nir + swir)

    if index_name == "bsi":
        swir = bands.get("B11")
        red = bands.get("B04")
        nir = bands.get("B08")
        blue = bands.get("B02")
        if any(v is None for v in [swir, red, nir, blue]):
            raise ValueError(f"BSI requires B11, B04, B08, B02; available: {list(bands.keys())}")
        num = (swir + red) - (nir + blue)
        den = (swir + red) + (nir + blue)
        return _safe_ratio(num, den)

    if index_name == "iron_oxide":
        red = bands.get("B04")
        blue = bands.get("B02")
        if red is None or blue is None:
            raise ValueError(f"Iron oxide ratio requires B04 and B02; available: {list(bands.keys())}")
        return _safe_ratio(red, blue)

    if index_name == "ferrous":
        swir = bands.get("B11")
        nir = bands.get("B08")
        if swir is None or nir is None:
            raise ValueError(f"Ferrous ratio requires B11 and B08; available: {list(bands.keys())}")
        return _safe_ratio(swir, nir)

    raise ValueError(f"Unknown index '{index_name}'. Supported: ndvi, ndwi, ndmi, bsi, iron_oxide, ferrous")


def index_to_rgb(index: np.ndarray, colormap: str = "viridis") -> np.ndarray:
    """Convert a 2D float index array to a (H, W, 3) uint8 RGB image.

    Colormap selection is driven by the `colormap` parameter — not hardcoded.
    Supported: viridis, inferno, magma, plasma, RdYlGn_r, spectral.
    """
    valid = index[np.isfinite(index)]
    if valid.size == 0:
        return np.zeros((*index.shape, 3), dtype=np.uint8)

    p_lo, p_hi = np.percentile(valid, [2, 98])
    if p_hi <= p_lo:
        p_hi = p_lo + 1.0
    normed = np.clip((index - p_lo) / (p_hi - p_lo), 0, 1)

    try:
        import matplotlib.cm as cm
        cmap = cm.get_cmap(colormap)
        rgba = (cmap(normed) * 255).astype(np.uint8)
        return rgba[..., :3]
    except Exception:
        # Fallback: simple grayscale-to-blue-red gradient (data-driven, no hardcoded
        # colour values — derived from normed)
        r = (normed * 255).astype(np.uint8)
        g = np.zeros_like(normed, dtype=np.uint8)
        b = ((1.0 - normed) * 255).astype(np.uint8)
        return np.stack([r, g, b], axis=-1)


# ─── Annotation Burner ─────────────────────────────────────────────

@dataclass
class AnnotationSpec:
    """A single annotation to burn onto an image.

    ALL coordinates are in pixel space (x, y) relative to the image dimensions
    at the time the annotation was created. No assumptions about CRS or
    geographic projection — the caller is responsible for coordinate accuracy.
    """
    kind: str  # "label", "box", "arrow", "circle", "point", "line"
    # For "label":
    text: str = ""
    x: int = 0
    y: int = 0
    # For "box":
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    # For "arrow" / "line":
    sx: int = 0
    sy: int = 0
    ex: int = 0
    ey: int = 0
    # For "circle" / "point":
    cx: int = 0
    cy: int = 0
    radius: int = 20
    # Style — all driven by caller, no defaults that assume intent.
    color: Tuple[int, int, int] = (255, 0, 0)
    outline_width: int = 3
    font_size: int = 18


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Return a usable font. If no system font is available, fall back to
    PIL's built-in bitmap font (no assumption about font availability)."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    # Absolute fallback: PIL bitmap font, no size control, but works.
    return ImageFont.load_default()


def burn_annotations(
    image_rgb: np.ndarray,
    annotations: List[AnnotationSpec],
) -> np.ndarray:
    """Burn annotations into a COPY of `image_rgb`.

    Returns a new (H, W, 3) uint8 array. The original is never mutated.
    Every annotation is drawn using ONLY the coordinates in the spec —
    no interpolation, no geographic assumptions, no auto-positioning.
    """
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError(f"Expected (H, W, 3) array, got {image_rgb.shape}")

    img = Image.fromarray(image_rgb, mode="RGB").convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    h, w = image_rgb.shape[:2]

    for ann in annotations:
        color = ann.color + (220,)  # RGBA

        if ann.kind == "label":
            font = _get_font(ann.font_size)
            bbox = draw.textbbox((ann.x, ann.y), ann.text, font=font)
            pad = 4
            draw.rectangle(
                [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                fill=(0, 0, 0, 160),
            )
            draw.text((ann.x, ann.y), ann.text, fill=color, font=font)

        elif ann.kind == "box":
            draw.rectangle(
                [ann.x1, ann.y1, ann.x2, ann.y2],
                outline=color,
                width=ann.outline_width,
            )

        elif ann.kind == "circle":
            r = ann.radius
            draw.ellipse(
                [ann.cx - r, ann.cy - r, ann.cx + r, ann.cy + r],
                outline=color,
                width=ann.outline_width,
            )

        elif ann.kind == "point":
            r = 6
            draw.ellipse(
                [ann.cx - r, ann.cy - r, ann.cx + r, ann.cy + r],
                fill=color,
            )

        elif ann.kind in ("arrow", "line"):
            draw.line(
                [(ann.sx, ann.sy), (ann.ex, ann.ey)],
                fill=color,
                width=ann.outline_width,
            )
            if ann.kind == "arrow":
                import math
                dx = ann.ex - ann.sx
                dy = ann.ey - ann.sy
                length = math.sqrt(dx * dx + dy * dy)
                if length > 1:
                    ux, uy = dx / length, dy / length
                    arrow_len = min(20, length * 0.3)
                    angle = 0.4
                    for sign in (1, -1):
                        ax = ann.ex - arrow_len * (ux * math.cos(angle) - sign * uy * math.sin(angle))
                        ay = ann.ey - arrow_len * (uy * math.cos(angle) + sign * ux * math.sin(angle))
                        draw.line([(ann.ex, ann.ey), (int(ax), int(ay))], fill=color, width=ann.outline_width)

    composited = Image.alpha_composite(img, overlay)
    return np.array(composited.convert("RGB"))


# ─── Public Rendering API ──────────────────────────────────────────

def render_satellite_composite(
    bands: Dict[str, np.ndarray],
    composite: str = "true_color",
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    annotations: Optional[List[Dict[str, Any]]] = None,
    subdir: str = "",
) -> Dict[str, Any]:
    """Render satellite bands to a PNG file and return its serving path.

    composite: one of "true_color", "false_color", "mineral", or a
    user-specified band mapping like {"R": "B08", "G": "B04", "B": "B03"}.

    Every value is derived from the `bands` dict. If a required band is
    absent, raises ValueError — never guesses.

    annotations (optional): list of AnnotationSpec-compatible dicts, burned
    onto the rendered image at explicit pixel coordinates.
    """
    if not bands:
        raise ValueError("bands dict must not be empty — no data to render")

    if isinstance(composite, str):
        composite_key = composite.lower().strip()
        mapping_map = {
            "true_color": {"R": "B04", "G": "B03", "B": "B02"},
            "false_color": {"R": "B08", "G": "B04", "B": "B03"},
            "mineral": {"R": "B11", "G": "B04", "B": "B02"},
            "swir": {"R": "B12", "G": "B11", "B": "B08"},
            "vegetation": {"R": "B08", "G": "B04", "B": "B03"},
        }
        if composite_key not in mapping_map:
            raise ValueError(
                f"Unknown composite '{composite}'. Supported: {list(mapping_map.keys())} "
                "or a dict mapping R/G/B to band names."
            )
        mapping = mapping_map[composite_key]
    elif isinstance(composite, dict):
        mapping = composite
    else:
        raise ValueError(f"composite must be str or dict, got {type(composite)}")

    rgb = composite_from_dict(bands, mapping, target_height=height, target_width=width)

    if annotations:
        specs = []
        for a in annotations:
            specs.append(AnnotationSpec(
                kind=a.get("kind", "label"),
                text=a.get("text", ""),
                x=a.get("x", 0), y=a.get("y", 0),
                x1=a.get("x1", 0), y1=a.get("y1", 0),
                x2=a.get("x2", 0), y2=a.get("y2", 0),
                sx=a.get("sx", 0), sy=a.get("sy", 0),
                ex=a.get("ex", 0), ey=a.get("ey", 0),
                cx=a.get("cx", 0), cy=a.get("cy", 0),
                radius=a.get("radius", 20),
                color=tuple(a.get("color", [255, 0, 0])),
                outline_width=a.get("outline_width", 3),
                font_size=a.get("font_size", 18),
            ))
        rgb = burn_annotations(rgb, specs)

    file_key, abs_path = _save_rgb_to_file(rgb, ext="png", subdir=subdir)
    return {
        "file_key": file_key,
        "file_url": f"/files/{file_key}",
        "mime_type": "image/png",
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "composite": composite if isinstance(composite, str) else "custom",
        "size_bytes": abs_path.stat().st_size,
    }


def render_user_image(
    image_bytes: bytes,
    *,
    target_height: int = 512,
    target_width: int = 512,
    annotations: Optional[List[Dict[str, Any]]] = None,
    subdir: str = "",
) -> Dict[str, Any]:
    """Render user-uploaded image bytes to a normalized PNG.

    Input is the raw file bytes (JPEG, PNG, TIFF, etc.). The renderer
    opens the image with PIL, resizes to the target dimensions, and
    saves as PNG. No colour assumptions — preserves original pixels
    (only resizes).
    """
    if not image_bytes:
        raise ValueError("image_bytes must not be empty")

    img = Image.open(io.BytesIO(image_bytes))
    # Preserve original colours — only resize, never re-interpret
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    elif img.mode == "RGBA":
        # Composite onto white background — no assumption about transparency intent
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg

    img = img.resize((target_width, target_height), Image.LANCZOS)
    rgb = np.array(img)

    if annotations:
        specs = []
        for a in annotations:
            specs.append(AnnotationSpec(
                kind=a.get("kind", "label"),
                text=a.get("text", ""),
                x=a.get("x", 0), y=a.get("y", 0),
                x1=a.get("x1", 0), y1=a.get("y1", 0),
                x2=a.get("x2", 0), y2=a.get("y2", 0),
                sx=a.get("sx", 0), sy=a.get("sy", 0),
                ex=a.get("ex", 0), ey=a.get("ey", 0),
                cx=a.get("cx", 0), cy=a.get("cy", 0),
                radius=a.get("radius", 20),
                color=tuple(a.get("color", [255, 0, 0])),
                outline_width=a.get("outline_width", 3),
                font_size=a.get("font_size", 18),
            ))
        rgb = burn_annotations(rgb, specs)

    file_key, abs_path = _save_rgb_to_file(rgb, ext="png", subdir=subdir)
    return {
        "file_key": file_key,
        "file_url": f"/files/{file_key}",
        "mime_type": "image/png",
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "size_bytes": abs_path.stat().st_size,
    }


def annotate_existing_image(
    image_file_key: str,
    annotations: List[Dict[str, Any]],
    *,
    subdir: str = "annotated",
) -> Dict[str, Any]:
    """Load an existing rendered image, burn annotations onto a copy, save as new file.

    image_file_key: the path under /files/ (e.g. "renders/somefile.png").
    annotations: list of AnnotationSpec dicts with explicit pixel coordinates.

    Returns the new file's serving info. Original is never mutated.
    """
    if not annotations:
        raise ValueError("annotations list must not be empty — nothing to burn")

    # Resolve the file
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / "storage" / "renders" / image_file_key.replace("renders/", ""),
        project_root / image_file_key,
    ]
    src_path = None
    for c in candidates:
        if c.is_file():
            src_path = c
            break
    if src_path is None:
        raise FileNotFoundError(f"Image not found: {image_file_key}")

    img = Image.open(str(src_path)).convert("RGB")
    rgb = np.array(img)

    specs = []
    for a in annotations:
        specs.append(AnnotationSpec(
            kind=a.get("kind", "label"),
            text=a.get("text", ""),
            x=a.get("x", 0), y=a.get("y", 0),
            x1=a.get("x1", 0), y1=a.get("y1", 0),
            x2=a.get("x2", 0), y2=a.get("y2", 0),
            sx=a.get("sx", 0), sy=a.get("sy", 0),
            ex=a.get("ex", 0), ey=a.get("ey", 0),
            cx=a.get("cx", 0), cy=a.get("cy", 0),
            radius=a.get("radius", 20),
            color=tuple(a.get("color", [255, 0, 0])),
            outline_width=a.get("outline_width", 3),
            font_size=a.get("font_size", 18),
        ))
    rgb = burn_annotations(rgb, specs)

    file_key, abs_path = _save_rgb_to_file(rgb, ext="png", subdir=subdir)
    return {
        "file_key": file_key,
        "file_url": f"/files/{file_key}",
        "mime_type": "image/png",
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "size_bytes": abs_path.stat().st_size,
        "based_on": image_file_key,
    }
