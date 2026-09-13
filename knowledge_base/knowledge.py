"""Adapter: bridges main.py knowledge endpoints to services/knowledge_base.py."""

import os
import re
import math
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Domain lexicons for entity extraction ────────────────────────────────
_MINERALS = {
    "gold", "silver", "copper", "zinc", "lead", "iron", "tin", "nickel", "cobalt",
    "titanium", "tungsten", "manganese", "chromium", "platinum", "palladium",
    "rhodium", "ruthenium", "iridium", "osmium", "diamond", "tanzanite",
    "emerald", "ruby", "sapphire", "tsavorite", "garnet", "amethyst", "tourmaline",
    "quartz", "feldspar", "mica", "calcite", "dolomite", "pyrite", "chalcopyrite",
    "galena", "sphalerite", "magnetite", "hematite", "goethite", "limonite",
    "bauxite", "magnetite", "chalcopyrite", "bornite", "covellite", "molybdenite",
    "wolframite", "cassiterite", "coltan", "monazite", "xenotime", "bastnasite",
    "uranium", "thorium", "lithium", "beryllium", "niobium", "tantalum", "rare earth",
}

_EQUIPMENT = {
    "excavator", "bulldozer", "loader", "dump truck", "haul truck", "drill rig",
    "jumbo", "longhole drill", "bolter", "shotcrete", "crusher", "grinder",
    "ball mill", "sag mill", "rod mill", "hydrocyclone", "leach pad", "heap leach",
    "cil tank", "carbon", "elution", "electrowinning", "smelter", "refinery",
    "conveyor", "pump", "agitator", "compressor", "ventilation", "piping",
    "shaker table", "spiral", "jig", "froth flotation", "magnetic separator",
    "gravity separator", "screen", "feeder", "hopper", "chute", "clarifier",
    "thickener", "filter press", "dewatering", "tailings dam", "waste rock",
    "dozer", "grader", "water truck", "service vehicle", "scale", "weighbridge",
}

_CHEMICALS = {
    "cyanide", "sodium cyanide", "caustic soda", "sulphuric acid", "sulfuric acid",
    "hydrochloric acid", "nitric acid", "ammonia", "lime", "quicklime",
    "hydrated lime", "soda ash", "flocculant", "coagulant", "xanthate",
    "frother", "collector", "activator", "depressant", "mercury", "lead nitrate",
    "sodium sulfide", "copper sulfate", "iron sulfate", "zinc dust", "carbon",
    "activated carbon", "resin", "ion exchange", "reagent", "flotation reagent",
    "diesel", "fuel oil", "lubricant", "glycol", "ethylene glycol",
    "phosphoric acid", "sodium hydroxide", "potassium hydroxide", "hydrogen peroxide",
}

_LOCATIONS = {
    "kapoeta", "camp 15", "camp15", "juba", "nairobi", "kampala", "dar es salaam",
    "kigali", "bujumbura", "lilongwe", "harare", "maputo", "lusaka", "addis ababa",
    "mombasa", "dar", "tanga", "morogoro", "mbeya", "arusha", "mwanza",
    "kipushi", "kamoto", "kolwezi", "likasi", "lubumbashi", "katanga",
    "tanzania", "kenya", "uganda", "drc", "congo", "zimbabwe", "mozambique",
    "zambia", "malawi", "ethiopia", "south sudan", "sudan", "rwanda", "burundi",
}

_PROCESSES = {
    "mining", "drilling", "blasting", "loading", "hauling", "crushing", "grinding",
    "milling", "flotation", "leaching", "cyanidation", "carbon-in-leach", "cil",
    "carbon-in-pulp", "cip", "heap leach", "gravity separation", "magnetic separation",
    "electrowinning", "smelting", "refining", "assaying", "exploration",
    "drilling", "trenching", "bulk sampling", "feasibility", "pre-feasibility",
    "JORC", "NI 43-101", "resource estimation", "geological mapping",
    "geophysical survey", "geochemical sampling", "diamond drilling",
    "reverse circulation", "rc drilling", "core drilling", "pitting",
    "trenching", "dewatering", "ventilation", "ground support",
    "shotcreting", "bolting", "scaling", "mucking", "backfilling",
}


