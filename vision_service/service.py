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
from typing import Dict, Any, Optional

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
