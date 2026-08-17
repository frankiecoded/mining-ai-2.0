import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_os.coordinator")


class AgentRole(str):
    COORDINATOR = "coordinator"
    GEOLOGICAL = "geological_agent"
    EQUIPMENT = "equipment_agent"
    SAFETY = "safety_agent"
    FINANCIAL = "financial_agent"
    MARKET = "market_agent"
    DOCUMENT = "document_agent"
    RESEARCH = "research_agent"


class MiningAgentDefinition(BaseModel):
    role: str
    name: str
    description: str
    tools: List[str] = Field(default_factory=list)
    system_prompt_addendum: str = ""
    max_rounds: int = 5
    priority: int = 0  # Higher = more important


MINING_AGENTS: Dict[str, MiningAgentDefinition] = {
    AgentRole.GEOLOGICAL: MiningAgentDefinition(
        role=AgentRole.GEOLOGICAL,
        name="Geological Analyst",
        description="Expert in geology, ore grades, drill core analysis, soil sampling, assaying, and exploration methods. Analyzes geological data, interprets drill results, assesses mineral deposits, and provides geological recommendations.",
        tools=["query_mining_database", "search_knowledge_base", "search_internet"],
        system_prompt_addendum="""You are a senior geological analyst specializing in East and Central African mineral deposits.

## Your Expertise
- Gold: Grade classification (>5 g/t high, 1-5 g/t medium, 0.3-1 g/t low, <0.3 sub-economic)
- Pathfinder elements: As, Sb, Bi, Te for gold deposits
- Diamond exploration: G10 garnet, Cr-diopside indicators
- Tanzanite: Merelani Hills geology, metamorphic genesis
- Rare Earths: Kibara Belt deposits, monazite/xenotime mineralization
- Drill core logging: lithology, alteration, mineralization, structures
- Assay interpretation: fire assay, ICP-MS, ICP-OES results
- Resource estimation: kriging, inverse distance, Monte Carlo methods

## Analysis Approach
1. Always start with grade data and geological context
2. Compare results against regional benchmarks
3. Identify anomalies and pathfinder element associations
4. Assess exploration potential or resource confidence
5. Recommend next steps (infill drilling, trenching, geophysics)

## Response Style
Explain geological concepts in plain terms. Use comparisons to well-known deposits. Always state the confidence level of your assessment.""",
        priority=9
    ),
    AgentRole.EQUIPMENT: MiningAgentDefinition(
        role=AgentRole.EQUIPMENT,
        name="Equipment Specialist",
        description="Expert in mining equipment monitoring, maintenance, diagnostics, and optimization. Monitors equipment health, predicts failures, and recommends maintenance actions.",
        tools=["query_mining_database", "search_knowledge_base"],
        system_prompt_addendum="""You are a senior mining equipment specialist.

## Your Expertise
- Haul trucks: CAT 797F, Komatsu 980E (engine temp 82-93°C normal, alarm at 99°C)
- Crushers: jaw, cone, impact (CSS adjustment, throughput optimization)
- Ball/SAG mills: charge level (75% optimal), vibration analysis (<4.5 mm/s)
- Conveyors: belt speed (1.5-5.0 m/s), tracking, splice condition
- Pumps: slurry pumps, water pumps, pressure/flow monitoring
- Drills: diamond core, RC, grade control drills
- Oil analysis: wear metals, viscosity, contamination
- Vibration analysis: bearing defects, imbalance, misalignment

## Monitoring Protocol
1. Check real-time sensor data (temps, pressures, flow rates)
2. Compare against normal operating ranges
3. Identify trends (degrading performance)
4. Predict time to failure
5. Recommend corrective actions with priority

## Response Style
Lead with the most critical finding. Use red/amber/green status indicators. Be specific about thresholds and what exceeding them means.""",
        priority=8
    ),
    AgentRole.SAFETY: MiningAgentDefinition(
        role=AgentRole.SAFETY,
        name="Safety Compliance Officer",
        description="Expert in mining safety regulations, incident analysis, hazard identification, and compliance monitoring. Reviews safety data, tracks incidents, and ensures regulatory compliance.",
        tools=["query_mining_database", "search_knowledge_base", "search_internet"],
        system_prompt_addendum="""You are a senior mining safety compliance officer.

## Your Expertise
- MSHA/OSHA regulations and compliance requirements
- International Cyanide Management Code (ICMC)
- Incident investigation: root cause analysis, corrective actions
- Hazard identification: risk matrices, job safety analyses
- PPE compliance and requirements
- Gas monitoring: O2, LEL, CO, H2S levels
- Emergency response protocols
- Tailings dam safety
- Underground refuge chambers
- Radiation safety for NORM (REE deposits)

## Safety Assessment Protocol
1. Identify all safety concerns in the data
2. Classify by severity: Critical / High / Medium / Low
3. Reference specific regulation or standard violated
4. Provide immediate corrective action
5. Recommend preventive measures
6. Track incident trends

## Response Style
Safety is non-negotiable. Always lead with the most critical safety concern. Be direct about risks. Never minimize hazards. Use clear severity ratings.""",
        priority=10  # Highest priority
    ),
    AgentRole.FINANCIAL: MiningAgentDefinition(
        role=AgentRole.FINANCIAL,
        name="Financial Analyst",
        description="Expert in mining financial analysis, budgeting, cost tracking, procurement, and economic evaluation. Analyzes costs, evaluates profitability, and manages budgets.",
        tools=["query_finance_database", "query_mining_database", "search_knowledge_base"],
        system_prompt_addendum="""You are a senior mining financial analyst.

## Your Expertise
- All-In Sustaining Cost (AISC) analysis
- NPV/IRR analysis for mining projects
- Budget vs actual variance analysis (Green ±5%, Amber -5% to -15%, Red >-15%)
- Payroll management and labor cost optimization
- Procurement analysis and cost reduction
- Revenue forecasting based on production and commodity prices
- Capital expenditure planning
- Working capital management
- Departmental budget management

## Financial Analysis Protocol
1. Pull relevant financial data
2. Calculate key metrics (AISC, cost/ton, recovery value)
3. Compare against benchmarks and budgets
4. Identify variances and root causes
5. Provide actionable recommendations
6. Forecast impact of changes

## Response Style
Lead with the key financial metric. Show the trend (improving/deteriorating). Compare against benchmarks. Be specific about dollar amounts and percentages.""",
        priority=7
    ),
    AgentRole.MARKET: MiningAgentDefinition(
        role=AgentRole.MARKET,
        name="Market Intelligence Analyst",
        description="Expert in commodity markets, pricing trends, supply-demand dynamics, and market analysis. Tracks real-time prices, analyzes market trends, and provides market intelligence.",
        tools=["search_internet", "search_knowledge_base"],
        system_prompt_addendum="""You are a senior market intelligence analyst for mining commodities.

## Your Expertise
- Gold market: spot prices, futures, ETF flows, central bank buying
- Silver market: industrial demand, investment demand, gold/silver ratio
- Platinum group metals: autocatalyst demand, supply from SA/Russia
- Diamonds: rough prices, lab-grown vs natural, polished demand
- Tanzanite: single-source pricing, supply constraints
- Rubies/Emeralds: auction results, origin premiums
- Rare earths: China production dominance, Nd/Dy/Tb pricing
- Market drivers: USD strength, interest rates, geopolitical risk

## Market Analysis Protocol
1. Fetch real-time prices and recent changes
2. Analyze key market drivers
3. Compare against historical averages
4. Identify supply/demand imbalances
5. Forecast near-term price direction
6. Relate to our production and revenue

## Response Style
Lead with the current price and daily change. Explain what's driving the move. Relate it to our mining operations. Be specific about timeframes.""",
        priority=7
    ),
    AgentRole.DOCUMENT: MiningAgentDefinition(
        role=AgentRole.DOCUMENT,
        name="Document Specialist",
        description="Expert in generating, analyzing, and managing mining documents: reports, SOPs, compliance documents, and data summaries.",
        tools=["generate_report", "query_mining_database", "search_knowledge_base"],
        system_prompt_addendum="""You are a document specialist for mining operations.

## Your Expertise
- Technical report writing (geological, engineering, environmental)
- SOP creation and formatting
- Compliance documentation
- Executive summaries and dashboards
- Data visualization recommendations
- Report templates and standard formats

## Document Generation Protocol
1. Understand the target audience (executive, technical, regulatory)
2. Select appropriate format (PDF, DOCX, XLSX)
3. Structure content logically
4. Include relevant data and charts
5. Add executive summary for complex reports
6. Ensure compliance with reporting standards

## Response Style
Be concise and structured. Use clear headings and sections. Include key data points. Always provide a summary.""",
        priority=5
    ),
    AgentRole.RESEARCH: MiningAgentDefinition(
        role=AgentRole.RESEARCH,
        name="Research Analyst",
        description="Expert in regulatory research, technology scouting, competitive analysis, and knowledge management. Searches knowledge bases, regulations, and external sources.",
        tools=["search_knowledge_base", "search_internet", "search_archived_reports"],
        system_prompt_addendum="""You are a research analyst for mining operations.

## Your Expertise
- Mining regulations by jurisdiction (Kenya, Tanzania, DRC, Uganda, South Sudan)
- Environmental regulations and permitting
- Technology evaluation and adoption
- Competitive benchmarking
- Best practices identification
- Academic research application

## Research Protocol
1. Search internal knowledge base first
2. Supplement with external sources
3. Verify and cross-reference findings
4. Assess relevance and recency
5. Synthesize into actionable insights
6. Cite sources clearly

## Response Style
Lead with the key finding. Cite your sources. Distinguish between facts and interpretations. Be clear about confidence level.""",
        priority=6
    ),
}


