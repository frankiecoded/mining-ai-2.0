import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("ai_os.prompt_suggestion")


class PromptSuggestionEngine:
    """
    Proactive prompt suggestion system adapted from Claude Code's
    promptSuggestion service. Analyzes conversation context and
    suggests relevant next actions for mining operations.

    Features:
    - Context-aware suggestions based on conversation history
    - Proactive recommendations based on data patterns
    - Skill-matched suggestions
    - Follow-up question suggestions
    """

    SUGGESTION_PATTERNS = {
        "gold_price": {
            "triggers": ["gold", "price", "market", "revenue", "sell"],
            "suggestions": [
                "What is the current gold-to-silver ratio and what does it mean for our revenue mix?",
                "Show me a 30-day gold price trend analysis",
                "How does our AISC compare to current gold price?",
            ]
        },
        "equipment": {
            "triggers": ["truck", "mill", "crusher", "conveyor", "equipment", "maintenance"],
            "suggestions": [
                "Run a full diagnostic on all haul trucks",
                "What is our equipment utilization rate this month?",
                "Show me maintenance schedules for the next 2 weeks",
            ]
        },
        "geology": {
            "triggers": ["grade", "drill", "assay", "ore", "geology", "exploration"],
            "suggestions": [
                "Compare this quarter's grades to last quarter",
                "Which drill holes show the highest gold grades?",
                "Show me the grade control reconciliation report",
            ]
        },
        "safety": {
            "triggers": ["safety", "incident", "hazard", "ppe", "compliance"],
            "suggestions": [
                "Run a safety compliance check on all active shifts",
                "What are the top 3 safety risks right now?",
                "Generate a safety audit report for this week",
            ]
        },
        "financial": {
            "triggers": ["budget", "cost", "payroll", "procurement", "finance"],
            "suggestions": [
                "Show me a department-by-department budget variance",
                "What is our cost per ounce produced this quarter?",
                "Compare actual spend vs budget for exploration",
            ]
        },
        "blast": {
            "triggers": ["blast", "explosive", "detonation", "fragmentation"],
            "suggestions": [
                "Design a blast pattern for the next bench",
                "Review the last blast's fragmentation results",
                "What is our powder factor trend over the last 10 blasts?",
            ]
        },
    }

    def __init__(self, skill_manager=None, memory_engine=None):
        self.skill_manager = skill_manager
        self.memory_engine = memory_engine

    def suggest(self, query: str, response: str = "", conversation_length: int = 0) -> List[Dict[str, Any]]:
        suggestions = []
        query_lower = query.lower()

        for pattern_name, pattern in self.SUGGESTION_PATTERNS.items():
            for trigger in pattern["triggers"]:
                if trigger in query_lower:
                    for suggestion_text in pattern["suggestions"]:
                        suggestions.append({
                            "text": suggestion_text,
                            "source": "pattern",
                            "pattern": pattern_name,
                            "priority": "high",
                        })
                    break

        if self.skill_manager:
            matching_skills = self.skill_manager.search_skills(query)
            for skill in matching_skills[:2]:
                suggestions.append({
                    "text": f"Run {skill.name} analysis",
                    "source": "skill",
                    "skill_id": skill.id,
                    "priority": "medium",
                })

        if conversation_length > 5 and response:
            response_lower = response.lower()
            if any(kw in response_lower for kw in ["trend", "increasing", "decreasing", "changing"]):
                suggestions.append({
                    "text": "Show me a detailed trend analysis with forecasts",
                    "source": "context",
                    "priority": "medium",
                })
            if any(kw in response_lower for kw in ["alert", "warning", "critical", "exceeds"]):
                suggestions.append({
                    "text": "What are the corrective actions for this issue?",
                    "source": "context",
                    "priority": "high",
                })

        seen = set()
        unique = []
        for s in suggestions:
            if s["text"] not in seen:
                seen.add(s["text"])
                unique.append(s)
        unique.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3))
        return unique[:5]

    def suggest_followup(self, last_topic: str, data_summary: str = "") -> List[str]:
        suggestions = []
        topic_lower = last_topic.lower()
        if any(kw in topic_lower for kw in ["production", "tonnage", "milled"]):
            suggestions.extend([
                "How does this compare to last month's production?",
                "What is the recovery rate trend?",
                "Show me production by mine/section",
            ])
        elif any(kw in topic_lower for kw in ["grade", "assay", "ore"]):
            suggestions.extend([
                "What is the grade control reconciliation?",
                "Are there any grade anomalies to investigate?",
                "Show me the grade distribution histogram",
            ])
        elif any(kw in topic_lower for kw in ["cost", "budget", "spend"]):
            suggestions.extend([
                "Which departments are over budget?",
                "What is our cost per ounce?",
                "Show me a cost breakdown by category",
            ])
        elif any(kw in topic_lower for kw in ["safety", "incident"]):
            suggestions.extend([
                "What are the near-miss trends?",
                "Show me the safety training compliance rate",
                "Are there any overdue corrective actions?",
            ])
        else:
            suggestions.extend([
                "What should I focus on next?",
                "Show me a summary of today's operations",
                "Are there any alerts or anomalies I should know about?",
            ])
        return suggestions[:3]
