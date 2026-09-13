"""
Roboflow / NVIDIA computer-vision client for mining and geology.

Runs object-detection and classification models through either:
  * Roboflow's hosted inference API, or
  * a local edge inference server (Roboflow Inference on an NVIDIA Jetson /
    GPU box with TensorRT acceleration) at a configurable URL.

Both speak the same REST contract, so switching models or environments never
changes calling code. When no API key (or model) is configured the client
returns empty results honestly — it never fabricates detections.
"""
import io
import logging
import base64
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ai_os.vision.roboflow")


def _raw_image_bytes(image_bytes: bytes) -> bytes:
    """Return JPEG bytes the inference API can consume (downscale to bound size)."""
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=82)
            return out.getvalue()
    except Exception:
        return image_bytes


class RoboflowVision:
    """Minimal, dependency-light wrapper around the Roboflow/edge inference API."""

    def __init__(
        self,
        api_key: str = "",
        inference_url: str = "",
        rock_detector: str = "",
        mineral_detector: str = "",
        ppe_detector: str = "",
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.inference_url = (inference_url or "").strip().rstrip("/")
        self.rock_detector = (rock_detector or "").strip()
        self.mineral_detector = (mineral_detector or "").strip()
        self.ppe_detector = (ppe_detector or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and (self.rock_detector or self.mineral_detector or self.ppe_detector))

    @property
    def mode(self) -> str:
        if not self.configured:
            return "disabled"
        return "edge" if self.inference_url else "hosted"

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "mode": self.mode,
            "models": {
                "rock": self.rock_detector,
                "mineral": self.mineral_detector,
                "ppe": self.ppe_detector,
            },
        }

    def _post(self, model_id: str, image_bytes: bytes, endpoint: str = "detect") -> Optional[Dict[str, Any]]:
        if not self.api_key or not model_id:
            return None
        import urllib.request

        base = self.inference_url or f"https://{endpoint}.roboflow.com"
        url = f"{base}/{model_id}?api_key={self.api_key}"
        body = _raw_image_bytes(image_bytes)
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "image/jpeg")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read().decode("utf-8", "ignore")
            import json
            data = json.loads(payload)
            if isinstance(data, dict) and data.get("error"):
                logger.warning(f"Roboflow inference error: {data.get('error')}")
                return None
            return data
        except Exception as e:
            logger.warning(f"Roboflow inference failed ({model_id}): {e}")
            return None

    def detect(self, model_id: str, image_bytes: bytes, task: str = "detect") -> List[Dict[str, Any]]:
        """Run object detection and normalise to {x,y,width,height,class,confidence}."""
        data = self._post(model_id, image_bytes, endpoint="detect")
        if not data or "predictions" not in data:
            return []
        out = []
        for p in data.get("predictions", []):
            x = float(p.get("x", 0) or 0)
            y = float(p.get("y", 0) or 0)
            w = float(p.get("width", 0) or 0)
            h = float(p.get("height", 0) or 0)
            out.append({
                "task": task,
                "class": str(p.get("class", "object")),
                "confidence": round(float(p.get("confidence", 0) or 0), 4),
                "x": round(x - w / 2, 2),
                "y": round(y - h / 2, 2),
                "width": round(w, 2),
                "height": round(h, 2),
            })
        return out

    def classify(self, model_id: str, image_bytes: bytes, task: str = "classification") -> List[Dict[str, Any]]:
        """Run classification and normalise to a labelled, confidence-ordered list."""
        data = self._post(model_id, image_bytes, endpoint="classify")
        if not data or "predictions" not in data:
            return []
        preds = data.get("predictions", [])
        if isinstance(preds, dict):
            preds = [
                {"class": k, "confidence": v} for k, v in preds.items()
            ]
        out = []
        for p in sorted(preds, key=lambda r: float(r.get("confidence", 0) or 0), reverse=True):
            out.append({
                "task": task,
                "class": str(p.get("class", "unknown")),
                "confidence": round(float(p.get("confidence", 0) or 0), 4),
            })
        return out

    def analyze_scene(self, image_bytes: bytes) -> Dict[str, Any]:
        """Run every configured geology/safety model against a scene.

        Returns honest results: an empty list per task when the model or key is
        not configured, or when inference fails. Never invented detections.
        """
        detections: List[Dict[str, Any]] = []
        classifications: List[Dict[str, Any]] = []
        if self.rock_detector:
            detections += self.detect(self.rock_detector, image_bytes, task="rock")
        if self.mineral_detector:
            detections += self.detect(self.mineral_detector, image_bytes, task="mineral")
        if self.ppe_detector:
            detections += self.detect(self.ppe_detector, image_bytes, task="ppe")
        return {
            "provider": self.mode,
            "configured": self.configured,
            "detections": detections,
            "classifications": classifications,
        }

    def base64_of(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")