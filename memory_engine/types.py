from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    OPERATOR = "operator"       # Operator roles, goals, preferences
    FEEDBACK = "feedback"       # Corrected approaches, confirmed workflows
    PROJECT = "project"         # Active incidents, deadlines, ongoing work
    REFERENCE = "reference"     # External systems, dashboards, contacts
    SHIFT = "shift"             # Shift-specific context (day/night handover)
    EQUIPMENT = "equipment"     # Equipment-specific learnings and history


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: f"mem_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{id(object()) % 10000:04d}")
    memory_type: MemoryType
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "conversation"  # conversation, tool, manual, system
    confidence: float = 1.0       # 0.0 to 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # For time-sensitive data
    related_memories: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_stale(self, max_age_days: int = 30) -> bool:
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        age = (datetime.utcnow() - self.updated_at).days
        return age > max_age_days

    def age_days(self) -> int:
        return (datetime.utcnow() - self.updated_at).days

    def freshness_text(self) -> str:
        days = self.age_days()
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            return f"{days // 7} weeks ago"
        elif days < 365:
            return f"{days // 30} months ago"
        else:
            return f"{days // 365} years ago"


class MemoryManifest(BaseModel):
    entries: List[MemoryEntry] = Field(default_factory=list)
    total_count: int = 0
    last_compaction: Optional[datetime] = None

    def add(self, entry: MemoryEntry):
        self.entries.append(entry)
        self.total_count = len(self.entries)

    def remove(self, entry_id: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.id != entry_id]
        self.total_count = len(self.entries)
        return len(self.entries) < before

    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> List[MemoryEntry]:
        query_lower = query.lower()
        results = []
        for entry in self.entries:
            if memory_type and entry.memory_type != memory_type:
                continue
            score = 0.0
            if query_lower in entry.title.lower():
                score += 3.0
            if query_lower in entry.content.lower():
                score += 1.0
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 2.0
            if score > 0:
                results.append((score, entry))
        results.sort(key=lambda x: (-x[0], -x[1].confidence))
        return [entry for _, entry in results[:limit]]

    def by_type(self, memory_type: MemoryType) -> List[MemoryEntry]:
        return [e for e in self.entries if e.memory_type == memory_type]

    def recent(self, limit: int = 20) -> List[MemoryEntry]:
        sorted_entries = sorted(self.entries, key=lambda e: e.updated_at, reverse=True)
        return sorted_entries[:limit]

    def stale_entries(self, max_age_days: int = 30) -> List[MemoryEntry]:
        return [e for e in self.entries if e.is_stale(max_age_days)]