class KnowledgeBase:
    """Thin wrapper around services.knowledge_base.KnowledgeBase that matches
    the interface expected by the FastAPI endpoints in main.py."""

    def __init__(self, tenant_id: Optional[str] = None):
        from services.knowledge_base import KnowledgeBase as _KB
        self._kb = _KB()
        self._tenant_id = tenant_id

    def list_documents(self) -> list[dict[str, Any]]:
        return self._kb.list_all_documents(tenant_id=self._tenant_id)

    def get_statistics(self) -> dict[str, Any]:
        return self._kb.get_statistics(tenant_id=self._tenant_id)

    def search(self, query: str, category: Optional[str] = None,
               file_type: Optional[str] = None) -> list[dict[str, Any]]:
        if category:
            return self._kb.search_by_category(category, tenant_id=self._tenant_id)
        if file_type:
            return self._kb.search_by_type(file_type)
        return self._kb.search(query, tenant_id=self._tenant_id)

    def get_recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._kb.get_recent_documents(limit=limit, tenant_id=self._tenant_id)

    # ─── Read ──────────────────────────────────────────────────────────────

    def read_document(self, doc_id: Optional[str] = None,
                      file_path: Optional[str] = None) -> dict[str, Any]:
        doc = None
        if doc_id:
            doc = self._kb.get_document(doc_id)
        if not doc and file_path and os.path.exists(file_path):
            doc = self._kb.add_document(file_path, os.path.basename(file_path))
        if not doc:
            return {"error": "Document not found"}

        text = doc.content_text or ""
        content = text[:10000]
        word_count = len(content.split()) if content.strip() else 0

        return {
            "doc_id": doc.doc_id,
            "filename": doc.original_filename,
            "title": doc.title,
            "content_text": content,
            "category": doc.category,
            "tags": doc.tags,
            "file_type": doc.file_type,
            "metadata": doc.metadata,
            "word_count": word_count,
            "page_count": self._estimate_pages(word_count),
            "created_at": doc.created_at,
            "summary": self._kb.generate_summary(text)[:2000] if text else "",
            "key_findings": self._extract_key_findings(text)[:8],
            "sections": self._extract_sections(content),
            "key_terms": self._kb.extract_key_terms(text)[:20] if text else [],
            "mining_relevance": self._assess_mining_relevance(text),
            "relevance_to_mining": self._assess_mining_relevance(text),
            "entities": self._extract_entities(text),
        }

    # ─── Deep Understand ───────────────────────────────────────────────────

    def understand_document(self, doc_id: Optional[str] = None,
                            file_path: Optional[str] = None) -> dict[str, Any]:
        doc = None
        if doc_id:
            doc = self._kb.get_document(doc_id)
        if not doc and file_path and os.path.exists(file_path):
            doc = self._kb.add_document(file_path, os.path.basename(file_path))
        if not doc:
            return {"error": "Document not found"}

        text = doc.content_text or ""
        content = text[:10000]
        word_count = doc.metadata.get("word_count", len(content.split())) if content.strip() else 0

        summary = self._kb.generate_summary(text)[:2000] if text else ""
        terms = self._kb.extract_key_terms(text)[:30] if text else []

        # For deep understand, also build a richer summary via key sentences
        sentences = [
            s.strip() for s in re.split(r'[.!?\n]+', text.replace("\n", " "))
            if len(s.strip()) > 20
        ]
        key_sentences = sentences[:15]

        return {
            "doc_id": doc.doc_id,
            "filename": doc.original_filename,
            "title": doc.title,
            "category": doc.category,
            "content_text": content,
            "summary": summary,
            "key_terms": terms,
            "key_sentences": key_sentences,
            "key_findings": self._extract_key_findings(text)[:10],
            "sections": self._extract_sections(content),
            "word_count": word_count,
            "page_count": self._estimate_pages(word_count),
            "mining_relevance": self._assess_mining_relevance(text),
            "relevance_to_mining": self._assess_mining_relevance(text),
            "entities": self._extract_entities(text),
        }

    def get_summary(self) -> dict[str, Any]:
        return self._kb.get_knowledge_summary()

    # ─── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_pages(word_count: int) -> int:
        return max(1, math.ceil(word_count / 300))

    @staticmethod
    def _assess_mining_relevance(text: str) -> float:
        """Return a 0.0-1.0 relevance score."""
        from services.knowledge_base import MINING_VOCABULARY
        text_lower = text.lower()
        hits = sum(1 for term in MINING_VOCABULARY if term.lower() in text_lower)
        total = len(MINING_VOCABULARY) or 1
        ratio = hits / total
        # Map to 0.0-1.0 with a reasonable curve
        return round(min(1.0, ratio * 3.0), 2)

    @staticmethod
    def _extract_key_findings(text: str) -> list[str]:
        """Extract the most information-dense sentences as key findings."""
        sentences = [
            s.strip() for s in re.split(r'[.!?\n]+', text.replace("\n", " "))
            if len(s.strip()) > 30
        ]
        # Rank by keyword density
        mining_kw = {"grade", "tonnes", "ore", "mineral", "production", "recovery",
                     "reserve", "resource", "drill", "assay", "geology", "fault",
                     "vein", "lode", "alluvial", "placer", "drill", "blast",
                     "crush", "mill", "leach", "gold", "copper", "yield", "cost",
                     "capex", "opex", "npv", "irr", "feasibility", "jorc",
                     "indicated", "inferred", "measured", "mh", "au", "cu", "zn"}
        scored = []
        for s in sentences:
            sl = s.lower()
            score = sum(1 for kw in mining_kw if kw in sl)
            # Also prefer sentences with numbers (data-rich)
            if re.search(r'\d', s):
                score += 1
            scored.append((score, s))
        scored.sort(reverse=True)
        return [s for _, s in scored[:10] if len(s) < 500]

    @staticmethod
    def _extract_sections(text: str) -> list[dict[str, Any]]:
        """Parse markdown-style headings or all-caps lines into sections."""
        sections: list[dict[str, Any]] = []
        lines = text.split("\n")
        current_heading = None
        current_level = 3
        current_content_lines: list[str] = []

        def _flush():
            nonlocal current_heading, current_level, current_content_lines
            if current_heading:
                content = "\n".join(current_content_lines).strip()
                if content:
                    sections.append({
                        "heading": current_heading,
                        "level": current_level,
                        "content": content[:800],
                    })
            current_content_lines = []

        for line in lines:
            stripped = line.strip()
            # Markdown heading
            m = re.match(r'^(#{1,6})\s+(.+)', stripped)
            if m:
                _flush()
                current_level = len(m.group(1))
                current_heading = m.group(2).strip()
                continue
            # ALL-CAPS line that looks like a heading (not data)
            if (stripped.isupper() and len(stripped) < 80 and len(stripped) > 3
                    and not re.match(r'^[\d\s,.\-:/]+$', stripped)):
                _flush()
                current_level = 2
                current_heading = stripped.title()
                continue
            # Numbered heading like "1. Introduction"
            m2 = re.match(r'^(\d+)[.)]\s+([A-Z][A-Za-z\s]{3,60})$', stripped)
            if m2:
                _flush()
                current_level = 2
                current_heading = m2.group(2).strip()
                continue
            current_content_lines.append(line)

        _flush()
        return sections[:20]

    @staticmethod
    def _extract_entities(text: str) -> dict[str, list[str]]:
        """Extract domain-specific entities from content text."""
        text_lower = text.lower()

        def _matches(lexicon: set[str]) -> list[str]:
            found = []
            for term in lexicon:
                if len(term) > 3 and term in text_lower:
                    found.append(term.title())
                elif len(term) <= 3 and re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                    found.append(term.upper())
            # Deduplicate while preserving order
            seen = set()
            result = []
            for item in found:
                key = item.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(item)
            return result

        return {
            "minerals": _matches(_MINERALS),
            "equipment": _matches(_EQUIPMENT),
            "locations": _matches(_LOCATIONS),
            "chemicals": _matches(_CHEMICALS),
            "processes": _matches(_PROCESSES),
        }
