import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_os.skills")


class SkillArg(BaseModel):
    name: str
    description: str
    required: bool = False
    default_value: str = ""


class MiningSkill(BaseModel):
    id: str
    name: str
    description: str
    domain: str = "general"
    effort: str = "medium"  # low, medium, high
    prompt_template: str = ""
    allowed_tools: List[str] = Field(default_factory=list)
    args: List[SkillArg] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True


MINING_SKILLS: Dict[str, MiningSkill] = {
    "blast_design": MiningSkill(
        id="blast_design",
        name="Blast Pattern Design",
        description="Design optimal blast patterns based on geological data, rock mass properties, and fragmentation targets.",
        domain="drilling_blasting",
        effort="high",
        prompt_template="""You are designing a blast pattern for a mining operation.

## Inputs Required
- Rock type and hardness
- Bench height and hole diameter
- Desired fragmentation size
- Geotechnical constraints (vibration limits, flyrock distance)
- Previous blast results

## Analysis Steps
1. Review geological data and rock mass rating
2. Calculate powder factor based on rock hardness
3. Design hole spacing and burden based on hole diameter
4. Calculate charge weights per hole
5. Design initiation sequence for optimal fragmentation
6. Estimate fragmentation size distribution
7. Calculate vibration predictions (PPV)
8. Provide safety exclusion zone distances

## Output
- Blast pattern diagram (coordinates)
- Drill hole schedule
- Charge design per hole
- Initiation sequence
- Safety zone calculations
- Estimated costs
- Risk assessment""",
        allowed_tools=["query_mining_database", "search_knowledge_base", "generate_report"],
        args=[
            SkillArg(name="rock_type", description="Type of rock to blast", required=True),
            SkillArg(name="bench_height", description="Bench height in meters", required=True),
            SkillArg(name="hole_diameter", description="Drill hole diameter in mm", required=True),
        ],
        tags=["blasting", "drilling", "explosives", "fragmentation"]
    ),
    "grade_control": MiningSkill(
        id="grade_control",
        name="Grade Control Analysis",
        description="Analyze grade control data to optimize ore/waste classification and minimize dilution.",
        domain="geological",
        effort="medium",
        prompt_template="""You are performing grade control analysis for a mining operation.

## Analysis Steps
1. Review drill hole assay data
2. Apply grade cutoff thresholds
3. Classify ore vs waste blocks
4. Calculate dilution and loss estimates
5. Identify grade anomalies
6. Recommend selective mining units
7. Update block model if needed

## Grade Classifications
- High grade: >5 g/t Au
- Medium grade: 1-5 g/t Au
- Low grade: 0.3-1 g/t Au
- Sub-economic: <0.3 g/t Au

## Output
- Ore/waste classification map
- Tonnage and grade by category
- Dilution/loss estimates
- Recommendations for selective mining""",
        allowed_tools=["query_mining_database", "search_knowledge_base", "generate_report"],
        args=[
            SkillArg(name="data_source", description="Source of grade control data (drill holes, channel samples)", required=True),
        ],
        tags=["grade", "assay", "ore_control", "classification"]
    ),
    "ventilation_assessment": MiningSkill(
        id="ventilation_assessment",
        name="Ventilation Assessment",
        description="Assess underground ventilation requirements and identify airflow deficiencies.",
        domain="underground",
        effort="high",
        prompt_template="""You are assessing ventilation requirements for an underground mining operation.

## Analysis Steps
1. Review current airflow measurements
2. Calculate required airflow based on equipment and personnel
3. Identify dead zones or recirculation areas
4. Check gas concentration levels (CH4, CO, NO2, dust)
5. Evaluate ventilation fan performance
6. Recommend adjustments

## Safety Thresholds
- O2: 19.5% minimum
- CO: 25 ppm TWA
- NO2: 3 ppm TWA
- CH4: 1% LEL
- Dust: 3 mg/m3 respirable

## Output
- Airflow adequacy assessment
- Gas concentration status
- Fan performance evaluation
- Recommended adjustments
- Energy optimization suggestions""",
        allowed_tools=["query_mining_database", "search_knowledge_base", "generate_report"],
        tags=["ventilation", "underground", "safety", "air_quality"]
    ),
    "equipment_diagnostic": MiningSkill(
        id="equipment_diagnostic",
        name="Equipment Diagnostic",
        description="Diagnose equipment issues based on sensor data, maintenance logs, and operating parameters.",
        domain="maintenance",
        effort="medium",
        prompt_template="""You are diagnosing a mining equipment issue.

## Analysis Steps
1. Review current sensor readings
2. Compare against normal operating ranges
3. Check maintenance history
4. Analyze failure patterns
5. Identify root cause
6. Recommend corrective action
7. Estimate time to failure if unresolved

## Normal Operating Ranges
- Engine temp: 82-93°C (alarm at 99°C)
- Oil pressure: 55-75 PSI
- Tire pressure: 88-96 PSI
- Vibration: <4.5 mm/s

## Output
- Issue identification
- Root cause analysis
- Urgency rating (Critical/High/Medium/Low)
- Corrective action plan
- Parts and labor estimate
- Downtime prediction""",
        allowed_tools=["query_mining_database", "search_knowledge_base"],
        args=[
            SkillArg(name="equipment_id", description="Equipment identifier", required=True),
            SkillArg(name="symptoms", description="Observed symptoms or issues", required=True),
        ],
        tags=["equipment", "maintenance", "diagnostic", "repair"]
    ),
    "safety_audit": MiningSkill(
        id="safety_audit",
        name="Safety Audit",
        description="Conduct a comprehensive safety audit of mining operations.",
        domain="safety",
        effort="high",
        prompt_template="""You are conducting a comprehensive safety audit.

## Audit Areas
1. Personal Protective Equipment compliance
2. Equipment safety (guards, emergency stops, alarms)
3. Ground conditions (benches, walls, floors)
4. Gas monitoring and ventilation
5. Fire prevention and suppression
6. Emergency response readiness
7. Training records and certifications
8. Incident reporting and investigation
9. Environmental compliance
10. Security and access control

## Rating System
- Green: Compliant, no issues
- Amber: Minor issues, corrective action within 30 days
- Red: Major issues, immediate action required
- Critical: Life-threatening, stop work immediately

## Output
- Audit findings by category
- Risk ratings (Green/Amber/Red/Critical)
- Corrective actions with deadlines
- Compliance score (0-100%)""",
        allowed_tools=["query_mining_database", "search_knowledge_base", "generate_report"],
        tags=["safety", "audit", "compliance", "inspection"]
    ),
    "market_analysis": MiningSkill(
        id="market_analysis",
        name="Market Analysis",
        description="Analyze commodity markets and provide pricing intelligence for mining products.",
        domain="finance",
        effort="medium",
        prompt_template="""You are analyzing commodity markets for a mining operation.

## Commodities to Track
- Gold (primary revenue)
- Silver
- Platinum
- Tanzanite
- Diamonds
- Rare earths (Nd, Dy, Tb)

## Analysis Steps
1. Fetch current spot prices
2. Analyze daily/weekly/monthly trends
3. Identify key market drivers
4. Calculate revenue impact on our production
5. Forecast near-term price direction
6. Recommend hedging strategy

## Output
- Current prices with change
- Trend analysis
- Revenue impact calculation
- Price forecast
- Hedging recommendations""",
        allowed_tools=["search_internet", "search_knowledge_base", "generate_report"],
        tags=["market", "pricing", "commodities", "revenue"]
    ),
    "environmental_compliance": MiningSkill(
        id="environmental_compliance",
        name="Environmental Compliance",
        description="Monitor and ensure environmental compliance for mining operations.",
        domain="environmental",
        effort="medium",
        prompt_template="""You are assessing environmental compliance for a mining operation.

## Key Areas
1. Water discharge quality (Cu <0.05 mg/L, pH 6.5-8.5)
2. Cyanide management (ICMC compliance)
3. Tailings dam safety
4. Air quality and dust control
5. Noise monitoring
6. Biodiversity impact
7. NORM handling (for REE deposits)
8. Waste management and recycling

## Compliance Status
- Compliant: Meeting all standards
- Minor breach: Within tolerance, corrective action needed
- Major breach: Exceeding limits, immediate action required

## Output
- Compliance status by area
- Monitoring data summary
- Corrective actions needed
- Regulatory reporting requirements""",
        allowed_tools=["query_mining_database", "search_knowledge_base", "generate_report"],
        tags=["environment", "compliance", "regulations", "monitoring"]
    ),
}