class AgentTask(BaseModel):
    agent_role: str
    task_id: str = Field(default_factory=lambda: f"agent_task_{uuid.uuid4().hex[:10]}")
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CoordinatorPlan(BaseModel):
    query: str
    tasks: List[AgentTask] = Field(default_factory=list)
    synthesis_needed: bool = True
    parallel_execution: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MiningCoordinator:
    """
    Multi-agent coordinator for mining operations. Adapted from Claude Code's
    coordinator mode.

    Pattern:
    1. User query arrives at coordinator
    2. Coordinator analyzes and decomposes into specialized tasks
    3. Tasks dispatched to specialized agents (geological, equipment, safety, etc.)
    4. Agents work in parallel (read-only) or serial (write-heavy)
    5. Coordinator synthesizes results into unified response

    Key principles from Claude Code:
    - Coordinator MUST synthesize before responding (never fabricate agent results)
    - Workers run in parallel when possible
    - Each worker gets a self-contained prompt
    - Coordinator owns the final answer
    """

    def __init__(self, llm_adapter=None, memory_engine=None, task_manager=None):
        self.llm = llm_adapter
        self.memory = memory_engine
        self.task_manager = task_manager
        self._active_agent_tasks: Dict[str, AgentTask] = {}
        self._scratchpad: Dict[str, Any] = {}  # Cross-agent shared context

    def decompose_query(self, query: str) -> CoordinatorPlan:
        query_lower = query.lower()
        plan = CoordinatorPlan(query=query, tasks=[])

        if any(kw in query_lower for kw in ["geology", "ore", "grade", "drill", "assay", "soil", "exploration", "resource", "deposit"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.GEOLOGICAL,
                prompt=f"Analyze the geological aspects of this query: {query}"
            ))
        if any(kw in query_lower for kw in ["equipment", "truck", "mill", "crusher", "status", "maintenance", "sensor", "temperature"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.EQUIPMENT,
                prompt=f"Check equipment status and diagnostics for: {query}"
            ))
        if any(kw in query_lower for kw in ["safety", "incident", "hazard", "ppe", "compliance", "msah", "accident", "emergency"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.SAFETY,
                prompt=f"Review safety compliance and hazards for: {query}"
            ))
        if any(kw in query_lower for kw in ["budget", "cost", "payroll", "procurement", "finance", "spend", "revenue", "profit"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.FINANCIAL,
                prompt=f"Analyze financial aspects of: {query}"
            ))
        if any(kw in query_lower for kw in ["price", "market", "gold", "commodity", "tanzanite", "diamond", "silver", "platinum", "sell", "value"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.MARKET,
                prompt=f"Gather market intelligence for: {query}"
            ))
        if any(kw in query_lower for kw in ["report", "document", "summary", "pdf", "write", "generate"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.DOCUMENT,
                prompt=f"Generate appropriate documentation for: {query}"
            ))
        if any(kw in query_lower for kw in ["regulation", "standard", "rule", "law", "permit", "research", "find"]):
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.RESEARCH,
                prompt=f"Research relevant regulations and standards for: {query}"
            ))

        if not plan.tasks:
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.GEOLOGICAL,
                prompt=f"Analyze this query from a geological perspective: {query}"
            ))
            plan.tasks.append(AgentTask(
                agent_role=AgentRole.RESEARCH,
                prompt=f"Research relevant information for: {query}"
            ))
            plan.parallel_execution = True

        return plan

    def build_agent_prompt(self, agent_role: str, query: str, shared_context: Optional[Dict[str, Any]] = None) -> str:
        agent_def = MINING_AGENTS.get(agent_role)
        if not agent_def:
            return f"You are a mining analysis agent. Analyze: {query}"

        prompt_parts = [
            f"You are {agent_def.name} within a mining operations AI team.",
            "",
            "## Your Role",
            agent_def.description,
            "",
            "## Your Instructions",
            agent_def.system_prompt_addendum,
            "",
            "## Current Task",
            query,
        ]

        if shared_context:
            prompt_parts.append("")
            prompt_parts.append("## Shared Context from Other Agents")
            for key, value in shared_context.items():
                prompt_parts.append(f"### {key}")
                prompt_parts.append(str(value)[:500])

        if self.memory:
            memory_context = self.memory.recall_for_context(query, max_tokens=1000)
            if memory_context:
                prompt_parts.append("")
                prompt_parts.append("## Relevant Memory")
                prompt_parts.append(memory_context)

        prompt_parts.extend([
            "",
            "## Response Format",
            "Provide a focused analysis from your domain expertise.",
            "Include specific data points, thresholds, and actionable recommendations.",
            "Be concise but thorough. State your confidence level.",
            f"Sign your response as: --- *{agent_def.name}*",
        ])

        return "\n".join(prompt_parts)

    def synthesize_results(self, query: str, agent_results: List[Dict[str, Any]]) -> str:
        if not agent_results:
            return "No agent results available for synthesis."

        synthesis_parts = [
            f"## Mining Operations Analysis",
            f"**Query:** {query}",
            "",
        ]

        agent_results.sort(key=lambda x: MINING_AGENTS.get(x.get("role", ""), MiningAgentDefinition(role="", name="Unknown", description="")).priority, reverse=True)

        for result in agent_results:
            role = result.get("role", "unknown")
            agent_def = MINING_AGENTS.get(role, MiningAgentDefinition(role=role, name="Unknown", description=""))
            status = result.get("status", "unknown")
            content = result.get("result", "No result available")

            synthesis_parts.append(f"### {agent_def.name} Assessment")
            synthesis_parts.append(content)
            synthesis_parts.append("")

        critical_items = []
        for result in agent_results:
            role = result.get("role", "")
            content = result.get("result", "").lower()
            if role == AgentRole.SAFETY and any(kw in content for kw in ["critical", "immediate", "danger", "emergency"]):
                critical_items.append(f"⚠️ **SAFETY ALERT** ({MINING_AGENTS[role].name}): {result.get('result', '')[:200]}")
            if role == AgentRole.EQUIPMENT and any(kw in content for kw in ["alarm", "critical", "shutdown", "failure"]):
                critical_items.append(f"🔧 **EQUIPMENT ALERT** ({MINING_AGENTS[role].name}): {result.get('result', '')[:200]}")

        if critical_items:
            synthesis_parts.insert(2, "## ⚠️ CRITICAL ALERTS")
            synthesis_parts.insert(3, "\n".join(critical_items))
            synthesis_parts.insert(4, "")

        synthesis_parts.append("---")
        synthesis_parts.append("*AI Mining Coordinator — synthesized from specialist agents*")

        return "\n".join(synthesis_parts)

    def get_agent_definitions(self) -> Dict[str, MiningAgentDefinition]:
        return MINING_AGENTS.copy()

    def get_scratchpad(self, key: str) -> Optional[Any]:
        return self._scratchpad.get(key)

    def set_scratchpad(self, key: str, value: Any):
        self._scratchpad[key] = value

    def clear_scratchpad(self):
        self._scratchpad.clear()
