import os
import re
import json
import time
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

#: Domain keywords that force a real (tool-backed) answer even for short
#: casual-looking messages — mirrors the mock router so lite-mode never breaks
#: genuinely actionable questions like "list tasks".
DOMAIN_KEYWORDS = frozenset([
    "price", "gold", "silver", "market", "budget", "finance", "payroll",
    "procurement", "cost", "spend", "task", "production", "report", "mining",
    "equipment", "grade", "drill", "ore", "conveyor", "shaft", "sop",
    "search", "internet", "news", "regulation", "ocr", "image", "invoice",
    "photo", "document", "pdf", "export", "summary", "memory", "team",
    "geology", "variant",
])


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
33. **render_satellite** - Render satellite band data (bands: {name: 2D array}; composite: true_color/false_color/mineral/swir/vegetation or {R,G,B} mapping) to a PNG shown inline in the chat. Optional annotations at explicit pixel coords. USE to show satellite imagery as an inline, downloadable photo.
34. **render_index** - Compute a spectral index (ndvi, ndwi, ndmi, bsi, iron_oxide, ferrous) from provided bands and render it as an inline PNG with a colormap.
35. **annotate_image** - Burn labels/boxes/arrows/circles onto an existing rendered image (image_file_key) at explicit pixel coordinates and add the annotated copy to the chat.

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

### Continuity & Follow-Up (Act like a partner, not a stateless API)
- The personalised user context above is YOUR memory of this user. Use it.
- Greet or respond as someone who already knows them: reference their concession,
  equipment, FX rate, and past decisions naturally — never explain that you
  "found a memory".
- When the user references something from a past session or "before", surface it
  from the personalised context instead of asking them to re-supply it.
- Look for OPEN THREADS from previous sessions (earlier user questions that were
  answered but never acted on). If this query continues one, say so and carry the
  thread forward.
- At the END of complex replies, proactively offer the most useful next question
  or action based on THEIR situation (e.g. pull satellite imagery for their exact
  coordinates, price their Kapoeta gold at black-market rate, update equipment
  registers). Suggest concrete follow-ups once, briefly — do not spam them.
- If new personal facts emerge in this conversation (owner names, mineral finds,
  machine additions, price agreements, preferences), state that you will remember
  them going forward.
- Never hallucinate facts you don't have. When unsure about a user detail, ask a
  concise clarifying question rather than guessing.

### Visual Sharing (Show, don't just tell)
- When the user asks about satellite imagery, terrain, spectral data, or any
  pixel-based mining analysis, USE render_satellite / render_index and present
  the actual rendered image INLINE in the chat so they can see and download it.
  Never answer with text alone when an image is clearly valuable.
- Unless the user explicitly requests the original GeoTIFF/raw format, deliver
  satellite imagery as a rendered PNG photo (true_color or false_color) via
  render_satellite.
- When a satellite or photo is analysed and annotated, create an annotated copy
  with annotate_image (boxes, labels, arrows at the actual coordinates of the
  finding) and share that annotated version inline.
- You may only render what you actually have. bands for render_satellite/
  render_index MUST come from real data already in the conversation or provided
  by the user. If you do not have band data, say so and ask, or point them to
  /api/satellite endpoints — NEVER invent band values, coordinates, or pixels.
