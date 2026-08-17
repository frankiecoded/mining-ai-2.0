import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_os.cost_tracker")


class ModelUsage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0


class SessionCost(BaseModel):
    session_id: str
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    by_model: Dict[str, ModelUsage] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    interactions: int = 0


class ShiftCost(BaseModel):
    shift_id: str
    site: str = "default"
    total_cost: float = 0.0
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_interactions: int = 0
    by_department: Dict[str, float] = Field(default_factory=dict)
    by_session: Dict[str, float] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    budget_limit: float = 0.0


class CostTracker:
    """
    Cost tracking system adapted from Claude Code's cost-tracker.ts.
    Tracks API costs per session, per shift, per department.
    Supports budget limits and alerts.

    Pricing (per 1M tokens):
    - gpt-oss-120b (HF Router): ~$0.15 input, $0.60 output (estimated)
    - ollama local: $0.00
    """

    MODEL_PRICING = {
        "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
        "qwen3-coder:30b": {"input": 0.0, "output": 0.0},
        "default": {"input": 0.15, "output": 0.60},
    }

    DATA_DIR = "data/costs"
    BUDGET_ALERT_THRESHOLD = 0.8  # Alert at 80% of budget

    def __init__(self):
        self._dir = Path(self.DATA_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, SessionCost] = {}
        self._shifts: Dict[str, ShiftCost] = {}
        self._daily_costs: Dict[str, float] = {}

    def _get_pricing(self, model: str) -> Dict[str, float]:
        for key, pricing in self.MODEL_PRICING.items():
            if key in model:
                return pricing
        return self.MODEL_PRICING["default"]

    def record_interaction(self, session_id: str, model: str, input_tokens: int,
                          output_tokens: int, tool_calls: int = 0,
                          department: str = "general", site: str = "default") -> Dict[str, Any]:
        pricing = self._get_pricing(model)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        if session_id not in self._sessions:
            self._sessions[session_id] = SessionCost(session_id=session_id)
        session = self._sessions[session_id]
        session.total_cost += cost
        session.total_input_tokens += input_tokens
        session.total_output_tokens += output_tokens
        session.total_tool_calls += tool_calls
        session.interactions += 1
        session.last_activity = datetime.utcnow()

        if model not in session.by_model:
            session.by_model[model] = ModelUsage(model=model)
        session.by_model[model].input_tokens += input_tokens
        session.by_model[model].output_tokens += output_tokens
        session.by_model[model].tool_calls += tool_calls
        session.by_model[model].cost_usd += cost

        shift_id = self._current_shift_id(site)
        if shift_id not in self._shifts:
            self._shifts[shift_id] = ShiftCost(shift_id=shift_id, site=site)
        shift = self._shifts[shift_id]
        shift.total_cost += cost
        shift.total_tokens += input_tokens + output_tokens
        shift.total_tool_calls += tool_calls
        shift.total_interactions += 1
        shift.by_session[session_id] = shift.by_session.get(session_id, 0) + cost
        shift.by_department[department] = shift.by_department.get(department, 0) + cost

        today = datetime.utcnow().strftime("%Y-%m-%d")
        self._daily_costs[today] = self._daily_costs.get(today, 0) + cost

        alerts = []
        if shift.budget_limit > 0:
            usage_pct = shift.total_cost / shift.budget_limit
            if usage_pct >= self.BUDGET_ALERT_THRESHOLD:
                alerts.append(f"SHIFT BUDGET ALERT: {usage_pct*100:.1f}% used (${shift.total_cost:.2f} / ${shift.budget_limit:.2f})")

        return {
            "cost_usd": round(cost, 6),
            "session_total": round(session.total_cost, 4),
            "shift_total": round(shift.total_cost, 4),
            "daily_total": round(self._daily_costs.get(today, 0), 4),
            "alerts": alerts,
        }

    def get_session_cost(self, session_id: str) -> Optional[SessionCost]:
        return self._sessions.get(session_id)

    def get_shift_cost(self, shift_id: str) -> Optional[ShiftCost]:
        return self._shifts.get(shift_id)

    def get_daily_cost(self, date: str = None) -> float:
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        return self._daily_costs.get(date, 0)

    def set_shift_budget(self, shift_id: str, budget: float):
        if shift_id in self._shifts:
            self._shifts[shift_id].budget_limit = budget

    def get_cost_summary(self) -> Dict[str, Any]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        active_sessions = [s for s in self._sessions.values()
                          if (datetime.utcnow() - s.last_activity).seconds < 3600]
        return {
            "daily_cost_usd": round(self.get_daily_cost(), 4),
            "active_sessions": len(active_sessions),
            "total_sessions": len(self._sessions),
            "total_shifts": len(self._shifts),
            "today": today,
            "active_session_costs": [
                {"session_id": s.session_id, "cost": round(s.total_cost, 4), "interactions": s.interactions}
                for s in active_sessions
            ],
        }

    def format_cost_report(self) -> str:
        summary = self.get_cost_summary()
        lines = [
            f"## Cost Report — {summary['today']}",
            f"**Daily Total:** ${summary['daily_cost_usd']:.4f}",
            f"**Active Sessions:** {summary['active_sessions']}",
            f"**Total Sessions:** {summary['total_sessions']}",
            "",
        ]
        if summary["active_session_costs"]:
            lines.append("### Active Session Costs")
            for s in summary["active_session_costs"]:
                lines.append(f"- {s['session_id']}: ${s['cost']:.4f} ({s['interactions']} interactions)")
        return "\n".join(lines)

    def _current_shift_id(self, site: str) -> str:
        now = datetime.utcnow()
        hour = now.hour
        if 6 <= hour < 14:
            shift = "day"
        elif 14 <= hour < 22:
            shift = "afternoon"
        else:
            shift = "night"
        return f"{site}_{now.strftime('%Y%m%d')}_{shift}"

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_remove = [sid for sid, s in self._sessions.items() if s.last_activity < cutoff]
        for sid in to_remove:
            del self._sessions[sid]
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old session cost records")
