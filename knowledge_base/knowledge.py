"""Adapter: bridges main.py knowledge endpoints to services/knowledge_base.py."""

import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
            results = self._kb.search_by_category(category, tenant_id=self._tenant_id)
            return results
        if file_type:
            return self._kb.search_by_type(file_type)
        return self._kb.search(query, tenant_id=self._tenant_id)

    def get_recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._kb.get_recent_documents(limit=limit, tenant_id=self._tenant_id)

    def read_document(self, doc_id: Optional[str] = None,
                      file_path: Optional[str] = None) -> dict[str, Any]:
        if doc_id:
            doc = self._kb.get_document(doc_id)
            if doc:
                return {
                    "doc_id": doc.doc_id,
                    "filename": doc.original_filename,
                    "title": doc.title,
                    "content": doc.content_text[:10000],
                    "category": doc.category,
                    "tags": doc.tags,
                    "file_type": doc.file_type,
                    "metadata": doc.metadata,
                    "created_at": doc.created_at,
                }
            return {"error": "Document not found"}
        if file_path and os.path.exists(file_path):
            doc = self._kb.add_document(file_path, os.path.basename(file_path))
            return {
                "doc_id": doc.doc_id,
                "filename": doc.original_filename,
                "title": doc.title,
                "content": doc.content_text[:10000],
                "category": doc.category,
                "tags": doc.tags,
                "file_type": doc.file_type,
            }
        return {"error": "File not found"}

    def understand_document(self, doc_id: Optional[str] = None,
                            file_path: Optional[str] = None) -> dict[str, Any]:
        doc = None
        if doc_id:
            doc = self._kb.get_document(doc_id)
        if not doc and file_path and os.path.exists(file_path):
            doc = self._kb.add_document(file_path, os.path.basename(file_path))
        if not doc:
            return {"error": "Document not found"}

        summary = self._kb.generate_summary(doc.content_text)
        terms = self._kb.extract_key_terms(doc.content_text)

        sentences = [s.strip() for s in doc.content_text.replace("\n", " ").split(".") if s.strip()]
        key_sentences = sentences[:10]

        return {
            "doc_id": doc.doc_id,
            "filename": doc.original_filename,
            "title": doc.title,
            "category": doc.category,
            "summary": summary[:2000],
            "key_terms": terms[:20],
            "key_sentences": key_sentences,
            "word_count": doc.metadata.get("word_count", len(doc.content_text.split())),
            "relevance_to_mining": self._assess_mining_relevance(doc.content_text),
        }

    def get_summary(self) -> dict[str, Any]:
        return self._kb.get_knowledge_summary()

    @staticmethod
    def _assess_mining_relevance(text: str) -> str:
        from services.knowledge_base import MINING_VOCABULARY
        text_lower = text.lower()
        hits = sum(1 for term in MINING_VOCABULARY if term.lower() in text_lower)
        total = len(MINING_VOCABULARY)
        ratio = hits / total if total > 0 else 0
        if ratio > 0.3:
            return "Highly relevant to mining operations"
        elif ratio > 0.15:
            return "Moderately relevant to mining"
        elif ratio > 0.05:
            return "Tangentially related to mining"
        return "Low direct relevance to mining"
