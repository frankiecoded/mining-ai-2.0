"""
Vision Service - Image analysis, OCR, and multimodal AI for mining operations.
Processes conveyor belts, rock samples, mine maps, invoices, and geological images.

Data policy: this service NEVER fabricates OCR text, mineralogy, or analysis.
If no real engine (or LLM) can read the image, it returns honest empty/``None``
results instead of inventing content.
"""
import io
import logging
import shutil
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ai_os.vision")


class VisionService:
    """Vision Service with OCR, object analysis, and multimodal AI capabilities."""

    def __init__(self):
        self.ocr_available = False
        self.easyocr_available = False
        try:
            import pytesseract
            # pytesseract is only usable if the tesseract binary is installed too.
            self.ocr_available = shutil.which("tesseract") is not None
            if not self.ocr_available:
                logger.warning("pytesseract present but 'tesseract' binary not found - OCR disabled")
        except ImportError:
            pass
        try:
            import easyocr
            self.easyocr_available = True
        except ImportError:
            pass

    def run_ocr(self, image_bytes: bytes, file_name: Optional[str] = None) -> str:
        """Extract text from images using the best REAL OCR engine available.

        Returns an empty string when no engine could produce genuine text.
        Never returns fabricated content.
        """
        logger.info(f"OCR analysis on {len(image_bytes)} bytes, file: {file_name}")

        if self.easyocr_available:
            try:
                import easyocr
                import numpy as np
                from PIL import Image

                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img_np = np.array(img)
                reader = easyocr.Reader(["en"], gpu=False)
                results = reader.readtext(img_np)
                text = " ".join([r[1] for r in results if r[1] and r[1].strip()])
                if text.strip():
                    return text
            except Exception as e:
                logger.warning(f"EasyOCR failed: {e}")

        if self.ocr_available:
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(io.BytesIO(image_bytes))
                text = pytesseract.image_to_string(img)
                if text.strip():
                    return text
            except Exception as e:
                logger.warning(f"Tesseract failed: {e}")

        logger.warning(f"No real OCR text produced for '{file_name}' ({len(image_bytes)} bytes)")
        return ""

    def analyze_image_objects(self, image_bytes: bytes, image_type: str = "general") -> Dict[str, Any]:
        """Analyze an image using REAL data only.

        Attempts a genuine multimodal-LLM read of the actual pixels. If no real
        analysis can be produced, returns an honest ``analysis_available: False``
        record — never hardcoded mineralogy or assumptions.
        """
        logger.info(f"Object analysis for type: '{image_type}'")

        pixels = {}
        try:
            from PIL import Image
            with Image.open(io.BytesIO(image_bytes)) as img:
                pixels = {
                    "width": img.width,
                    "height": img.height,
                    "format": (img.format or "").upper(),
                }
        except Exception as e:
            logger.warning(f"Image metadata read failed: {e}")

        # Real analysis via the multimodal LLM (reads the actual image).
        try:
            result = self.analyze_multimodal(
                image_bytes,
                "Describe exactly what is visible in this image. Be factual and "
                "specific: identify any readable text, equipment, terrain, rocks, "
                "documents, or labels. Do not guess at values that are not visible. "
                "If nothing can be determined, say so.",
                file_name=image_type,
            )
            if result and "Image analysis error" not in result and "analysis error" not in result.lower():
                return {
                    "object_type": "ai_interpreter",
                    "analysis_available": True,
                    "description": result,
                    "pixels": pixels,
                }
        except Exception as e:
            logger.warning(f"Multimodal analysis failed: {e}")

        return {
            "object_type": "unavailable",
            "analysis_available": False,
            "pixels": pixels,
            "reason": "No OCR/vision data could be produced for this image. Only real "
                       "image metadata is reported; no content was assumed.",
        }

    # ─────────────────────────────────────────────────────────────────────
    # Geology vision: Roboflow/NVIDIA CV + multimodal LLM narration.
    # ─────────────────────────────────────────────────────────────────────

    def _roboflow(self):
        """Lazily build the Roboflow/edge CV client from configured settings."""
        try:
            from vision_service.roboflow import RoboflowVision
            from backend.config import settings
            return RoboflowVision(
                api_key=settings.ROBOFLOW_API_KEY,
                inference_url=settings.ROBOFLOW_INFERENCE_URL,
                rock_detector=settings.ROBOFLOW_ROCK_DETECTOR,
                mineral_detector=settings.ROBOFLOW_MINERAL_DETECTOR,
                ppe_detector=settings.ROBOFLOW_PPE_DETECTOR,
            )
        except Exception as e:
            logger.warning(f"Roboflow client unavailable: {e}")
            return None

    def _image_stats(self, image_bytes: bytes) -> Dict[str, Any]:
        """Cheap colour/structure statistics used for live-frame narration when
        no CV model is configured. Real pixels only."""
        try:
            from PIL import Image
            import numpy as np
            import io as _io
            with Image.open(_io.BytesIO(image_bytes)).convert("RGB") as img:
                if img.width * img.height > 64_000:
                    img.thumbnail((256, 256), Image.Resampling.LANCZOS)
                arr = np.asarray(img).astype(float)
                r, g, b = arr[..., 0].mean(), arr[..., 1].mean(), arr[..., 2].mean()
                brightness = (r * 0.299 + g * 0.587 + b * 0.114)
                # Simple green-ratio proxy for vegetation cover.
                denom = (r + g + b + 1e-6)
                green_ratio = g / denom
                return {
                    "rgb": [round(float(r)), round(float(g)), round(float(b))],
                    "brightness": round(float(brightness)),
                    "green_ratio": round(float(green_ratio), 3),
                }
        except Exception:
            return {}

    def analyze_scene_detections(self, image_bytes: bytes) -> Dict[str, Any]:
        """Run all configured CV models (rock / mineral / safety)."""
        rf = self._roboflow()
        if not rf or not rf.configured:
            return {"provider": "disabled", "configured": False, "detections": []}
        try:
            return rf.analyze_scene(image_bytes)
        except Exception as e:
            logger.warning(f"CV scene analysis failed: {e}")
            return {"provider": "disabled", "configured": False, "detections": []}

    def _rock_lexicon(self) -> Dict[str, str]:
        """Default geological reading for common rock/ore classes seen in CV
        models. Mapped from real class labels when the detection is authoritative."""
        return {
            "granite": "light, coarse-grained intrusive rock rich in quartz and feldspar",
            "basalt": "dark, fine-grained volcanic rock of mafic composition",
            "sandstone": "clastic sedimentary rock with visible sand-grade grains",
            "quartz": "silica-rich rock, often a mineralisation host",
            "quartz_vein": "silica-filled fracture typical of gold-bearing vein systems",
            "limestone": "carbonate sedimentary rock",
            "schist": "metamorphic foliated rock with aligned minerals",
            "gneiss": "high-grade metamorphic banded rock",
            "conglomerate": "sedimentary rock with rounded clasts in a matrix",
            "laterite": "iron-rich weathered zone, common in tropical regolith",
            "ore": "economic mineralisation",
            "pyrite": "iron sulphide, commonly associated with gold mineralisation",
            "chalcopyrite": "copper-iron sulphide — a primary copper ore",
            "bornite": "copper sulphide with a distinctive blue-purple tarnish",
            "galena": "lead sulphide with metallic lustre",
            "hematite": "iron oxide, common in banded iron formations",
            "hematite_rock": "iron oxide rock",
            "magnetite": "strongly magnetic iron oxide ore",
            "gold": "visible gold mineralisation",
            "malachite": "green copper carbonate, a strong copper surface indicator",
            "azurite": "blue copper carbonate, a copper oxide indicator",
            "manganese": "dark manganese oxide staining",
            "cassiterite": "tin oxide ore",
            "bauxite": "aluminium ore formed in tropical weathering",
            "soil": "surface regolith and soil cover",
            "rock_face": "exposed rock outcrop",
            "outcrop": "exposed bedrock at surface",
            "drill_core": "drill core sample material",
            "sample_bag": "collected rock sample bag",
        }

    def _normalize_detections(self, detections: list, image_bytes: bytes) -> list:
        """Convert pixel box coords to 0..1 view-space (the downscaled image the
        CV model actually saw), so the client can draw boxes over any display size."""
        ow, oh = 1280, 1280
        try:
            from PIL import Image
            import io as _io
            with Image.open(_io.BytesIO(image_bytes)) as img:
                w, h = img.size
                scale = min(1280.0 / max(w, h), 1.0)
                ow, oh = round(w * scale), round(h * scale)
        except Exception:
            pass
        out = []
        for d in detections:
            try:
                x = float(d.get("x", 0)) / ow
                y = float(d.get("y", 0)) / oh
                w = float(d.get("width", 0)) / ow
                h = float(d.get("height", 0)) / oh
            except (TypeError, ValueError):
                x, y, w, h = 0, 0, 0, 0
            out.append({**d, "x": round(max(0, min(1, x)), 4),
                        "y": round(max(0, min(1, y)), 4),
                        "width": round(max(0, min(1, w)), 4),
                        "height": round(max(0, min(1, h)), 4)})
        return out

    def _rule_narration(self, detections: list, stats: dict) -> List[str]:
        """Build a short, factual narration sentence set from detections + pixel
        statistics. Used live when the LLM path is throttled."""
        sentences: List[str] = []
        if stats.get("green_ratio", 0) > 0.42:
            sentences.append("Heavy vegetation cover is limiting rock exposure right now.")
        lexicon = self._rock_lexicon()
        for d in detections[:4]:
            cls = str(d.get("class", "rock")).lower()
            conf = d.get("confidence", 0)
            reading = lexicon.get(cls)
            if reading:
                sentences.append(f"{cls} detected with {round(float(conf or 0) * 100)}% confidence — {reading}.")
        if not sentences:
            sentences.append("Scene is reading as mostly unclassified ground cover and sky.")
        return sentences

    def live_frame(self, image_bytes: bytes, include_llm: bool = True,
                   ambient: str = "") -> Dict[str, Any]:
        """Analyse a live camera frame for the geology feed.

        Returns narration-ready text (spoken aloud by the client) plus structured
        detections. Narration is REAL: either CV detections or this scene's
        actual pixels via the vision LLM.
        """
        detections_result = self.analyze_scene_detections(image_bytes)
        detections = self._normalize_detections(detections_result.get("detections", []), image_bytes)
        stats = self._image_stats(image_bytes)

        narration = ""
        if detections:
            narration = "\n".join(self._rule_narration(detections, stats))
        elif include_llm:
            context = f" Live-context hint: {ambient}" if ambient else ""
            narration = self.analyze_multimodal(
                image_bytes,
                "You are a field geologist narrating live in first person. In one or two "
                "short, spoken sentences, describe what is geologically visible: rock type, "
                "weathering, structure, veining, or mineralisation. Only state what you can "
                "actually see. If nothing geological is visible, say so plainly. Do not repeat "
                "the prompt." + context,
                file_name="live_frame",
            )
        if not narration:
            narration = "Still analysing this scene before I can comment on the geology."

        return {
            "provider": detections_result.get("provider", "llm"),
            "detections": detections,
            "stats": stats,
            "narration": narration,
            "speakable": narration,
        }

    def geology_report(self, image_bytes: bytes, name: str = "sample") -> Dict[str, Any]:
        """Full single-image geological report combining CV + vision-LLM read."""
        detections_result = self.analyze_scene_detections(image_bytes)
        detections = self._normalize_detections(detections_result.get("detections", []), image_bytes)
        stats = self._image_stats(image_bytes)

        llm = self.analyze_multimodal(
            image_bytes,
            "Act as a senior exploration geologist. Produce a concise, factual field "
            "assessment of this geological image. Cover: (1) rock type and lithology, "
            "(2) structural features, (3) visible alteration or mineralisation, (4) "
            "weathering and terrain, (5) recommended field test (e.g. magnetic sus, "
            "acid test, panning). Only describe what is actually visible; never invent "
            "assay values. Keep it under 180 words as spoken prose.",
            file_name=name,
        )

        return {
            "provider": detections_result.get("provider", "llm"),
            "configured": detections_result.get("configured", False),
            "detections": detections,
            "stats": stats,
            "assessment": llm,
            "filename": name,
        }

    def _downscale_image(self, image_bytes: bytes, max_size: int = 768) -> bytes:
        """Downscale + re-encode an image to bound upload size and vision tokens.

        Falls back to the original bytes if PIL cannot process the image, so OCR
        and analysis paths never break on odd formats.
        """
        try:
            from PIL import Image, ImageOps
            import io as _io

            with Image.open(_io.BytesIO(image_bytes)) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                out = _io.BytesIO()
                img.save(out, format="JPEG", quality=80)
                return out.getvalue()
        except Exception:
            return image_bytes

    def analyze_multimodal(self, image_bytes: bytes, prompt: str, file_name: Optional[str] = None) -> str:
        """Use the dedicated HF vision-language model for detailed image analysis.

        Downscales the image first to minimise vision tokens, and passes a small
        max_tokens so the description stays tight (saves HF spend).
        """
        try:
            import base64
            image_b64 = base64.b64encode(self._downscale_image(image_bytes)).decode("utf-8")

            from local_model.adapter import LocalLLMAdapter
            from backend.config import settings
            from langchain_core.messages import HumanMessage

            llm = LocalLLMAdapter(
                model_name=settings.VISION_LLM_MODEL or settings.LOCAL_LLM_MODEL,
                api_url=settings.VISION_LLM_URL or settings.LOCAL_LLM_URL,
            )

            message = HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ])

            result = llm.invoke([message], tools=[], max_tokens=256)
            return result.content if hasattr(result, "content") else str(result)
        except Exception as e:
            logger.error(f"Multimodal analysis failed: {e}")
            return f"Image analysis error: {str(e)}. Falling back to basic analysis."