- annotate_image coordinates MUST be the actual pixel coordinates of a real
  feature in the image. Never draw annotations at guessed positions.

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
{persona_section}
{user_profile_section}
{team_section}
{memory_context_section}
{rag_context_section}
{knowledge_digest_section}"""


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

        # Token-conservation caches (thread-safe, TTL-bounded)
        self._rag_cache = {}
        self._rag_cache_ts = {}
        self._team_digest_cache = {}
        self._team_digest_cache_ts = {}
        self._fact_gate = {}
        self._module_lock = __import__("threading").RLock()

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

    # ── Token conservation helpers ────────────────────────────────────────

    def _env_int(self, key: str, default: int) -> int:
        try:
            return int(os.getenv(key, str(default)))
        except (TypeError, ValueError):
            return default

    def _env_float(self, key: str, default: float) -> float:
        try:
            return float(os.getenv(key, str(default)))
        except (TypeError, ValueError):
            return default

    def _is_casual_message(self, message: str) -> bool:
        """True = answer without tools (saves ~6.4K tool-schema tokens/turn).

        Mirrors the mock router's conversational path: greetings, or short
        non-domain chit-chat. Domain keywords force tools, keeping the
        assistant fully cooperative on anything actionable.
        """
        text = (message or "").strip()
        if not text:
            return True
        lowered = text.lower()
        if any(tok in lowered for tok in GREETING_TOKENS):
            return True
        words = [w for w in re.findall(r"[a-z']+", lowered) if w]
        if len(words) <= 4 and not any(k in lowered for k in DOMAIN_KEYWORDS):
            return True
        return False

    def _cached(self, cache: dict, cache_ts: dict, key: str, ttl: Optional[float] = None) -> Optional[Any]:
        if ttl is None:
            ttl = self._env_float("TOKEN_CACHE_TTL_S", 300.0)
        with self._module_lock:
            if key in cache_ts:
                age = time.time() - cache_ts[key]
                if age < ttl:
                    return cache.get(key)
                cache.pop(key, None)
                cache_ts.pop(key, None)
        return None

    def _store_cached(self, cache: dict, cache_ts: dict, key: str, value: Any) -> None:
        with self._module_lock:
            cache[key] = value
            cache_ts[key] = time.time()
            if len(cache) > 256:
                for oldest in sorted(cache_ts, key=cache_ts.get)[:128]:
                    cache.pop(oldest, None)
                    cache_ts.pop(oldest, None)

    def _build_team_digest(self, admin_user) -> str:
        """Aggregate every team account's identity + memory + recent activity so the
        admin (Frank) agent sees the full team in one context block."""
        try:
            from backend.auth import team_members
            parts = []
            for member in team_members():
                name = member.display_name or member.username
                role = member.role_title or member.role
                lines = [f"- {name} (username: {member.username}) — {role}"]
                if member.email:
                    lines.append(f"  email: {member.email}")
                profile = self.memory_engine.retrieve_user_profile(member.username) if self.memory_engine else {}
                if profile:
                    facts = [f"    {k}: {v}" for k, v in profile.items() if k != "history"]
                    if facts:
                        lines.append("  memory profile:")
                        lines.extend(facts[:12])
                # Last few exchanges for this member across sessions
                try:
                    recent = self._recent_member_exchanges(member.username, 3)
                except Exception:
                    recent = ""
                if recent:
                    lines.append("  recent work:")
                    lines.append("    " + "\n    ".join(recent.splitlines()))
                parts.append("\n".join(lines))
            return "\n\n".join(parts)
        except Exception as e:
            logger.debug(f"Team digest build failed: {e}")
            return ""

    def _recent_member_exchanges(self, tenant_id: str, cap: int = 3) -> str:
        """Pull the most recent user/assistant exchanges for a tenant."""
        if not (self.memory_engine and self.memory_engine.postgres_client):
            return ""
        convos = self.memory_engine.postgres_client.get_recent_conversations(limit=6, tenant_id=tenant_id) or []
        out_lines = []
        for conv in convos:
            for msg in (conv.get("messages") or []):
                role = msg.get("role", "")
                content = (msg.get("content", "") or "").strip()
                if not content or content.startswith("[Attached:"):
                    continue
                if role in ("user", "assistant") and len(out_lines) < cap * 2:
                    out_lines.append(f"{role}: {content[:200]}")
                if len(out_lines) >= cap * 2:
                    break
            if len(out_lines) >= cap * 2:
                break
        return "\n".join(out_lines)

    def _build_system_prompt(self, state: AgentState) -> str:
        phone = state.get("phone_number", "unknown")
        session = state.get("session_id", "unknown")
        interaction_mode = state.get("interaction_mode", "web_chat")

        # Memories and conversation history are keyed by tenant user (e.g.
        # "baguley") while the stream carries a tenant-prefixed session id
        # ("baguley:sess_xxx"). Always derive the memory key from the session
        # prefix so profile lookup and awareness context hit the right user.
        memory_user = phone
        if ":" in str(session):
            memory_user = str(session).split(":", 1)[0]

        user_profile_section = ""
        try:
            awareness = self.memory_engine.build_awareness_context(
                memory_user,
                recent_limit=6,
                message_budget=3500,
                exclude_session=session,
            )
            if awareness:
                user_profile_section = "## Personalised User Context (this user, across all time)\n" + awareness
            else:
                user_profile_section = "## Personalised User Context\nNo prior information stored about this user yet."
        except Exception:
            user_profile_section = "## Personalised User Context\nUnable to retrieve user context."

        # Persona: each provisioned team member gets their own professional persona.
        persona_section = ""
        try:
            from backend.auth import USERS as AUTH_USERS, persona_prompt
            persona = persona_prompt(AUTH_USERS.get(memory_user))
            if persona:
                persona_section = "## Your Persona\n" + persona
        except Exception:
            pass

        # Team visibility for admins (Frank): surface every team account so the
        # agent can answer questions about the whole team and their work.
        # Cached ~TTL to avoid re-aggregating every member's profile/exchanges.
        team_section = ""
        try:
            from backend.auth import team_members, USERS as AUTH_USERS
            user_obj = AUTH_USERS.get(memory_user)
            if user_obj and user_obj.role == "admin":
                cached = self._cached(self._team_digest_cache, self._team_digest_cache_ts, f"team:{memory_user}")
                if cached is None:
                    digest = self._build_team_digest(user_obj)
                    self._store_cached(self._team_digest_cache, self._team_digest_cache_ts, f"team:{memory_user}", digest)
                else:
                    digest = cached
                if digest:
                    team_section = "## Team Overview (visible to you as admin)\n" + digest
        except Exception:
            team_section = ""

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

        # RAG: search all collections but cap breadth + per-hit snippet so the
        # context block stays inside the token budget. Results are cached by
        # (tenant, normalized query) so repeated questions skip the re-embed.
        rag_context_section = ""
        last_human = ""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                last_human = msg.content
                break

        rag_limit = self._env_int("TOKEN_RAG_LIMIT", 12)
        snippet_chars = self._env_int("TOKEN_RAG_SNIPPET_CHARS", 800)
        if last_human and self._should_rag(last_human):
            query_key = f"{memory_user}|{last_human.strip().lower()}"
            cached = self._cached(self._rag_cache, self._rag_cache_ts, query_key)
            if cached is not None:
                rag_context_section = cached
            else:
                try:
                    from ingestion.embeddings import embed_text
                    query_vector = embed_text(last_human)
                    if query_vector and self.mining_engine.vector_client:
                        vc = self.mining_engine.vector_client
                        all_results = []

                        # Search all 4 static collections PLUS this tenant's own KB.
                        collections = ["company_knowledge", "production_data", "financial_data", "long_term_memories"]
                        tenant_collection = f"company_knowledge_{memory_user}"
                        if tenant_collection not in collections:
                            collections.append(tenant_collection)
                        # Admin (Frank) also searches every team member's KB so he can
                        # see/answer from the whole team's documents and memories.
                        try:
                            from backend.auth import team_members, USERS as AUTH_USERS
                            user_obj = AUTH_USERS.get(memory_user)
                            if user_obj and user_obj.role == "admin":
                                for member in team_members():
                                    col = f"company_knowledge_{member.username}"
                                    if col not in collections:
                                        collections.append(col)
                        except Exception:
                            pass
                        for collection in collections:
                            try:
                                hits = vc.search_similarity(collection, query_vector, limit=8, score_threshold=0.30)
                                for hit in hits:
                                    hit["_collection"] = collection
                                all_results.extend(hits)
                            except Exception:
                                continue

                        # Sort by score, take the configured top-N.
                        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                        top_results = all_results[:rag_limit]

                        if top_results:
                            context_parts = []
                            for hit in top_results:
                                payload = hit.get("payload", {})
                                title = payload.get("title", "")
                                content = payload.get("content_preview", payload.get("content", ""))
                                score = hit.get("score", 0)
                                collection = hit.get("_collection", "")
                                if (title or content) and score > 0.30:
                                    from local_model.token_policy import truncate_text
                                    context_parts.append(f"[{collection}] {title} (relevance: {score:.2f}):\n{truncate_text(content, snippet_chars)}")
                            if context_parts:
                                rag_context_section = "RELEVANT KNOWLEDGE BASE CONTEXT (from vector search across all collections):\n\n" + "\n\n---\n\n".join(context_parts)
                        self._store_cached(self._rag_cache, self._rag_cache_ts, query_key, rag_context_section)
                except Exception as e:
                    logger.debug(f"RAG retrieval failed: {e}")

        # Knowledge digest: compact dataset index, injected ONLY for substantive
        # queries and capped to the configured budget. Full file content is
        # fetched on demand by load_knowledge_base_file — not auto-injected.
        knowledge_digest_section = ""
        try:
            from services.knowledge_digest import get_dataset_digest

            digest_chars = self._env_int("TOKEN_DIGEST_CHARS", 6000)
            if last_human and self._should_rag(last_human) and digest_chars > 0:
                dataset_index = get_dataset_digest(max_chars=digest_chars)
                if dataset_index:
                    knowledge_digest_section = "## Available Knowledge Bases (index only — load full files on demand)\n" + dataset_index
        except Exception as e:
            logger.debug(f"Knowledge digest failed: {e}")

        # Manual replacement instead of str.format() so literal braces in the
        # template (e.g. {R,G,B} mappings in tool docs) are preserved verbatim.
        prompt = COORDINATOR_PROMPT
        prompt = prompt.replace("{phone_number}", phone)
        prompt = prompt.replace("{session_id}", session)
        prompt = prompt.replace("{interaction_mode}", interaction_mode)
        prompt = prompt.replace("{user_profile_section}", user_profile_section)
        prompt = prompt.replace("{persona_section}", persona_section)
        prompt = prompt.replace("{team_section}", team_section)
        prompt = prompt.replace("{memory_context_section}", memory_context_section)
        prompt = prompt.replace("{rag_context_section}", rag_context_section)
        prompt = prompt.replace("{knowledge_digest_section}", knowledge_digest_section)
        return prompt

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
        tools = None
        if self._env_int("TOKEN_LITE_TOOLS", 1) and self._is_casual_message(last_human):
            tools = []
        response = self.llm.invoke(full_messages, tools=tools)
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
        phone = state.get("phone_number", "")

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

            elif tool_name == "render_satellite":
                # Renders satellite band data to a PNG shown inline in the chat.
                # Data is passed in `bands` (band-name -> 2D array). composite is
                # "true_color"/"false_color"/"mineral"/"swir"/"vegetation" or a
                # custom {"R":..., "G":..., "B":...} mapping. Optional `annotations`
                # drawn at explicit pixel coordinates.
                bands_arg = args.get("bands", {}) or {}
                composite = args.get("composite", "true_color")
                width = args.get("width")
                height = args.get("height")
                annotations = args.get("annotations") or []
                import numpy as _np
                bands = {}
                for name, data in bands_arg.items():
                    arr = _np.array(data, dtype=_np.float64)
                    if arr.ndim != 2:
                        raise ValueError(f"Band '{name}' must be 2D, got {arr.ndim}D")
                    bands[name] = arr
                from services.image_renderer import render_satellite_composite
                img = render_satellite_composite(bands, composite, width=width, height=height, annotations=annotations, subdir=str(phone or ""))
                _output_report = {
                    "filename": f"satellite_{composite if isinstance(composite, str) else 'custom'}.png",
                    "storage_uri": f"local://{img['file_key']}",
                    "mime_type": "image/png",
                    "size_bytes": img["size_bytes"],
                    "image": True,
                }
                result = f"Rendered satellite image ({img['width']}x{img['height']}) and added it to the chat as an image. URL: {img['file_url']}"

            elif tool_name == "render_index":
                bands_arg = args.get("bands", {}) or {}
                index = args.get("index", "ndvi")
                colormap = args.get("colormap", "viridis")
                width = args.get("width")
                height = args.get("height")
                import numpy as _np
                from services.image_renderer import compute_index, index_to_rgb, _save_rgb_to_file
                bands = {}
                for name, data in bands_arg.items():
                    arr = _np.array(data, dtype=_np.float64)
                    if arr.ndim != 2:
                        raise ValueError(f"Band '{name}' must be 2D, got {arr.ndim}D")
                    bands[name] = arr
                index_arr = compute_index(bands, index)
                rgb = index_to_rgb(index_arr, colormap=colormap)
                if width and height:
                    from services.image_renderer import build_rgb
                    h, w = rgb.shape[:2]
                    if h != height or w != width:
                        raise ValueError(f"Rendered size {w}x{h} does not match requested {width}x{height}")
                file_key, abs_path = _save_rgb_to_file(rgb, ext="png", subdir=str(phone or ""))
                _output_report = {
                    "filename": f"{index}_{colormap}.png",
                    "storage_uri": f"local://{file_key}",
                    "mime_type": "image/png",
                    "size_bytes": abs_path.stat().st_size,
                    "image": True,
                }
                result = f"Computed and rendered the {index} index ({rgb.shape[1]}x{rgb.shape[0]}) and added it to the chat as an image. URL: /files/{file_key}"

            elif tool_name == "annotate_image":
                # Burn annotations onto an existing rendered image. image_file_key
                # refers to a file under /files/ (e.g. "renders/xxx.png"). All
                # annotation coordinates are explicit pixel values — no guessing.
                image_file_key = args.get("image_file_key", "")
                annotations = args.get("annotations", []) or []
                if not image_file_key:
                    raise ValueError("image_file_key is required")
                if not annotations:
                    raise ValueError("annotations list must not be empty")
                from services.image_renderer import annotate_existing_image
                out = annotate_existing_image(image_file_key, annotations, subdir=str(phone or ""))
                _output_report = {
                    "filename": "annotated_image.png",
                    "storage_uri": f"local://{out['file_key']}",
                    "mime_type": "image/png",
                    "size_bytes": out["size_bytes"],
                    "image": True,
                }
                result = f"Annotated the image and added it to the chat. Annotated copy URL: {out['file_url']}"

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
        return {"messages": [t_msg], "output_report": locals().get("_output_report")}

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
            # Store the report content into the tenant's knowledge base so it
            # becomes retrievable later (REAL content only).
            tenant = str(state.get("phone_number", "") or "").split(":", 1)[0]
            if tenant and content.strip():
                self._index_into_tenant_kb(tenant, content, "report", f"Report_{state['session_id']}.pdf")
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
            session_id = state.get("session_id", "")
            memory_user = phone
            if ":" in str(session_id):
                memory_user = str(session_id).split(":", 1)[0]
            profile = self.memory_engine.retrieve_user_profile(memory_user)
            content = f"Retrieved User Memory profile for {memory_user}: {profile}" if profile else \
                    f"No stored memories found for {memory_user}. This may be a new user."
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
            "render_satellite": "coordinator",
            "render_index": "coordinator",
            "annotate_image": "coordinator",
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
            "render_satellite": self.node_coordinator,
            "render_index": self.node_coordinator,
            "annotate_image": self.node_coordinator,
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
            if result.get("output_report"):
                base_state["output_report"] = result["output_report"]
            last = messages[-1] if messages else None
            if isinstance(last, ToolMessage):
                return last.content
            if hasattr(last, "content"):
                return str(last.content)
            return str(result)
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}")
            return f"Tool execution failed: {_safe_str(e)}"

    def _index_into_tenant_kb(self, tenant_id: str, text: str, source: str, filename: str = ""):
        """Chunk + embed + upsert real text into the tenant's knowledge base
        collection (company_knowledge_{tenant_id}) so uploaded/generated
        content becomes retrievable by RAG. No-op on missing deps or errors."""
        try:
            if not tenant_id or not text or not text.strip():
                return 0
            if not self.mining_engine or not self.mining_engine.vector_client:
                return 0
            from ingestion.embeddings import chunk_text
            from ingestion.loader import index_documents_to_vector_db
            import hashlib

            chunks = chunk_text(text, max_chunk_size=1000, overlap=150)
            if not chunks:
                return 0
            docs = []
            for idx, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{tenant_id}_{source}_{filename}_{idx}".encode()).hexdigest()
                docs.append({
                    "id": doc_id,
                    "text": chunk,
                    "payload": {
                        "source": source,
                        "filename": filename or tenant_id,
                        "chunk_index": idx,
                        "tenant_id": tenant_id,
                        "content_preview": chunk[:500],
                        "title": filename or source,
                    },
                })
            collection = f"company_knowledge_{tenant_id}"
            count = index_documents_to_vector_db(
                self.mining_engine.vector_client, docs, collection_name=collection
            )
            logger.info(f"Indexed {count} chunks into {collection} (source={source})")
            return count
        except Exception as e:
            logger.warning(f"Tenant KB indexing failed ({source}): {e}")
            return 0

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
        max_rounds = self._env_int("TOKEN_MAX_ROUNDS", 8)
        # Casual (greeting / short non-domain) messages answer without the
        # 31-tool schema — saves ~6.4K tool-definition tokens per turn.
        tools = None
        if self._env_int("TOKEN_LITE_TOOLS", 1) and self._is_casual_message(text_message):
            tools = []
        while rounds < max_rounds:
            rounds += 1
            pending_tool_calls = {}
            try:
                for chunk in self.llm.stream(full_messages, tools=tools):
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
                if base_state.get("output_report"):
                    report = base_state["output_report"]
                    storage_uri = report.get("storage_uri", "")
                    if storage_uri.startswith("local://"):
                        file_key = storage_uri[len("local://"):]
                    elif storage_uri.startswith("s3://"):
                        parts = storage_uri.split("/", 3)
                        file_key = "/".join(parts[2:]) if len(parts) > 2 else storage_uri
                    else:
                        file_key = storage_uri
                    is_image = bool(report.get("image", False)) or str(report.get("mime_type", "")).startswith("image/")
                    event_type = "image" if is_image else "file"
                    yield {
                        "type": event_type,
                        "filename": report.get("filename", "report.pdf"),
                        "file_url": f"/files/{file_key}",
                        "mime_type": report.get("mime_type", "application/pdf"),
                        "size_bytes": report.get("size_bytes", 0),
                    }
                    base_state["output_report"] = None

        self._auto_store_memory(text_message, full_content, session_id)

        # LLM-based auto-learning: extract durable user facts from the exchange.
        # Gated to substantive, non-casual messages, throttled per session, and
        # run in a background thread so the chat stream is never blocked.
        try:
            if self.memory_engine and full_content and text_message:
                min_chars = self._env_int("TOKEN_FACT_MIN_CHARS", 20)
                interval_s = self._env_float("TOKEN_FACT_MIN_INTERVAL_S", 60.0)
                memory_user = str(session_id or "").split(":", 1)[0] if ":" in str(session_id) else phone_number
                if (
                    len(text_message.strip()) >= min_chars
                    and not self._is_casual_message(text_message)
                ):
                    now = time.time()
                    gate_key = str(session_id or memory_user)
                    last_run = self._fact_gate.get(gate_key, 0.0)
                    if last_run and (now - last_run) < interval_s:
                        logger.debug(f"Fact extraction throttled for {gate_key}")
                    else:
                        self._fact_gate[gate_key] = now
                        import threading
                        threading.Thread(
                            target=self.memory_engine.extract_and_store_facts,
                            args=(memory_user, f"User: {text_message}\nAssistant: {full_content}", self.llm),
                            daemon=True,
                        ).start()
        except Exception as e:
            logger.debug(f"Fact extraction/store skipped: {e}")

        yield {"type": "done", "content": full_content, "tool_calls": executed_tool_calls}
