import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

logger = logging.getLogger("ai_os.compaction")


class ContextCompactor:
    """
    Context compaction system adapted from Claude Code's compact service.
    Manages conversation context by compressing old messages while
    preserving critical information.

    Tiered approach:
    1. MicroCompact - trim large tool results, keep summaries
    2. Full Compact - summarize entire conversation into decisions + context
    3. Session Memory - persist critical state to markdown

    This is critical for mining AI because conversations involve
    massive sensor data, geological logs, and equipment readings.
    """

    AUTO_COMPACT_FRACTION = 0.75
    MAX_TOOL_RESULT_CHARS = 2000
    MAX_MESSAGES_BEFORE_COMPACT = 40
    RECENT_MESSAGES_TO_KEEP = 10

    def __init__(self, session_memory=None):
        self.session_memory = session_memory
        self._compaction_counts: Dict[str, int] = {}

    def should_compact(self, messages: List[BaseMessage], context_window: int = 128000) -> bool:
        total_chars = sum(len(str(m.content)) for m in messages)
        estimated_tokens = total_chars // 4
        if estimated_tokens > context_window * self.AUTO_COMPACT_FRACTION:
            return True
        if len(messages) > self.MAX_MESSAGES_BEFORE_COMPACT:
            return True
        return False

    def micro_compact(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        if len(messages) <= 5:
            return messages
        compacted = []
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        compacted.extend(system_msgs)
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]
        recent_count = min(self.RECENT_MESSAGES_TO_KEEP, len(non_system))
        recent = non_system[-recent_count:]
        old = non_system[:-recent_count]
        for msg in old:
            if isinstance(msg, ToolMessage) and len(str(msg.content)) > self.MAX_TOOL_RESULT_CHARS:
                content = str(msg.content)
                summary = content[:500] + f"\n\n[... truncated, {len(content)} chars total]"
                compacted.append(ToolMessage(content=summary, tool_call_id=msg.tool_call_id))
            else:
                compacted.append(msg)
        compacted.extend(recent)
        return compacted

    def full_compact(self, messages: List[BaseMessage], session_id: str = "") -> List[BaseMessage]:
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]

        if not non_system:
            return messages

        human_msgs = [m for m in non_system if isinstance(m, HumanMessage)]
        ai_msgs = [m for m in non_system if isinstance(m, AIMessage)]
        tool_msgs = [m for m in non_system if isinstance(m, ToolMessage)]

        decisions = []
        key_findings = []
        for msg in ai_msgs:
            content = str(msg.content) if msg.content else ""
            if content and len(content) > 50:
                sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 20]
                for s in sentences[:3]:
                    if any(kw in s.lower() for kw in ["recommend", "conclude", "found", "result", "analysis"]):
                        key_findings.append(s)
        for msg in human_msgs:
            content = str(msg.content) if msg.content else ""
            if content and not content.startswith("["):
                short = content[:200]
                if len(short) < len(content):
                    short += "..."
                decisions.append(f"User asked: {short}")

        tool_count = len(tool_msgs)
        tools_used = set()
        for msg in ai_msgs:
            calls = getattr(msg, "tool_calls", []) or []
            for tc in calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if name:
                    tools_used.add(name)

        summary_parts = [
            f"## Conversation Summary ({len(non_system)} messages compacted)",
            f"**Tools used:** {', '.join(sorted(tools_used)) if tools_used else 'none'}",
            f"**Tool calls made:** {tool_count}",
            "",
        ]
        if decisions:
            summary_parts.append("### Key Questions/Requests")
            for d in decisions[-10:]:
                summary_parts.append(f"- {d}")
            summary_parts.append("")
        if key_findings:
            summary_parts.append("### Key Findings")
            for f in key_findings[-10:]:
                summary_parts.append(f"- {f}")
            summary_parts.append("")

        summary_text = "\n".join(summary_parts)

        recent_count = min(self.RECENT_MESSAGES_TO_KEEP, len(non_system))
        recent = non_system[-recent_count:]

        compacted = system_msgs + [HumanMessage(content=summary_text)] + recent

        self._compaction_counts[session_id] = self._compaction_counts.get(session_id, 0) + 1
        logger.info(f"Compacted {len(non_system)} messages to {len(compacted)} (session: {session_id})")

        return compacted

    def estimate_tokens(self, messages: List[BaseMessage]) -> int:
        total_chars = sum(len(str(m.content)) for m in messages)
        return total_chars // 4

    def get_compaction_stats(self, session_id: str = "") -> Dict[str, Any]:
        return {
            "compactions_performed": self._compaction_counts.get(session_id, 0),
            "auto_compact_threshold": f"{self.AUTO_COMPACT_FRACTION * 100:.0f}%",
            "max_tool_result_chars": self.MAX_TOOL_RESULT_CHARS,
        }
