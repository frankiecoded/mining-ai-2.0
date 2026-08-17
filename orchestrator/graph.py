import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Iterator
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage, SystemMessage

from orchestrator.state import AgentState
from local_model.adapter import LocalLLMAdapter, GREETING_TOKENS
from research.service import ResearchService
from document_service.service import DocumentService
from vision_service.service import VisionService
from voice_service.service import VoiceService
from mining_engine.service import MiningEngineService
from finance_engine.service import FinanceEngineService
from memory_engine.service import MemoryEngineService
from coordinator.mining_coordinator import MiningCoordinator, MINING_AGENTS, AgentRole
from memory_engine.persistent import MemoryEngine
from task_manager.manager import TaskManager, TaskType, TaskPriority
from session_memory.manager import SessionMemoryManager
from services.cost_tracker import CostTracker
from services.skills import SkillManager
from services.compaction import ContextCompactor
from services.plan_mode import PlanMode
from services.prompt_suggestion import PromptSuggestionEngine
from services.todo_manager import TodoManager
from services.anomaly_detector import MiningAnomalySystem
from services.alert_system import AlertSystem, AlertSeverity, AlertStatus
from services.document_intelligence import DocumentIntelligence, AnalysisType
from services.audit_trail import AuditTrail, ActionType, ActionStatus
from services.report_generator import ReportGenerator, ReportData, ReportType

logger = logging.getLogger("ai_os.orchestrator")


def _safe_str(e: Exception) -> str:
    try:
        text = str(e).strip()
        return text[:200] if text else "Unknown error"
    except Exception:
        return "Unknown error"


COORDINATOR_PROMPT = """You are the AI Mining Operations Coordinator — a multi-agent intelligence system for a gold, precious stones, and rare earth metals mining operation focused on East and Central Africa.

You are NOT a simple chatbot. You are a COORDINATOR that directs specialized analysis agents and synthesizes their findings into actionable intelligence.

## How You Work

When a user asks a question, you:
1. **Decompose** the request into domain-specific tasks
2. **Dispatch** those tasks to specialized agents (geological, equipment, safety, financial, market, research)
3. **Synthesize** the agent findings into a unified, actionable response
4. **Remember** key findings for future queries (persistent memory)

## Your Agent Team

### Geological Analyst
Expert in ore grades, drill core analysis, soil sampling, assaying, exploration methods.
- Grade classifications: >5 g/t high, 1-5 g/t medium, 0.3-1 g/t low, <0.3 sub-economic
- Pathfinder elements: As, Sb, Bi, Te for gold deposits
- Drill types: Diamond (HQ/NQ/BQ), RC, AC
- Assaying: Fire assay (standard), ICP-MS, ICP-OES

### Equipment Specialist
Expert in mining equipment monitoring, maintenance, diagnostics, and optimization.
- CAT 797F: Engine temp 82-93°C normal, alarm at 99°C
- Haul trucks: Oil pressure 55-75 PSI, tire pressure 88-96 PSI
- Ball mills: 75% charge optimal, vibration <4.5 mm/s
- Conveyors: Speed 1.5-5.0 m/s

### Safety Compliance Officer
Expert in mining safety regulations, incident analysis, hazard identification.
- MSHA/Occupational Safety standards
- Cyanide safety: pH >10, HCN detection
- Gas monitoring: O2, LEL, CO, H2S
- Incident classification: Critical / High / Medium / Low

### Financial Analyst
Expert in mining financial analysis, budgeting, cost tracking.
- AISC: <$1000/oz excellent, $1000-1200 acceptable, >$1200 marginal
- Budget variance: Green ±5%, Amber -5% to -15%, Red >-15%
- NPV/IRR analysis for mining projects

### Market Intelligence Analyst
Expert in commodity markets, pricing trends, supply-demand dynamics.
- Gold/Silver ratio (historically 60-80)
- Central bank buying trends
- Tanzanite supply constraints (single-source, 25 years remaining)
- Diamond market: Lab-grown vs natural premium

### Research Analyst
Expert in regulations, technology scouting, competitive analysis.
- Mining regulations by jurisdiction (Kenya, Tanzania, DRC, Uganda, South Sudan)
- Environmental regulations and permitting
- Technology evaluation

## Available Tools
1. **query_mining_database** - Production logs, SOPs, equipment status, geological data
2. **query_finance_database** - Budgets, payroll, procurement, cost analysis
3. **search_knowledge_base** - Regulations, equipment manuals, company policies
4. **generate_report** - Create PDF/DOCX/XLSX reports
5. **analyze_image** - OCR, visual analysis of photos, maps, invoices
6. **search_internet** - Real-time market prices, regulations, mining news
7. **retrieve_user_memory** - User profile and conversation history
8. **search_archived_reports** - Historical reports and analyses
9. **delegate_to_agent** - Delegate task to a specialized agent (geological, equipment, safety, financial, market, research)
10. **get_agent_results** - Retrieve results from a delegated agent
11. **store_memory** - Store findings in persistent memory (operator, feedback, project, reference, shift, equipment)
12. **recall_memory** - Recall relevant memories for context
13. **create_task** - Create a background task for tracking (geological, equipment, safety, financial, market, analysis)
14. **update_task** - Update task progress
15. **list_tasks** - List active tasks and their status
16. **get_session_memory** - Get the live mine state document (active targets, equipment status, safety concerns, geological findings)
17. **update_session_memory** - Update sections of the live mine state document
18. **create_plan** - Create structured plans for complex operations (blast design, ventilation, drill programs, emergency response)
19. **get_plan** - Retrieve and view plans with all steps and dependencies
20. **approve_plan** - Approve plans before execution (required for safety)
21. **add_todo** - Add tasks to the shift task list (safety, maintenance, geological, financial, operations)
22. **update_todo** - Update task status (pending, in_progress, completed, blocked)
23. **list_todos** - View shift task list with priorities and categories
24. **get_safety_checklist** - Generate standard safety checklist for the shift
25. **get_cost_report** - View API usage, token consumption, and budget status
26. **suggest_next_actions** - Get proactive suggestions based on conversation context
27. **compact_context** - Compress conversation history to maintain focus
28. **check_anomalies** - ML-based anomaly detection for production, safety, equipment, financial data
29. **check_alerts** - Check active alerts and notifications with escalation
30. **analyze_document** - AI-powered document analysis, extraction, and compliance checking
31. **get_audit_log** - Query complete audit trail of all system activity and AI decisions
32. **generate_report_from_data** - Generate comprehensive PDF/DOCX reports from mine data

## Coordinator Behavior (ALWAYS follow)

### Multi-Step Analysis
- Break complex requests into domain-specific sub-tasks
- Call multiple tools in sequence to gather comprehensive data
- Cross-reference findings across domains (e.g., grade + market price + cost = profitability)
- Complete the FULL analysis before responding

### Proactive Intelligence
- Don't just answer what was asked — anticipate what else matters
- If gold grade is discussed, also check current gold price and AISC
- If equipment status is checked, also check related safety parameters
- If budget is discussed, compare against production targets
- Use suggest_next_actions to offer relevant follow-ups

### Tool Chaining
- Always verify data before responding (don't guess)
- Use search_internet for real-time prices when discussing value
- Use query_mining_database for operational data
- Use search_knowledge_base for standards and procedures
- Generate reports for complex multi-domain analyses

### Safety First
- Safety concerns ALWAYS override other analysis
- If a safety issue is detected, lead with it
- Never minimize safety risks
- Always provide immediate corrective actions for safety issues
- Use get_safety_checklist at the start of each shift

### Plan Mode
- For complex operations (blast design, ventilation changes), use create_plan
- Plans require approval before execution
- Always add steps with dependencies and risk assessment
- Present plans for review before transitioning to execution

### Session Memory
- Update the live mine state document as you learn new information
- Track active drilling targets, equipment status, safety concerns
- Record recent decisions and pending actions
- The session memory provides context continuity across the conversation

### Task Management
- Use add_todo for operational tasks and action items
- Use create_task for tracked background analyses
- Mark tasks as completed when done
- Prioritize safety-critical tasks

### Response Structure
1. **Lead with the most actionable finding** (not a summary of what you did)
2. **Explain the significance** (what it means for operations)
3. **Provide supporting data** (specific numbers, dates, thresholds)
4. **Recommend actions** (what to do next)
5. **Cite sources** (which tools provided the data)

### Memory Integration
- Store important findings for future reference
- Recall relevant past findings when analyzing similar queries
- Track operator preferences and feedback
- Note equipment patterns and recurring issues

## Response Guidelines
- Conversational tone, not robotic. Explain meaning, not just numbers.
- Your audience ranges from beginners to experts. No jargon without explanation.
- When you give a figure, always explain what it means and why it matters.
- Never make assumptions. If unsure, say so or ask.
- Be concise but thorough.
- For complex queries, synthesize findings from multiple tools into a coherent narrative.

## Domain Focus
- Primary: Gold mining (CIL, gravity, heap leach)
- Secondary: Tanzanite, diamonds, rubies, emeralds, tsavorite
- Tertiary: Rare earth elements (Nd, Dy, Tb)
- Geography: South Sudan, Kenya, Uganda, DRC, Tanzania, Zimbabwe, Mozambique

## User Context
- Phone: {phone_number}
- Session: {session_id}
- Interaction Mode: {interaction_mode}
{user_profile_section}
{memory_context_section}
{rag_context_section}"""