class SkillManager:
    """
    Mining skills system adapted from Claude Code's skill system.
    Skills are domain-specific task templates that encapsulate
    mining expertise, workflows, and best practices.
    """

    SKILLS_DIR = "data/skills"

    def __init__(self):
        self._dir = Path(self.SKILLS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._skills = MINING_SKILLS.copy()
        self._load_custom_skills()

    def _load_custom_skills(self):
        for skill_file in self._dir.glob("*.json"):
            try:
                data = json.loads(skill_file.read_text())
                skill = MiningSkill(**data)
                self._skills[skill.id] = skill
            except Exception as e:
                logger.warning(f"Failed to load custom skill {skill_file}: {e}")

    def get_skill(self, skill_id: str) -> Optional[MiningSkill]:
        return self._skills.get(skill_id)

    def list_skills(self, domain: str = None, enabled_only: bool = True) -> List[MiningSkill]:
        skills = list(self._skills.values())
        if domain:
            skills = [s for s in skills if s.domain == domain]
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        return sorted(skills, key=lambda s: s.name)

    def search_skills(self, query: str) -> List[MiningSkill]:
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            score = 0
            if query_lower in skill.name.lower():
                score += 3
            if query_lower in skill.description.lower():
                score += 2
            for tag in skill.tags:
                if query_lower in tag.lower():
                    score += 2
            if score > 0:
                results.append((score, skill))
        results.sort(key=lambda x: -x[0])
        return [s for _, s in results]

    def get_skill_prompt(self, skill_id: str, args: Dict[str, str] = None) -> str:
        skill = self.get_skill(skill_id)
        if not skill:
            return f"Unknown skill: {skill_id}"
        prompt = skill.prompt_template
        if args:
            for key, value in args.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", value)
        return prompt

    def render_skills_for_prompt(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["## Available Mining Skills", ""]
        for skill in skills:
            effort_indicator = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(skill.effort, "⚪")
            lines.append(f"### {effort_indicator} {skill.name} (`{skill.id}`)")
            lines.append(f"{skill.description}")
            if skill.args:
                lines.append(f"**Args:** {', '.join(a.name for a in skill.args if a.required)}")
            lines.append("")
        return "\n".join(lines)

    def match_skill_to_query(self, query: str) -> Optional[MiningSkill]:
        query_lower = query.lower()
        best_match = None
        best_score = 0
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            score = 0
            for tag in skill.tags:
                if tag in query_lower:
                    score += 3
            if skill.name.lower() in query_lower:
                score += 5
            for kw in skill.description.lower().split():
                if kw in query_lower and len(kw) > 3:
                    score += 1
            if score > best_score:
                best_score = score
                best_match = skill
        return best_match if best_score >= 3 else None

    def create_custom_skill(self, skill: MiningSkill) -> bool:
        try:
            self._skills[skill.id] = skill
            path = self._dir / f"{skill.id}.json"
            path.write_text(skill.model_dump_json(indent=2))
            logger.info(f"Created custom skill: {skill.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create skill: {e}")
            return False
