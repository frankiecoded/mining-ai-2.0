import json
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from memory_engine.types import MemoryEntry, MemoryType, MemoryManifest

logger = logging.getLogger("ai_os.memory_engine")


class MemoryEngine:
    """
    Persistent memory system with AI-powered recall, staleness detection,
    and multi-type memory taxonomy. Adapted from Claude Code's memdir system.

    Memory types:
      - operator: Operator roles, goals, preferences, shift patterns
      - feedback: Corrected approaches, confirmed workflows, lessons learned
      - project: Active incidents, deadlines, ongoing initiatives
      - reference: External systems, dashboards, contacts, SOPs
      - shift: Shift-specific context for handovers
      - equipment: Equipment-specific learnings, failure patterns, maintenance history
    """

    MEMORY_DIR = "data/memory"
    MEMORY_INDEX = "data/memory/MEMORY.md"
    MAX_MEMORY_ENTRIES = 500
    MAX_MEMORY_BYTES = 25 * 1024  # 25KB
    MAX_LINES = 200
    STALE_THRESHOLD_DAYS = 30
    RELEVANCE_THRESHOLD = 0.3

    def __init__(self, postgres_client=None, vector_client=None):
        self.postgres = postgres_client
        self.vector = vector_client
        self.manifest = MemoryManifest()
        self._loaded = False
        self._memory_dir = Path(self.MEMORY_DIR)
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = Path(self.MEMORY_INDEX)
        self._load_manifest()

    def _load_manifest(self):
        manifest_path = self._memory_dir / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                self.manifest = MemoryManifest(**data)
                self._loaded = True
                logger.debug(f"Loaded memory manifest: {len(self.manifest.entries)} entries")
            except Exception as e:
                logger.warning(f"Failed to load memory manifest: {e}")
                self.manifest = MemoryManifest()
        else:
            self.manifest = MemoryManifest()

    def _save_manifest(self):
        manifest_path = self._memory_dir / "manifest.json"
        try:
            manifest_path.write_text(self.manifest.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save memory manifest: {e}")

    def store(self, memory_type: MemoryType, title: str, content: str,
              tags: Optional[List[str]] = None, source: str = "conversation",
              confidence: float = 1.0, expires_at: Optional[datetime] = None,
              metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        entry = MemoryEntry(
            memory_type=memory_type,
            title=title,
            content=content,
            tags=tags or [],
            source=source,
            confidence=confidence,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        existing = self.manifest.search(title, memory_type=memory_type, limit=5)
        if existing and existing[0].title.lower() == title.lower():
            old = existing[0]
            old.content = content
            old.updated_at = datetime.utcnow()
            old.confidence = max(old.confidence, confidence)
            if tags:
                old.tags = list(set(old.tags + tags))
            entry = old
            logger.debug(f"Updated existing memory: {title}")
        else:
            self.manifest.add(entry)
            logger.debug(f"Stored new memory: {title} ({memory_type.value})")

        if len(self.manifest.entries) > self.MAX_MEMORY_ENTRIES:
            self._compact()
        self._save_manifest()
        self._persist_to_file(entry)
        return entry

    def recall(self, query: str, limit: int = 5, memory_type: Optional[MemoryType] = None,
               include_stale: bool = True) -> List[MemoryEntry]:
        results = self.manifest.search(query, memory_type=memory_type, limit=limit * 2)

        if not include_stale:
            results = [r for r in results if not r.is_stale(self.STALE_THRESHOLD_DAYS)]

        scored = []
        for entry in results:
            score = self._relevance_score(query, entry)
            if score >= self.RELEVANCE_THRESHOLD:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        selected = [entry for _, entry in scored[:limit]]

        for entry in selected:
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
        self._save_manifest()
        return selected

    def _relevance_score(self, query: str, entry: MemoryEntry) -> float:
        query_lower = query.lower()
        score = 0.0
        if query_lower in entry.title.lower():
            score += 4.0
        if query_lower in entry.content.lower():
            score += 2.0
        for tag in entry.tags:
            if query_lower in tag.lower():
                score += 3.0
        query_words = set(query_lower.split())
        entry_words = set(entry.title.lower().split() + entry.content.lower().split())
        overlap = len(query_words & entry_words)
        score += overlap * 0.5
        if entry.is_stale(self.STALE_THRESHOLD_DAYS):
            age_penalty = min(entry.age_days() / self.STALE_THRESHOLD_DAYS, 0.5)
            score *= (1 - age_penalty)
        score *= entry.confidence
        return score

    def recall_for_context(self, query: str, max_tokens: int = 2000) -> str:
        entries = self.recall(query, limit=5)
        if not entries:
            return ""
        sections = []
        for entry in entries:
            age_text = entry.freshness_text()
            stale_warning = ""
            if entry.is_stale(self.STALE_THRESHOLD_DAYS):
                stale_warning = f" [STALE - {age_text}]"
            section = f"[{entry.memory_type.value.upper()}] {entry.title}{stale_warning}\n{entry.content[:500]}"
            sections.append(section)
        result = "\n\n---\n\n".join(sections)
        if len(result) > max_tokens:
            result = result[:max_tokens]
        return result

    def _persist_to_file(self, entry: MemoryEntry):
        topic_file = self._memory_dir / f"{entry.memory_type.value}_{entry.title.lower().replace(' ', '_')[:50]}.md"
        try:
            lines = [
                f"---",
                f"type: {entry.memory_type.value}",
                f"title: {entry.title}",
                f"created: {entry.created_at.isoformat()}",
                f"updated: {entry.updated_at.isoformat()}",
                f"source: {entry.source}",
                f"confidence: {entry.confidence}",
                f"tags: {', '.join(entry.tags)}",
                f"---",
                f"",
                f"{entry.content}",
            ]
            topic_file.write_text("\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to persist memory to file: {e}")

    def _compact(self):
        stale = self.manifest.stale_entries(self.STALE_THRESHOLD_DAYS)
        low_access = sorted(
            [e for e in self.manifest.entries if e not in stale],
            key=lambda e: (e.access_count, e.confidence)
        )
        to_remove = stale[:len(stale) // 2] + low_access[:len(low_access) // 4]
        for entry in to_remove:
            self.manifest.remove(entry.id)
            topic_file = self._memory_dir / f"{entry.memory_type.value}_{entry.title.lower().replace(' ', '_')[:50]}.md"
            if topic_file.exists():
                topic_file.unlink()
        logger.info(f"Memory compaction: removed {len(to_remove)} entries")

    def build_memory_index(self) -> str:
        lines = [
            "# Mining AI Memory Index",
            "",
            f"Total memories: {len(self.manifest.entries)}",
            f"Last updated: {datetime.utcnow().isoformat()}",
            "",
        ]
        for mtype in MemoryType:
            entries = self.manifest.by_type(mtype)
            if entries:
                lines.append(f"## {mtype.value.title()} ({len(entries)} entries)")
                for entry in entries:
                    age = entry.freshness_text()
                    stale = " [STALE]" if entry.is_stale(self.STALE_THRESHOLD_DAYS) else ""
                    lines.append(f"- {entry.title} ({age}{stale})")
                lines.append("")

        content = "\n".join(lines)
        if len(content) > self.MAX_MEMORY_BYTES:
            content = content[:self.MAX_MEMORY_BYTES]
        lines = content.split("\n")
        if len(lines) > self.MAX_LINES:
            content = "\n".join(lines[:self.MAX_LINES])

        self._index_path.write_text(content)
        return content

    def get_memory_stats(self) -> Dict[str, Any]:
        stats = {
            "total_entries": len(self.manifest.entries),
            "by_type": {},
            "stale_count": len(self.manifest.stale_entries(self.STALE_THRESHOLD_DAYS)),
            "total_size_bytes": 0,
        }
        for mtype in MemoryType:
            entries = self.manifest.by_type(mtype)
            stats["by_type"][mtype.value] = len(entries)
        for f in self._memory_dir.glob("*.md"):
            if f.name != "MEMORY.md":
                stats["total_size_bytes"] += f.stat().st_size
        return stats

    def auto_store_from_interaction(self, query: str, response: str, session_id: str = ""):
        feedback_keywords = ["correct", "wrong", "actually", "not like that", "better way", "preferred", "always do", "never do"]
        project_keywords = ["incident", "deadline", "urgent", "in progress", "completed", "blocked", "milestone"]
        equipment_keywords = ["truck", "crusher", "mill", "conveyor", "pump", "excavator", "drill", "haul"]

        query_lower = query.lower()
        if any(kw in query_lower for kw in feedback_keywords):
            self.store(
                MemoryType.FEEDBACK,
                title=f"Feedback: {query[:80]}",
                content=f"User said: {query}\nResponse context: {response[:300]}",
                tags=["feedback", "correction"],
                source="conversation",
                confidence=0.9
            )
        elif any(kw in query_lower for kw in project_keywords):
            self.store(
                MemoryType.PROJECT,
                title=f"Project update: {query[:80]}",
                content=f"{query}\n{response[:300]}",
                tags=["project", "status"],
                source="conversation",
                confidence=0.85
            )
        elif any(kw in query_lower for kw in equipment_keywords):
            self.store(
                MemoryType.EQUIPMENT,
                title=f"Equipment note: {query[:80]}",
                content=f"{query}\n{response[:300]}",
                tags=["equipment", "maintenance"],
                source="conversation",
                confidence=0.8
            )

    def retrieve_user_profile(self, phone: str) -> Optional[Dict[str, Any]]:
        profile_entries = self.recall(phone, limit=3, memory_type=MemoryType.OPERATOR)
        if not profile_entries:
            return None
        profile = {"phone": phone, "preferences": {}, "history": []}
        for entry in profile_entries:
            profile["history"].append({"title": entry.title, "content": entry.content[:200]})
            for tag in entry.tags:
                profile["preferences"][tag] = entry.content[:100]
        return profile

    def search_archived_reports(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        entries = self.recall(query, limit=limit, memory_type=MemoryType.PROJECT)
        return [
            {"title": e.title, "summary": e.content[:200], "created": e.created_at.isoformat()}
            for e in entries
        ]