class AIOrchestrator:
    """
    AI Orchestrator with multi-agent coordinator, persistent memory,
    and task management. Routes between voice, vision, research,
    document generation, and domain databases.
    """

    def __init__(
        self,
        llm: LocalLLMAdapter,
        research_service: ResearchService,
        doc_service: DocumentService,
        vision_service: VisionService,
        voice_service: VoiceService,
        mining_engine: MiningEngineService,
        finance_engine: FinanceEngineService,
        memory_engine: MemoryEngineService
    ):
        self.llm = llm
        self.research_service = research_service
        self.doc_service = doc_service
        self.vision_service = vision_service
        self.voice_service = voice_service
        self.mining_engine = mining_engine
        self.finance_engine = finance_engine
        self.memory_engine = memory_engine

        self.coordinator = MiningCoordinator(
            llm_adapter=llm,
            memory_engine=None,
            task_manager=None
        )
        self.persistent_memory = MemoryEngine()
        self.task_manager = TaskManager()
        self.session_memory = SessionMemoryManager()
        self.cost_tracker = CostTracker()
        self.skill_manager = SkillManager()
        self.compactor = ContextCompactor()
        self.plan_mode = PlanMode()
        self.prompt_suggestion = PromptSuggestionEngine(self.skill_manager)
        self.todo_manager = TodoManager()
        self.anomaly_system = MiningAnomalySystem()
        self.alert_system = AlertSystem()
        self.document_intelligence = DocumentIntelligence()
        self.audit_trail = AuditTrail()
        self.report_generator = ReportGenerator()

        self.anomaly_system.initialize_sample_data()

        self.coordinator.memory = self.persistent_memory
        self.coordinator.task_manager = self.task_manager
        self.compactor.session_memory = self.session_memory

        self._system_prompt_cache = None
        self._system_prompt_cache_key = None

        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("preprocess_attachments", self.node_preprocess_attachments)
        graph.add_node("agent", self.node_agent)
        graph.add_node("research_node", self.node_research)
        graph.add_node("document_node", self.node_document)
        graph.add_node("vision_node", self.node_vision)
        graph.add_node("mining_node", self.node_mining)
        graph.add_node("finance_node", self.node_finance)
        graph.add_node("memory_node", self.node_memory)
        graph.add_node("archive_node", self.node_archive)
        graph.add_node("coordinator_node", self.node_coordinator)

        graph.set_entry_point("preprocess_attachments")
        graph.add_edge("preprocess_attachments", "agent")

        graph.add_conditional_edges(
            "agent",
            self.route_agent_decision,
            {
                "research": "research_node",
                "document": "document_node",
                "vision": "vision_node",
                "mining": "mining_node",
                "finance": "finance_node",
                "memory": "memory_node",
                "archive": "archive_node",
                "coordinator": "coordinator_node",
                "end": END
            }
        )

        graph.add_edge("research_node", "agent")
        graph.add_edge("document_node", "agent")
        graph.add_edge("vision_node", "agent")
        graph.add_edge("mining_node", "agent")
        graph.add_edge("finance_node", "agent")
        graph.add_edge("memory_node", "agent")
        graph.add_edge("archive_node", "agent")
        graph.add_edge("coordinator_node", "agent")

        return graph.compile()

    def _should_rag(self, message: str) -> bool:
        text = (message or "").strip()
        if not text:
            return False
        lowered = text.lower()
        if any(tok in lowered for tok in GREETING_TOKENS):
            return False
        words = [w for w in re.findall(r"[a-z']+", lowered) if w]
        return len(words) > 4

    def _build_system_prompt(self, state: AgentState) -> str:
        phone = state.get("phone_number", "unknown")
        session = state.get("session_id", "unknown")
        interaction_mode = state.get("interaction_mode", "web_chat")

        user_profile_section = ""
        try:
            profile = self.memory_engine.retrieve_user_profile(phone)
            if profile:
                profile_lines = [f"- {k}: {v}" for k, v in profile.items() if k != "history"]
                user_profile_section = "User Profile:\n" + "\n".join(profile_lines)
            else:
                user_profile_section = "User Profile: No prior information stored."
        except Exception:
            user_profile_section = "User Profile: Unable to retrieve."

        memory_context_section = ""
        try:
            last_human = ""
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    last_human = msg.content
                    break
            if last_human:
                memory_context = self.persistent_memory.recall_for_context(last_human, max_tokens=1500)
                if memory_context:
                    memory_context_section = "Relevant Memory Context:\n" + memory_context
        except Exception as e:
            logger.debug(f"Memory recall failed: {e}")

        rag_context_section = ""
        last_human = ""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                last_human = msg.content
                break

        if last_human and self._should_rag(last_human):
            try:
                from ingestion.embeddings import embed_text
                query_vector = embed_text(last_human)
                if query_vector:
                    rag_results = self.mining_engine.vector_client.search_similarity(
                        "company_knowledge", query_vector, limit=5
                    ) if self.mining_engine.vector_client else []
                    if rag_results:
                        context_parts = []
                        for hit in rag_results:
                            payload = hit.get("payload", {})
                            title = payload.get("title", "")
                            preview = payload.get("content_preview", "")
                            score = hit.get("score", 0)
                            if (title or preview) and score > 0.3:
                                context_parts.append(f"- {title} (relevance: {score:.2f}): {preview[:200]}")
                        if context_parts:
                            rag_context_section = "Relevant Knowledge Base Context:\n" + "\n".join(context_parts)
            except Exception as e:
                logger.debug(f"RAG retrieval failed: {e}")

        return COORDINATOR_PROMPT.format(
            phone_number=phone,
            session_id=session,
            interaction_mode=interaction_mode,
            user_profile_section=user_profile_section,
            memory_context_section=memory_context_section,
            rag_context_section=rag_context_section
        )

    def node_preprocess_attachments(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Preprocessing Attachments...")
        attachments = state.get("attachments", [])
        updated_messages = list(state.get("messages", []))
        extracted = dict(state.get("extracted_data", {}))

        for attach in attachments:
            mime = attach.get("mime_type", "")
            uri = attach.get("storage_uri", "")
            raw_bytes = b"Simulated attachment binary content."

            if "audio" in mime or uri.endswith(".ogg") or uri.endswith(".wav"):
                transcript = self.voice_service.speech_to_text(raw_bytes, mime)
                updated_messages.append(HumanMessage(content=f"[Voice Note Transcript]: {transcript}"))
            elif "image" in mime or uri.endswith(".png") or uri.endswith(".jpg"):
                ocr_text = self.vision_service.run_ocr(raw_bytes, attach.get("name", ""))
                extracted["ocr_text"] = ocr_text
                v_analysis = self.vision_service.analyze_image_objects(raw_bytes, attach.get("name", ""))
                extracted["vision_objects"] = v_analysis
                extracted["image_path"] = attach.get("storage_uri", "")
            else:
                text = attach.get("text", "")
                if not text and attach.get("storage_uri"):
                    try:
                        from backend.file_reader import extract_text
                        from pathlib import Path
                        if Path(attach["storage_uri"]).exists():
                            text = extract_text(attach.get("name", "file"), Path(attach["storage_uri"]).read_bytes())
                    except Exception as e:
                        logger.error(f"Document attachment extraction failed: {e}")
                        text = ""
                if text:
                    truncated = text[:12000]
                    note = "\n\n(Content truncated — file was longer)" if len(text) > 12000 else ""
                    updated_messages.append(HumanMessage(content=f"[Attached File: {attach.get('name', 'file')}]\n\n{truncated}{note}"))

        return {"messages": updated_messages, "extracted_data": extracted}

    def node_agent(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Invoking AI coordinator...")
        last_human = ""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                last_human = msg.content
                break
        cache_key = (state.get("session_id"), state.get("phone_number"), state.get("interaction_mode"), last_human)
        if self._system_prompt_cache_key != cache_key:
            self._system_prompt_cache = self._build_system_prompt(state)
            self._system_prompt_cache_key = cache_key
        system_prompt = self._system_prompt_cache
        messages = list(state["messages"])
        extracted = state.get("extracted_data", {})
        system_content = system_prompt
        if "ocr_text" in extracted:
            system_content += f"\n\nOCR Extracted Text:\n{extracted['ocr_text']}"
        if "vision_objects" in extracted:
            system_content += f"\n\nVisual Analysis:\n{extracted['vision_objects']}"
        full_messages = [SystemMessage(content=system_content)] + messages
        response = self.llm.invoke(full_messages)
        return {"messages": [response]}

    def node_coordinator(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Coordinator processing multi-agent task...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}

        tool_call = tool_calls[0]
        tool_name = tool_call["name"]
        args = tool_call["args"]
        session_id = state.get("session_id", "default")

        try:
            if tool_name == "delegate_to_agent":
                agent_role = args.get("agent_role", "")
                task_prompt = args.get("prompt", "")
                agent_def = MINING_AGENTS.get(agent_role)
                if not agent_def:
                    result = f"Unknown agent role: {agent_role}. Available roles: {', '.join(MINING_AGENTS.keys())}"
                else:
                    shared_context = {}
                    for key, value in self.coordinator._scratchpad.items():
                        shared_context[key] = str(value)[:500]
                    agent_prompt = self.coordinator.build_agent_prompt(agent_role, task_prompt, shared_context)
                    agent_messages = [SystemMessage(content=agent_prompt)]
                    agent_response = self.llm.invoke(agent_messages)
                    result = f"[{agent_def.name}] {agent_response.content}"
                    self.coordinator.set_scratchpad(f"last_{agent_role}", result)

            elif tool_name == "get_agent_results":
                agent_role = args.get("agent_role", "")
                result = self.coordinator.get_scratchpad(f"last_{agent_role}")
                if result is None:
                    result = f"No results from {agent_role} yet. Use delegate_to_agent first."

            elif tool_name == "store_memory":
                memory_type = args.get("memory_type", "project")
                title = args.get("title", "")
                content = args.get("content", "")
                tags = args.get("tags", [])
                from memory_engine.types import MemoryType
                try:
                    mtype = MemoryType(memory_type)
                except ValueError:
                    mtype = MemoryType.PROJECT
                entry = self.persistent_memory.store(mtype, title, content, tags)
                result = f"Memory stored: {entry.title} ({entry.memory_type.value})"

            elif tool_name == "recall_memory":
                query = args.get("query", "")
                entries = self.persistent_memory.recall(query, limit=5)
                if entries:
                    result = "\n".join([
                        f"[{e.memory_type.value}] {e.title}: {e.content[:200]}"
                        for e in entries
                    ])
                else:
                    result = "No relevant memories found."

            elif tool_name == "create_task":
                title = args.get("title", "")
                description = args.get("description", "")
                task_type_str = args.get("task_type", "analysis")
                priority_str = args.get("priority", "medium")
                try:
                    ttype = TaskType(task_type_str)
                except ValueError:
                    ttype = TaskType.ANALYSIS
                try:
                    priority = TaskPriority(priority_str)
                except ValueError:
                    priority = TaskPriority.MEDIUM
                task = self.task_manager.create_task(title, description, ttype, priority)
                self.task_manager.start_task(task.id)
                result = f"Task created: {task.id} - {task.title} [RUNNING]"

            elif tool_name == "update_task":
                task_id = args.get("task_id", "")
                activity = args.get("activity", "")
                task = self.task_manager.update_progress(task_id, activity=activity)
                if task:
                    result = f"Task {task_id} updated: {task.progress.last_activity}"
                else:
                    result = f"Task {task_id} not found."

            elif tool_name == "list_tasks":
                tasks = self.task_manager.active_tasks()
                if tasks:
                    result = "\n".join([t.summary() for t in tasks])
                else:
                    result = "No active tasks."

            elif tool_name == "get_session_memory":
                section = self.session_memory.build_prompt_section(session_id)
                if section:
                    result = section
                else:
                    result = "No session memory yet. The session memory will be built as we continue the conversation."

            elif tool_name == "update_session_memory":
                section_name = args.get("section", "current_state")
                content = args.get("content", "")
                append = args.get("append", False)
                self.session_memory.update_section(session_id, section_name, content, append)
                result = f"Session memory section '{section_name}' updated."

            elif tool_name == "create_plan":
                title = args.get("title", "")
                description = args.get("description", "")
                plan_type = args.get("plan_type", "general")
                plan = self.plan_mode.create_plan(session_id, title, description, plan_type)
                result = f"Plan created: {plan['id']} - {title}\n\nUse add_step to add phases, then approve_plan when ready."

            elif tool_name == "get_plan":
                plan_id = args.get("plan_id", "")
                if plan_id:
                    plan = self.plan_mode.get_plan(plan_id)
                else:
                    plan = self.plan_mode.get_active_plan_for_session(session_id)
                if plan:
                    result = self.plan_mode.render_plan(plan["id"])
                else:
                    result = "No active plan found. Use create_plan to start planning."

            elif tool_name == "approve_plan":
                plan_id = args.get("plan_id", "")
                success = self.plan_mode.approve_plan(plan_id, approved_by=session_id)
                if success:
                    result = f"Plan {plan_id} approved. You can now transition to execution."
                else:
                    result = f"Could not approve plan {plan_id}. Check the plan ID."

            elif tool_name == "add_todo":
                content = args.get("content", "")
                priority = args.get("priority", "medium")
                category = args.get("category", "general")
                assignee = args.get("assignee", "")
                todo = self.todo_manager.add_todo(session_id, content, priority, category, assignee)
                result = f"Todo added: {todo.id} - {content} [{priority}]"

            elif tool_name == "update_todo":
                todo_id = args.get("todo_id", "")
                status = args.get("status", None)
                notes = args.get("notes", None)
                todo = self.todo_manager.update_todo(session_id, todo_id, status=status, notes=notes)
                if todo:
                    result = f"Todo {todo_id} updated: {todo.content} [{todo.status.value}]"
                else:
                    result = f"Todo {todo_id} not found."

            elif tool_name == "list_todos":
                status_filter = args.get("status", None)
                category_filter = args.get("category", None)
                todos = self.todo_manager.list_todos(session_id, status=status_filter, category=category_filter)
                if todos:
                    result = self.todo_manager.render_todos(session_id)
                else:
                    result = "No tasks in the list."

            elif tool_name == "get_safety_checklist":
                self.todo_manager.get_safety_checklist(session_id)
                result = self.todo_manager.render_todos(session_id)

            elif tool_name == "get_cost_report":
                result = self.cost_tracker.format_cost_report()

            elif tool_name == "suggest_next_actions":
                query = ""
                for msg in reversed(state.get("messages", [])):
                    if isinstance(msg, HumanMessage):
                        query = msg.content
                        break
                suggestions = self.prompt_suggestion.suggest(query)
                if suggestions:
                    result = "## Suggested Next Actions\n\n" + "\n".join(
                        f"- {s['text']} ({s['source']})" for s in suggestions
                    )
                else:
                    result = "No specific suggestions. What would you like to focus on?"

            elif tool_name == "compact_context":
                result = f"Context compaction available. Current message count: {len(state.get('messages', []))}. " \
                         f"Use this when the conversation gets long to maintain focus."

            elif tool_name == "check_anomalies":
                query = args.get("query", "all")
                result_data = self.anomaly_system.analyze_query(query)
                if "health" in result_data:
                    health = result_data["health"]
                    result = f"## Anomaly Detection Status\n\n**Health Score:** {health['health_score']}/100 ({health['status']})\n"
                    result += f"**Active Anomalies:** {health['active_anomalies']}\n"
                    result += f"**Metrics Tracked:** {health['metrics_tracked']}\n"
                    if result_data.get("active_anomalies"):
                        result += "\n### Active Anomalies\n"
                        for a in result_data["active_anomalies"][:5]:
                            result += f"- **[{a['severity'].upper()}]** {a['title']}: {a['description']}\n"
                elif "trends" in result_data:
                    result = "## Metric Trends\n\n"
                    for name, trend in result_data["trends"].items():
                        result += f"- **{name}:** {trend.get('trend', 'N/A')} ({trend.get('change_percent', 0):+.1f}%)\n"
                elif "forecasts" in result_data:
                    result = "## Forecasts\n\n"
                    for name, forecast in result_data["forecasts"].items():
                        result += f"- **{name}:** Current {forecast.get('current_value', 0):.2f}, Trend {forecast.get('trend_per_period', 0):+.2f}/period\n"
                else:
                    result = json.dumps(result_data, indent=2, default=str)

            elif tool_name == "check_alerts":
                category = args.get("category", "all")
                alerts = self.alert_system.get_active_alerts(category if category != "all" else None)
                if alerts:
                    result = self.alert_system.format_alerts_for_display(alerts)
                else:
                    result = "No active alerts. All systems operating within normal parameters."

            elif tool_name == "analyze_document":
                doc_id = args.get("document_id", "")
                analysis_type_str = args.get("analysis_type", "summary")
                try:
                    analysis_type = AnalysisType(analysis_type_str)
                except ValueError:
                    analysis_type = AnalysisType.SUMMARY
                analysis = self.document_intelligence.analyze_document(doc_id, analysis_type)
                if analysis:
                    result = self.document_intelligence.format_analysis_for_display(analysis)
                else:
                    result = f"Document '{doc_id}' not found. Use document upload to register documents first."

            elif tool_name == "get_audit_log":
                query_type = args.get("query_type", "recent")
                user_id = args.get("user_id", "")
                limit = args.get("limit", 20)

                if query_type == "statistics":
                    stats = self.audit_trail.get_statistics()
                    result = f"## Audit Trail Statistics\n\n**Total Entries:** {stats['total_entries']}\n"
                    if stats.get("by_action_type"):
                        result += "\n### By Action Type\n"
                        for action, count in stats["by_action_type"].items():
                            result += f"- {action}: {count}\n"
                elif query_type == "security":
                    events = self.audit_trail.get_security_events()
                    if events:
                        result = "## Security Events\n\n"
                        for event in events[:limit]:
                            result += f"- `{event['timestamp']}` **{event['type']}** - {event['description']}\n"
                    else:
                        result = "No security events in the last 7 days."
                elif query_type == "ai_decisions":
                    decisions = self.audit_trail.get_ai_decision_log()
                    if decisions:
                        result = "## AI Decision Log\n\n"
                        for decision in decisions[:limit]:
                            result += f"- `{decision['timestamp']}` {decision['decision']}\n"
                    else:
                        result = "No AI decisions logged in the last 7 days."
                else:
                    from services.audit_trail import AuditQuery
                    query = AuditQuery(limit=limit)
                    if user_id:
                        query.user_id = user_id
                    entries = self.audit_trail.query_entries(query)
                    result = self.audit_trail.format_entries_for_display(entries, limit)

            elif tool_name == "generate_report_from_data":
                report_type_str = args.get("report_type", "production")
                title = args.get("title", None)

                report_data = ReportData(
                    production={"tonnage_mined": 25000, "tonnage_milled": 24000, "gold_grade": 5.2, "recovery_rate": 92.5, "gold_produced": 350},
                    safety={"incidents": 0, "near_misses": 2, "inspections": 15, "score": 95},
                    financial={"revenue": 700000, "operating_costs": 450000, "cost_per_ounce": 1250, "margin": 750},
                    equipment={"Excavator 1": {"availability": 92, "hours": 18}, "Haul Truck 3": {"availability": 88, "hours": 16}},
                    alerts=self.alert_system.get_active_alerts()
                )

                template_map = {
                    "production": "daily_production",
                    "safety": "weekly_safety",
                    "financial": "monthly_financial",
                    "shift": "shift_handover",
                    "equipment": "equipment_status",
                    "custom": "daily_production"
                }
                template_name = template_map.get(report_type_str, "daily_production")

                report_result = self.report_generator.generate_report(
                    template_name=template_name,
                    data=report_data,
                    title=title,
                    period_start=datetime.now() - timedelta(days=1),
                    period_end=datetime.now()
                )

                if "error" not in report_result:
                    result = report_result.get("content", "Report generated successfully.")
                else:
                    result = f"Report generation failed: {report_result['error']}"

            else:
                result = f"Unknown coordinator tool: {tool_name}"

        except Exception as e:
            logger.error(f"Coordinator tool '{tool_name}' failed: {e}", exc_info=True)
            result = f"Coordinator error: {_safe_str(e)}"

        t_msg = ToolMessage(content=result, tool_call_id=tool_call["id"])
        return {"messages": [t_msg]}

    def node_research(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Executing Research Service...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        query = tool_call["args"].get("query", "")
        try:
            sources = self.research_service.search(query)
            res = self.research_service.rank_and_verify(sources, query)
            content = res.get("answer", "No research results found.")
        except Exception as e:
            logger.error(f"Research failed: {e}")
            content = f"Research service error: {str(e)}. Please try rephrasing your query."
        t_msg = ToolMessage(content=content, tool_call_id=tool_call["id"])
        return {"messages": [t_msg]}

    def node_document(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Executing Document generation...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        title = tool_call["args"].get("title", "Report")
        content = tool_call["args"].get("content", "")
        file_type = tool_call["args"].get("file_type", "pdf")
        try:
            report_meta = self.doc_service.process_and_store_report(
                filename=f"Report_{state['session_id']}.pdf",
                content=content,
                file_type=file_type
            )
            result = f"Report generated successfully. Link: {report_meta['storage_uri']}"
            return {"messages": [ToolMessage(content=result, tool_call_id=tool_call["id"])], "output_report": report_meta}
        except Exception as e:
            logger.error(f"Document generation failed: {e}")
            return {"messages": [ToolMessage(content=f"Document generation error: {str(e)}", tool_call_id=tool_call["id"])]}

    def node_vision(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Vision/OCR request...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        image_path = tool_call["args"].get("image_path", "")
        analysis_type = tool_call["args"].get("analysis_type", "full_analysis")
        extracted = state.get("extracted_data", {})
        image_bytes = extracted.get("image_bytes", b"dummy")
        if "image_path" in extracted:
            image_path = extracted["image_path"]
        try:
            ocr_text = self.vision_service.run_ocr(image_bytes, image_path)
            vision_result = self.vision_service.analyze_image_objects(image_bytes, image_path)
            result_parts = [f"OCR Extracted Text: {ocr_text}"]
            if analysis_type in ("object_detection", "full_analysis"):
                result_parts.append(f"Object Analysis: {vision_result}")
            content = "\n".join(result_parts)
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            content = f"Vision analysis error: {str(e)}"
        t_msg = ToolMessage(content=content, tool_call_id=tool_call["id"])
        return {"messages": [t_msg]}

    def node_mining(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Querying mining databases...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        query = tool_call["args"].get("query", "")
        results = []
        try:
            sop = self.mining_engine.retrieve_sop(query)
            if sop:
                results.append(f"SOP/Procedure:\n{sop}")
        except Exception as e:
            logger.warning(f"SOP retrieval failed: {e}")
        try:
            prod_data = self.mining_engine.query_production_data("recent")
            if prod_data:
                prod_summary = "\n".join([
                    f"- {r.get('date')}: {r.get('shaft')} - {r.get('tons_milled')}t milled, "
                    f"grade {r.get('head_grade_cu')}, recovery {r.get('recovery_rate')}, "
                    f"gold recovered {r.get('concentrate_produced', 'N/A')} oz"
                    for r in prod_data[:5]
                ])
                results.append(f"Recent Gold Production Data:\n{prod_summary}")
        except Exception as e:
            logger.warning(f"Production data retrieval failed: {e}")
        if any(kw in query.lower() for kw in ["equipment", "truck", "status", "machine"]):
            try:
                equip_data = self.mining_engine.query_equipment_status(None)
                if equip_data:
                    equip = equip_data[0] if isinstance(equip_data, list) else equip_data
                    results.append(f"Equipment Status ({equip.get('equipment_id')}):\n"
                                 f"Type: {equip.get('type')}, Status: {equip.get('status')}\n"
                                 f"Operating Hours: {equip.get('operating_hours')}\n"
                                 f"Engine Temp: {equip.get('engine_temp_c')}°C\n"
                                 f"Oil Pressure: {equip.get('oil_pressure_psi')} PSI\n"
                                 f"Next Service: {equip.get('next_service')}")
            except Exception as e:
                logger.warning(f"Equipment query failed: {e}")
        if any(kw in query.lower() for kw in ["gemstone", "tanzanite", "ruby", "diamond", "emerald", "tsavorite"]):
            try:
                gem_path = os.path.join(os.path.dirname(__file__), "..", "datasets", "precious_stones", "gemstones.json")
                with open(gem_path) as f:
                    gem_data = json.load(f)
                gemstones = gem_data.get("gemstones", {})
                for name, info in list(gemstones.items())[:4]:
                    price = info.get("market_price", {})
                    results.append(f"{name}: ${price.get('per_carat_usd', 'N/A')}/ct - {info.get('description', '')[:100]}")
            except Exception as e:
                logger.warning(f"Gemstone data failed: {e}")
        if any(kw in query.lower() for kw in ["soil", "sample", "exploration", "assay", "drill"]):
            try:
                geo_path = os.path.join(os.path.dirname(__file__), "..", "datasets", "geology", "gold_geology_exploration.json")
                with open(geo_path) as f:
                    geo_data = json.load(f)
                methods = geo_data.get("exploration_methods", {})
                results.append("Exploration Methods Available:\n")
                for method_name, method_info in list(methods.get("geochemical_prospecting", {}).get("methods", {}).items())[:3]:
                    results.append(f"- {method_name}: {method_info.get('description', '')[:100]}")
            except Exception as e:
                logger.warning(f"Geology data failed: {e}")
        if any(kw in query.lower() for kw in ["market", "price", "gold price", "commodity"]):
            try:
                from research.market_scraper import get_market_scraper
                scraper = get_market_scraper()
                if scraper:
                    loop = asyncio.get_event_loop()
                    prices = loop.run_until_complete(scraper.get_all_prices())
                    if prices:
                        gold = prices.get("gold", {})
                        silver = prices.get("silver", {})
                        results.append(f"Live Market Data:\n"
                                     f"Gold: ${gold.get('price', 'N/A')}/oz ({gold.get('change', 'N/A')})\n"
                                     f"Silver: ${silver.get('price', 'N/A')}/oz ({silver.get('change', 'N/A')})\n"
                                     f"Source: {gold.get('source', 'Market data')}")
            except Exception as e:
                logger.warning(f"Market data failed: {e}")
        t_msg = ToolMessage(
            content="\n\n".join(results) if results else "No mining data found for this query.",
            tool_call_id=tool_call["id"]
        )
        return {"messages": [t_msg]}

    def node_finance(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Querying finance databases...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        query = tool_call["args"].get("query", "")
        results = []
        query_lower = query.lower()
        try:
            if "payroll" in query_lower:
                payroll = self.finance_engine.get_payroll_summary()
                results.append(f"Payroll Summary ({payroll.get('month')}):\n"
                             f"Total Employees: {payroll.get('total_employees')}\n"
                             f"Gross Payroll: ${payroll.get('gross_payroll', 0):,.0f}\n"
                             f"Tax Withheld: ${payroll.get('tax_withheld', 0):,.0f}\n"
                             f"Benefits Cost: ${payroll.get('benefits_cost', 0):,.0f}\n"
                             f"Net Paid: ${payroll.get('net_paid', 0):,.0f}")
            else:
                for dept in ["exploration", "operations", "environmental", "processing", "safety", "corporate", "market_intelligence"]:
                    if dept in query_lower or "budget" in query_lower or "all" in query_lower:
                        budget = self.finance_engine.get_budget_vs_actual(dept)
                        status_indicator = "OVER" if budget.get("variance", 0) < 0 else "UNDER"
                        results.append(
                            f"{budget.get('department', dept).title()} Department (FY{budget.get('fiscal_year', '2026')}):\n"
                            f"  Allocated: ${budget.get('budget_allocated', 0):,.0f}\n"
                            f"  Spent: ${budget.get('actual_spend', 0):,.0f}\n"
                            f"  Variance: ${budget.get('variance', 0):,.0f} ({status_indicator} budget)\n"
                            f"  Status: {budget.get('status', 'unknown')}"
                        )
                        break
                if not results:
                    budget = self.finance_engine.get_budget_vs_actual("exploration")
                    results.append(f"Financial Overview:\n{budget}")
        except Exception as e:
            logger.error(f"Finance query failed: {e}")
            results.append(f"Finance service error: {str(e)}")
        t_msg = ToolMessage(content="\n\n".join(results), tool_call_id=tool_call["id"])
        return {"messages": [t_msg]}

    def node_memory(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Memory retrieval...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        phone = tool_call["args"].get("phone_number", state.get("phone_number", ""))
        try:
            profile = self.memory_engine.retrieve_user_profile(phone)
            content = f"Retrieved User Memory profile for {phone}: {profile}" if profile else \
                    f"No stored memories found for {phone}. This may be a new user."
        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            content = f"Memory retrieval error: {str(e)}"
        t_msg = ToolMessage(content=content, tool_call_id=tool_call["id"])
        return {"messages": [t_msg]}

    def node_archive(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Searching archived reports...")
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {"messages": [ToolMessage(content="No tool call found.", tool_call_id="fallback")]}
        tool_call = tool_calls[0]
        query = tool_call["args"].get("query", "")
        try:
            archived = self.memory_engine.search_archived_reports(query)
            if archived:
                archive_text = "\n".join([
                    f"- {r.get('title', r.get('payload', {}).get('title', 'Unknown'))}: "
                    f"{r.get('summary', r.get('payload', {}).get('content_preview', ''))[:150]}"
                    for r in archived
                ])
            else:
                archive_text = "No archived reports found matching this query."
        except Exception as e:
            logger.error(f"Archive search failed: {e}")
            archive_text = f"Archive search error: {str(e)}"
        t_msg = ToolMessage(content=f"Archived Reports:\n{archive_text}", tool_call_id=tool_call["id"])
        return {"messages": [t_msg]}

    def route_agent_decision(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            return "end"
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return "end"
        call_name = tool_calls[0]["name"]
        logger.info(f"Routing tool call: '{call_name}'")
        routing_map = {
            "query_mining_database": "mining",
            "query_finance_database": "finance",
            "search_knowledge_base": "research",
            "search_internet": "research",
            "generate_report": "document",
            "analyze_image": "vision",
            "retrieve_user_memory": "memory",
            "search_archived_reports": "archive",
            "delegate_to_agent": "coordinator",
            "get_agent_results": "coordinator",
            "store_memory": "coordinator",
            "recall_memory": "coordinator",
            "create_task": "coordinator",
            "update_task": "coordinator",
            "list_tasks": "coordinator",
            "get_session_memory": "coordinator",
            "update_session_memory": "coordinator",
            "create_plan": "coordinator",
            "get_plan": "coordinator",
            "approve_plan": "coordinator",
            "add_todo": "coordinator",
            "update_todo": "coordinator",
            "list_todos": "coordinator",
            "get_safety_checklist": "coordinator",
            "get_cost_report": "coordinator",
            "suggest_next_actions": "coordinator",
            "compact_context": "coordinator",
            "check_anomalies": "coordinator",
            "check_alerts": "coordinator",
            "analyze_document": "coordinator",
            "get_audit_log": "coordinator",
            "generate_report_from_data": "coordinator",
        }
        return routing_map.get(call_name, "end")

    def run(self, session_id, phone_number, text_message, attachments=None, interaction_mode="web_chat") -> AgentState:
        from commands.handler import handle_command, command_service
        from commands.service import CommandState
        session = command_service.get_session(phone_number)
        if text_message.strip().startswith("/") or session.state != CommandState.IDLE:
            try:
                cmd_result = handle_command(phone_number=phone_number, text=text_message, attachments=attachments or [])
                if cmd_result and cmd_result.get("type") == "command_response":
                    return AgentState(
                        messages=[AIMessage(content=cmd_result["text"])],
                        session_id=session_id, phone_number=phone_number,
                        attachments=attachments or [], extracted_data={},
                        output_report=None, next_step="", interaction_mode=interaction_mode
                    )
            except Exception as e:
                logger.error(f"Command handling failed: {e}")
                return AgentState(
                    messages=[AIMessage(content="Command error. Type /help for available commands.")],
                    session_id=session_id, phone_number=phone_number,
                    attachments=attachments or [], extracted_data={},
                    output_report=None, next_step="", interaction_mode=interaction_mode
                )
        initial_state = AgentState(
            messages=[HumanMessage(content=text_message)],
            session_id=session_id, phone_number=phone_number,
            attachments=attachments or [], extracted_data={},
            output_report=None, next_step="", interaction_mode=interaction_mode
        )
        try:
            return self.workflow.invoke(initial_state, {"recursion_limit": 50})
        except Exception as e:
            logger.error(f"Orchestrator execution failed: {e}", exc_info=True)
            return AgentState(
                messages=[AIMessage(content="I apologize, but I encountered an error processing your request. Please try again or rephrase your question.")],
                session_id=session_id, phone_number=phone_number,
                attachments=attachments or [], extracted_data={},
                output_report=None, next_step="", interaction_mode=interaction_mode
            )

    def stream(self, session_id, phone_number, text_message, attachments=None, interaction_mode="web_chat", history=None) -> Iterator[Dict[str, Any]]:
        messages = history or []
        messages.append(HumanMessage(content=text_message))
        initial_state = AgentState(
            messages=messages, session_id=session_id, phone_number=phone_number,
            attachments=attachments or [], extracted_data={},
            output_report=None, next_step="", interaction_mode=interaction_mode
        )
        try:
            for event in self.workflow.stream(initial_state, {"recursion_limit": 50}):
                yield event
        except Exception as e:
            logger.error(f"Orchestrator streaming failed: {e}", exc_info=True)
            yield {"error": True, "messages": [AIMessage(content=f"I apologize, but I encountered an error processing your request. Error: {str(e)[:200]}")]}

    async def arun(self, session_id, phone_number, text_message, attachments=None, interaction_mode="web_chat") -> AgentState:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.run(session_id, phone_number, text_message, attachments, interaction_mode)
        )

    def _tool_router(self) -> Dict[str, Any]:
        return {
            "query_mining_database": self.node_mining,
            "query_finance_database": self.node_finance,
            "search_knowledge_base": self.node_research,
            "search_internet": self.node_research,
            "generate_report": self.node_document,
            "analyze_image": self.node_vision,
            "retrieve_user_memory": self.node_memory,
            "search_archived_reports": self.node_archive,
            "delegate_to_agent": self.node_coordinator,
            "get_agent_results": self.node_coordinator,
            "store_memory": self.node_coordinator,
            "recall_memory": self.node_coordinator,
            "create_task": self.node_coordinator,
            "update_task": self.node_coordinator,
            "list_tasks": self.node_coordinator,
            "get_session_memory": self.node_coordinator,
            "update_session_memory": self.node_coordinator,
            "create_plan": self.node_coordinator,
            "get_plan": self.node_coordinator,
            "approve_plan": self.node_coordinator,
            "add_todo": self.node_coordinator,
            "update_todo": self.node_coordinator,
            "list_todos": self.node_coordinator,
            "get_safety_checklist": self.node_coordinator,
            "get_cost_report": self.node_coordinator,
            "suggest_next_actions": self.node_coordinator,
            "compact_context": self.node_coordinator,
            "check_anomalies": self.node_coordinator,
            "check_alerts": self.node_coordinator,
            "analyze_document": self.node_coordinator,
            "get_audit_log": self.node_coordinator,
            "generate_report_from_data": self.node_coordinator,
        }

    def _execute_tool(self, name, tool_call, base_state) -> str:
        node = self._tool_router().get(name)
        if node is None:
            return f"Unknown tool: {name}"
        state = dict(base_state)
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state["messages"] = [ai_msg]
        try:
            result = node(state)
            messages = result.get("messages", [])
            last = messages[-1] if messages else None
            if isinstance(last, ToolMessage):
                return last.content
            if hasattr(last, "content"):
                return str(last.content)
            return str(result)
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}")
            return f"Tool execution failed: {_safe_str(e)}"

    def _auto_store_memory(self, query: str, response: str, session_id: str = ""):
        try:
            self.persistent_memory.auto_store_from_interaction(query, response, session_id)
        except Exception as e:
            logger.debug(f"Auto-store memory failed: {e}")

    def stream_conversation(self, session_id, phone_number, text_message, interaction_mode="web_chat", history=None, attachments=None) -> Iterator[Dict[str, Any]]:
        messages = list(history or [])
        attachments = attachments or []
        for attach in attachments:
            name = attach.get("name", "file")
            mime = (attach.get("mime_type", "") or "").lower()
            if mime.startswith("image/"):
                try:
                    from pathlib import Path
                    raw = Path(attach["storage_uri"]).read_bytes()
                    ocr_text = self.vision_service.run_ocr(raw, name)
                    v_analysis = self.vision_service.analyze_image_objects(raw, name)
                    block = f"[Attached Image: {name}]\n\nOCR Text:\n{ocr_text}\n\nVisual Analysis:\n{v_analysis}"
                    messages.append(HumanMessage(content=block))
                except Exception as e:
                    logger.error(f"Image attachment processing failed: {e}")
                    messages.append(HumanMessage(content=f"[Attached Image: {name}] (could not be analysed: {_safe_str(e)})"))
            else:
                text = attach.get("text", "") or ""
                if not text and attach.get("storage_uri"):
                    try:
                        from backend.file_reader import extract_text
                        from pathlib import Path
                        text = extract_text(name, Path(attach["storage_uri"]).read_bytes())
                    except Exception as e:
                        logger.error(f"Document attachment extraction failed: {e}")
                        text = ""
                if text:
                    truncated = text[:12000]
                    note = "\n\n(Content truncated — file was longer)" if len(text) > 12000 else ""
                    messages.append(HumanMessage(content=f"[Attached File: {name}]\n\n{truncated}{note}"))
                else:
                    messages.append(HumanMessage(content=f"[Attached File: {name}] (no extractable text)"))
        messages.append(HumanMessage(content=text_message))
        base_state = {
            "session_id": session_id, "phone_number": phone_number,
            "interaction_mode": interaction_mode, "attachments": attachments,
            "extracted_data": {}, "output_report": None, "next_step": "", "messages": messages,
        }
        system_prompt = self._build_system_prompt(base_state)
        full_messages = [SystemMessage(content=system_prompt)] + messages
        full_content = ""
        executed_tool_calls = []
        rounds = 0
        max_rounds = 15
        while rounds < max_rounds:
            rounds += 1
            pending_tool_calls = {}
            try:
                for chunk in self.llm.stream(full_messages):
                    delta = getattr(chunk, "content", "") or ""
                    if delta:
                        full_content += delta
                        yield {"type": "content", "content": delta}
                    calls = getattr(chunk, "tool_calls", None) or []
                    for tc in calls:
                        tc_id = tc.get("id", f"call_{tc.get('name','')}_{rounds}")
                        pending_tool_calls[tc_id] = {
                            "name": tc.get("name", ""), "args": tc.get("args", {}),
                            "id": tc_id, "type": "tool_call",
                        }
            except Exception as e:
                logger.error(f"LLM streaming failed: {e}", exc_info=True)
                if not full_content:
                    yield {"type": "content", "content": f"I'm sorry, something went wrong: {_safe_str(e)}"}
                    full_content = f"I'm sorry, something went wrong: {_safe_str(e)}"
                break
            if not pending_tool_calls:
                break
            pending_list = list(pending_tool_calls.values())
            executed_tool_calls.extend(pending_list)
            full_messages.append(AIMessage(content="", tool_calls=pending_list))
            for tc in pending_list:
                yield {"type": "tool_call", "name": tc["name"], "args": tc["args"]}
                tool_content = self._execute_tool(tc["name"], tc, base_state)
                full_messages.append(ToolMessage(content=tool_content, tool_call_id=tc["id"]))

        self._auto_store_memory(text_message, full_content, session_id)

        yield {"type": "done", "content": full_content, "tool_calls": executed_tool_calls}
