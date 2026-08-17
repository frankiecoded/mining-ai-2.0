import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_os.session_memory")


class SessionSection(BaseModel):
    title: str
    content: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    max_chars: int = 2000


class SessionMemory(BaseModel):
    title: str = "Current Mining Operation"
    sections: Dict[str, SessionSection] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0
    token_estimate: int = 0


class SessionMemoryManager:
    """
    Live mine state document system. Adapted from Claude Code's sessionMemory.

    Maintains a structured markdown document that tracks:
    - Current mining operation state
    - Active drilling targets
    - Equipment status
    - Safety concerns
    - Geological findings
    - Active workflows

    The document is injected into the system prompt for context continuity.
    """

    MEMORY_DIR = "data/session_memory"
    MAX_TOTAL_TOKENS = 12000
    MIN_MESSAGES_TO_INIT = 3
    MESSAGES_BETWEEN_UPDATES = 5
    SECTIONS = [
        "current_state",
        "active_targets",
        "equipment_status",
        "safety_concerns",
        "geological_findings",
        "active_workflows",
        "recent_decisions",
        "pending_actions",
    ]

    def __init__(self):
        self._dir = Path(self.MEMORY_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, SessionMemory] = {}

    def _session_path(self, session_id: str) -> Path:
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.md"

    def get_or_create(self, session_id: str) -> SessionMemory:
        if session_id in self._sessions:
            return self._sessions[session_id]
        path = self._session_path(session_id)
        if path.exists():
            try:
                content = path.read_text()
                memory = self._parse_markdown(session_id, content)
                self._sessions[session_id] = memory
                return memory
            except Exception as e:
                logger.warning(f"Failed to load session memory: {e}")
        memory = SessionMemory(title=f"Mining Operation — {session_id}")
        for section_name in self.SECTIONS:
            memory.sections[section_name] = SessionSection(
                title=section_name.replace("_", " ").title(),
                content=""
            )
        self._sessions[session_id] = memory
        return memory

    def update_section(self, session_id: str, section: str, content: str, append: bool = False):
        memory = self.get_or_create(session_id)
        if section not in memory.sections:
            memory.sections[section] = SessionSection(
                title=section.replace("_", " ").title(),
                content=content
            )
        else:
            if append:
                existing = memory.sections[section].content
                memory.sections[section].content = f"{existing}\n{content}"[-2000:]
            else:
                memory.sections[section].content = content[:2000]
        memory.sections[section].updated_at = datetime.utcnow()
        memory.updated_at = datetime.utcnow()
        self._persist(session_id, memory)

    def record_interaction(self, session_id: str, query: str, response: str, tool_calls: List[str] = None):
        memory = self.get_or_create(session_id)
        memory.message_count += 1

        self._extract_state_from_interaction(memory, query, response, tool_calls or [])
        self._persist(session_id, memory)

    def _extract_state_from_interaction(self, memory: SessionMemory, query: str, response: str, tool_calls: List[str]):
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["status", "current", "state", "now", "today"]):
            state_excerpt = f"[{datetime.utcnow().strftime('%H:%M')}] Query: {query[:100]}"
            memory.sections["current_state"].content = (
                memory.sections["current_state"].content + "\n" + state_excerpt
            )[-2000:]

        if any(kw in query_lower for kw in ["drill", "borehole", "target", "prospect"]):
            memory.sections["active_targets"].content = (
                memory.sections["active_targets"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

        if any(kw in query_lower for kw in ["truck", "mill", "crusher", "conveyor", "equipment"]):
            memory.sections["equipment_status"].content = (
                memory.sections["equipment_status"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

        if any(kw in query_lower for kw in ["safety", "incident", "hazard", "emergency", "ppe"]):
            memory.sections["safety_concerns"].content = (
                memory.sections["safety_concerns"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

        if any(kw in query_lower for kw in ["grade", "assay", "geology", "ore", "mineral"]):
            memory.sections["geological_findings"].content = (
                memory.sections["geological_findings"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

        if any(kw in query_lower for kw in ["workflow", "process", "procedure", "sop", "step"]):
            memory.sections["active_workflows"].content = (
                memory.sections["active_workflows"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

        if any(kw in query_lower for kw in ["decided", "confirmed", "approved", "go with", "use"]):
            memory.sections["recent_decisions"].content = (
                memory.sections["recent_decisions"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

        if any(kw in query_lower for kw in ["todo", "next", "need to", "must", "action"]):
            memory.sections["pending_actions"].content = (
                memory.sections["pending_actions"].content +
                f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {query[:150]}"
            )[-2000:]

    def build_prompt_section(self, session_id: str) -> str:
        memory = self.get_or_create(session_id)
        if memory.message_count < self.MIN_MESSAGES_TO_INIT:
            return ""
        sections = []
        for key, section in memory.sections.items():
            if section.content.strip():
                sections.append(f"### {section.title}\n{section.content.strip()}")
        if not sections:
            return ""
        header = f"# {memory.title}\nLast updated: {memory.updated_at.strftime('%Y-%m-%d %H:%M')}\nMessages in session: {memory.message_count}"
        content = header + "\n\n" + "\n\n".join(sections)
        token_est = len(content) // 4
        if token_est > self.MAX_TOTAL_TOKENS:
            content = content[:self.MAX_TOTAL_TOKENS * 4]
        return f"## Session Memory (Live Mine State)\n\n{content}"

    def _persist(self, session_id: str, memory: SessionMemory):
        try:
            path = self._session_path(session_id)
            lines = [
                f"# {memory.title}",
                f"Created: {memory.created_at.isoformat()}",
                f"Updated: {memory.updated_at.isoformat()}",
                f"Messages: {memory.message_count}",
                "",
            ]
            for key, section in memory.sections.items():
                if section.content.strip():
                    lines.append(f"## {section.title}")
                    lines.append(section.content.strip())
                    lines.append("")
            path.write_text("\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to persist session memory: {e}")

    def _parse_markdown(self, session_id: str, content: str) -> SessionMemory:
        memory = SessionMemory(title=f"Mining Operation — {session_id}")
        current_section = None
        current_content = []
        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section and current_content:
                    memory.sections[current_section] = SessionSection(
                        title=current_section.replace("_", " ").title(),
                        content="\n".join(current_content).strip()
                    )
                section_name = line[3:].strip().lower().replace(" ", "_")
                current_section = section_name
                current_content = []
            elif current_section:
                current_content.append(line)
        if current_section and current_content:
            memory.sections[current_section] = SessionSection(
                title=current_section.replace("_", " ").title(),
                content="\n".join(current_content).strip()
            )
        return memory

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        memory = self.get_or_create(session_id)
        return {
            "session_id": session_id,
            "title": memory.title,
            "sections": {k: len(v.content) for k, v in memory.sections.items()},
            "message_count": memory.message_count,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        for path in self._dir.glob("*.md"):
            session_id = path.stem
            sessions.append(self.get_session_summary(session_id))
        return sorted(sessions, key=lambda s: s.get("updated_at", ""), reverse=True)
