import os
import json
import csv
import io
import hashlib
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ai_os.commands.ingestion")

PRIVATE_DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "private_datasets")
MAX_FILE_SIZE = 50 * 1024 * 1024
SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/csv": "csv",
    "text/markdown": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/json": "json",
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
}


def ensure_private_dir():
    os.makedirs(PRIVATE_DATASETS_DIR, exist_ok=True)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            return "\n\n".join(text_parts) if text_parts else "No text extracted from PDF."
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return f"PDF text extraction failed: {str(e)[:100]}"


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) if paragraphs else "No text found in DOCX."
    except Exception as e:
        logger.warning(f"DOCX extraction failed: {e}")
        return f"DOCX extraction failed: {str(e)[:100]}"


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(file_bytes))
        return df.to_string(index=False)
    except Exception as e:
        logger.warning(f"XLSX extraction failed: {e}")
        return f"XLSX extraction failed: {str(e)[:100]}"


def extract_text_from_csv(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return "Empty CSV file."
        headers = rows[0]
        lines = [", ".join(headers)]
        for row in rows[1:51]:
            lines.append(", ".join(row))
        if len(rows) > 51:
            lines.append(f"... ({len(rows) - 1} total rows)")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"CSV extraction failed: {e}")
        return f"CSV extraction failed: {str(e)[:100]}"


def extract_text_from_image(file_bytes: bytes, file_name: str = "") -> str:
    try:
        from vision_service.service import VisionService
        vision = VisionService()
        ocr_text = vision.run_ocr(file_bytes, file_name)
        analysis = vision.analyze_image_objects(file_bytes, file_name)
        return f"OCR Text:\n{ocr_text}\n\nImage Analysis:\n{json.dumps(analysis, indent=2)}"
    except Exception as e:
        logger.warning(f"Image extraction failed: {e}")
        return f"Image analysis failed: {str(e)[:100]}"


def chunk_text(text: str, max_chars: int = 512, overlap: int = 64) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
        if start + overlap >= len(text):
            break
    return chunks


def convert_file_to_dataset(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    category: str = "general",
    description: str = ""
) -> Dict[str, Any]:
    if len(file_bytes) > MAX_FILE_SIZE:
        return {"success": False, "error": f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB."}

    file_ext = SUPPORTED_MIME_TYPES.get(mime_type, "")
    if not file_ext:
        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "unknown"

    extracted_text = ""
    if mime_type == "application/pdf" or file_ext == "pdf":
        extracted_text = extract_text_from_pdf(file_bytes)
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_ext == "docx":
        extracted_text = extract_text_from_docx(file_bytes)
    elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or file_ext == "xlsx":
        extracted_text = extract_text_from_xlsx(file_bytes)
    elif mime_type == "text/csv" or file_ext == "csv":
        extracted_text = extract_text_from_csv(file_bytes)
    elif mime_type == "application/json" or file_ext == "json":
        try:
            data = json.loads(file_bytes)
            extracted_text = json.dumps(data, indent=2)[:50000]
        except Exception:
            extracted_text = file_bytes.decode("utf-8", errors="replace")[:50000]
    elif mime_type.startswith("image/") or file_ext in ("png", "jpg", "jpeg"):
        extracted_text = extract_text_from_image(file_bytes, file_name)
    elif mime_type == "text/plain" or file_ext in ("txt", "md"):
        extracted_text = file_bytes.decode("utf-8", errors="replace")
    else:
        extracted_text = file_bytes.decode("utf-8", errors="replace")[:50000]

    if not extracted_text or len(extracted_text.strip()) < 10:
        return {"success": False, "error": "Could not extract meaningful text from this file."}

    chunks = chunk_text(extracted_text)

    dataset = {
        "metadata": {
            "source_file": file_name,
            "mime_type": mime_type,
            "category": category,
            "description": description,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "original_size_bytes": len(file_bytes),
            "text_length": len(extracted_text),
            "chunks": len(chunks)
        },
        "content": {
            "full_text": extracted_text[:100000],
            "chunks": [{"index": i, "text": c} for i, c in enumerate(chunks)]
        }
    }

    ensure_private_dir()
    cat_dir = os.path.join(PRIVATE_DATASETS_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)

    file_hash = hashlib.md5(file_name.encode()).hexdigest()[:8]
    base_name = os.path.splitext(file_name)[0]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
    dataset_name = f"{safe_name}_{file_hash}.json"
    dataset_path = os.path.join(cat_dir, dataset_name)

    with open(dataset_path, "w") as f:
        json.dump(dataset, f, indent=2)

    return {
        "success": True,
        "dataset_name": dataset_name,
        "category": category,
        "path": os.path.relpath(dataset_path, PRIVATE_DATASETS_DIR),
        "text_length": len(extracted_text),
        "chunks": len(chunks),
        "preview": extracted_text[:200]
    }


def ingest_text_directly(
    text: str,
    source_name: str,
    category: str = "general",
    description: str = ""
) -> Dict[str, Any]:
    if not text or len(text.strip()) < 10:
        return {"success": False, "error": "Text too short to create a dataset."}

    chunks = chunk_text(text)

    dataset = {
        "metadata": {
            "source_file": source_name,
            "mime_type": "text/plain",
            "category": category,
            "description": description,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "original_size_bytes": len(text.encode()),
            "text_length": len(text),
            "chunks": len(chunks)
        },
        "content": {
            "full_text": text[:100000],
            "chunks": [{"index": i, "text": c} for i, c in enumerate(chunks)]
        }
    }

    ensure_private_dir()
    cat_dir = os.path.join(PRIVATE_DATASETS_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)

    file_hash = hashlib.md5(source_name.encode()).hexdigest()[:8]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in os.path.splitext(source_name)[0])
    dataset_name = f"{safe_name}_{file_hash}.json"
    dataset_path = os.path.join(cat_dir, dataset_name)

    with open(dataset_path, "w") as f:
        json.dump(dataset, f, indent=2)

    return {
        "success": True,
        "dataset_name": dataset_name,
        "category": category,
        "path": os.path.relpath(dataset_path, PRIVATE_DATASETS_DIR),
        "text_length": len(text),
        "chunks": len(chunks),
        "preview": text[:200]
    }
