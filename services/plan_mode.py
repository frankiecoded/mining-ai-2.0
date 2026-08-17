import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_os.plan_mode")


class PlanPhase(str, Enum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    DESIGN = "design"
    REVIEW = "review"
    APPROVAL = "approval"
    EXECUTION = "execution"
    VERIFICATION = "verification"


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    phase: PlanPhase
    title: str
    description: str
    status: str = "pending"  # pending, in_progress, completed, blocked, skipped
    depends_on: List[str] = Field(default_factory=list)
    tools_needed: List[str] = Field(default_factory=list)
    estimated_duration: str = ""
    risks: List[str] = Field(default_factory=list)
    output: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PlanMode:
    """
    Plan mode system adapted from Claude Code's EnterPlanModeTool.
    Enables structured planning for complex mining operations
    with approval gates before execution.

    Used for:
    - Blast design planning
    - Ventilation planning
    - Drill program planning
    - Capital expenditure planning
    - Emergency response planning
    - Environmental compliance planning
    """

    def __init__(self):
        self._active_plans: Dict[str, Dict[str, Any]] = {}
        self._plan_history: List[Dict[str, Any]] = []

    def create_plan(self, session_id: str, title: str, description: str,
                    plan_type: str = "general") -> Dict[str, Any]:
        plan = {
            "id": f"plan_{uuid.uuid4().hex[:10]}",
            "session_id": session_id,
            "title": title,
            "description": description,
            "plan_type": plan_type,
            "status": "draft",
            "mode": "plan",  # plan mode = read-only, no execution
            "steps": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "approval_required": True,
            "approved": False,
            "approved_by": None,
            "approved_at": None,
        }
        self._active_plans[plan["id"]] = plan
        logger.info(f"Created plan: {plan['id']} - {title}")
        return plan

    def add_step(self, plan_id: str, phase: PlanPhase, title: str, description: str,
                 depends_on: Optional[List[str]] = None, tools_needed: Optional[List[str]] = None,
                 risks: Optional[List[str]] = None, estimated_duration: str = "") -> Optional[PlanStep]:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None
        step = PlanStep(
            phase=phase,
            title=title,
            description=description,
            depends_on=depends_on or [],
            tools_needed=tools_needed or [],
            risks=risks or [],
            estimated_duration=estimated_duration,
        )
        plan["steps"].append(step.model_dump())
        plan["updated_at"] = datetime.utcnow().isoformat()
        return step

    def approve_plan(self, plan_id: str, approved_by: str = "operator") -> bool:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return False
        plan["approved"] = True
        plan["approved_by"] = approved_by
        plan["approved_at"] = datetime.utcnow().isoformat()
        plan["status"] = "approved"
        logger.info(f"Plan approved: {plan_id} by {approved_by}")
        return True

    def transition_to_execute(self, plan_id: str) -> bool:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return False
        if not plan.get("approved"):
            logger.warning(f"Plan {plan_id} not yet approved")
            return False
        plan["mode"] = "execute"
        plan["status"] = "executing"
        logger.info(f"Plan transitioned to execution: {plan_id}")
        return True

    def complete_step(self, plan_id: str, step_id: str, output: str = "") -> bool:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return False
        for step in plan["steps"]:
            if step["id"] == step_id:
                step["status"] = "completed"
                step["output"] = output
                step["completed_at"] = datetime.utcnow().isoformat()
                self._check_dependents(plan, step_id)
                plan["updated_at"] = datetime.utcnow().isoformat()
                return True
        return False

    def _check_dependents(self, plan: Dict, completed_step_id: str):
        for step in plan["steps"]:
            if step["status"] == "blocked" and completed_step_id in step.get("depends_on", []):
                all_met = all(
                    any(s["id"] == dep and s["status"] == "completed" for s in plan["steps"])
                    for dep in step["depends_on"]
                )
                if all_met:
                    step["status"] = "pending"

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        return self._active_plans.get(plan_id)

    def get_active_plan_for_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        for plan in self._active_plans.values():
            if plan["session_id"] == session_id and plan["status"] in ("draft", "approved", "executing"):
                return plan
        return None

    def list_plans(self, session_id: str = None, status: str = None) -> List[Dict[str, Any]]:
        plans = list(self._active_plans.values())
        if session_id:
            plans = [p for p in plans if p["session_id"] == session_id]
        if status:
            plans = [p for p in plans if p["status"] == status]
        return sorted(plans, key=lambda p: p["created_at"], reverse=True)

    def render_plan(self, plan_id: str) -> str:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return "Plan not found"
        lines = [
            f"# {plan['title']}",
            f"**Type:** {plan['plan_type']} | **Status:** {plan['status']} | **Mode:** {plan['mode']}",
            f"**Created:** {plan['created_at'][:19]}",
            "",
            plan["description"],
            "",
        ]
        if plan.get("approved"):
            lines.append(f"**Approved by:** {plan['approved_by']} at {plan['approved_at'][:19]}")
            lines.append("")
        phases = {}
        for step in plan["steps"]:
            phase = step["phase"]
            if phase not in phases:
                phases[phase] = []
            phases[phase].append(step)
        for phase, steps in phases.items():
            lines.append(f"## {phase.title()}")
            for step in steps:
                status_icon = {"pending": "⬜", "in_progress": "🔵", "completed": "✅", "blocked": "🔴", "skipped": "⏭️"}.get(step["status"], "❓")
                lines.append(f"- {status_icon} **{step['title']}**")
                lines.append(f"  {step['description']}")
                if step.get("risks"):
                    lines.append(f"  ⚠️ Risks: {', '.join(step['risks'])}")
                if step.get("output"):
                    lines.append(f"  📋 Output: {step['output'][:200]}")
            lines.append("")
        if not plan.get("approved") and plan["status"] == "draft":
            lines.append("---")
            lines.append("*Plan is in DRAFT mode. Awaiting approval before execution.*")
        return "\n".join(lines)

    def create_blast_plan(self, session_id: str, bench_info: Dict[str, Any]) -> Dict[str, Any]:
        plan = self.create_plan(
            session_id, "Blast Pattern Design", 
            f"Design blast pattern for bench at {bench_info.get('location', 'unknown')}",
            plan_type="blast_design"
        )
        self.add_step(plan["id"], PlanPhase.RESEARCH, "Gather Geological Data",
                     "Review drill hole data, rock mass properties, and geotechnical assessment",
                     tools_needed=["query_mining_database"],
                     risks=["Incomplete geological data", "Outdated assay results"])
        self.add_step(plan["id"], PlanPhase.ANALYSIS, "Calculate Parameters",
                     "Determine powder factor, hole spacing, burden, and charge weights",
                     depends_on=[plan["steps"][0]["id"] if plan["steps"] else ""])
        self.add_step(plan["id"], PlanPhase.DESIGN, "Design Blast Pattern",
                     "Create hole layout, charge design, and initiation sequence",
                     depends_on=[plan["steps"][1]["id"] if len(plan["steps"]) > 1 else ""])
        self.add_step(plan["id"], PlanPhase.REVIEW, "Safety Review",
                     "Review vibration limits, flyrock distance, and exclusion zones",
                     depends_on=[plan["steps"][2]["id"] if len(plan["steps"]) > 2 else ""])
        self.add_step(plan["id"], PlanPhase.APPROVAL, "Operator Approval",
                     "Present plan for operator review and approval",
                     depends_on=[plan["steps"][3]["id"] if len(plan["steps"]) > 3 else ""])
        self.add_step(plan["id"], PlanPhase.EXECUTION, "Execute Blast",
                     "Drill, charge, stem, and initiate blast per approved plan",
                     depends_on=[plan["steps"][4]["id"] if len(plan["steps"]) > 4 else ""])
        return plan
