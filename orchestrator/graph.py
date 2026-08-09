import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Iterator
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage, SystemMessage

from orchestrator.state import AgentState
from local_model.adapter import LocalLLMAdapter
from research.service import ResearchService
from document_service.service import DocumentService
from vision_service.service import VisionService
from voice_service.service import VoiceService
from mining_engine.service import MiningEngineService
from finance_engine.service import FinanceEngineService
from memory_engine.service import MemoryEngineService

logger = logging.getLogger("ai_os.orchestrator")

SYSTEM_PROMPT_TEMPLATE = """You are the AI Operating System for a gold, precious stones, and rare earth metals mining operation focused on East and Central Africa. You are an expert assistant with deep knowledge of precious metals mining, gemstone recovery, financial management, geological assessment, market intelligence, safety compliance, and environmental regulations.

## Your Capabilities
You have access to the following tools:
1. **query_mining_database** - Production logs, SOPs, equipment status, geological data, grade control, soil samples
2. **query_finance_database** - Budgets, payroll, procurement, cost analysis
3. **search_knowledge_base** - Regulations, equipment manuals, geological standards, company policies, market intelligence
4. **generate_report** - Create PDF/DOCX/XLSX reports and documents
5. **analyze_image** - OCR, visual analysis of invoices, conveyor belts, rock samples, maps, ore photographs
6. **search_internet** - Real-time market prices (gold, silver, platinum, diamonds, tanzanite, rubies, emeralds, tsavorite), regulations, and mining news
7. **retrieve_user_memory** - User profile and conversation history
8. **search_archived_reports** - Historical reports and analyses
9. **process_voice_query** - Handle voice/video call queries and generate conversational responses

## Response Guidelines
- Always cite specific data points from tool responses (grades, tonnages, dates, costs, prices)
- Reference SOPs and regulations by their code numbers when available
- For complex queries, call multiple tools and synthesize the results
- Generate PDF reports for multi-step analyses or when the user requests a document
- Flag anomalies: equipment temps >90°C, budget variances >10%, safety non-conformances
- For voice/video calls: Use natural, conversational language. Avoid markdown. Be concise but thorough.
- When responding to voice queries, structure answers as spoken dialogue - use transitions and natural flow
- Ask clarifying questions when needed - be conversational, not robotic
- Remember context from earlier in the conversation
- Use professional, concise language suitable for WhatsApp delivery
- If you need more information, ask clarifying questions before making assumptions

## Domain Expertise

### Gold Mining
- Grade classifications: >5 g/t high grade, 1-5 g/t medium, 0.3-1 g/t low, <0.3 g/t sub-economic
- Recovery targets: CIL >95%, gravity >85%, heap leach 60-80%
- Processing: Cyanidation (CIL/CIP), gravity separation, flotation, heap leach
- AIC (All-In Sustaining Cost): <$1000/oz excellent, $1000-1200 acceptable, >$1200 marginal
- Key indicators: Au, As, Sb, Bi, Te as pathfinder elements
- Gold extraction: CIL, CIP, heap leach, pressure oxidation, biooxidation, gravity, amalgamation
- Gold refining: Electrowinning, smelting, aqua regia, Miller, Wohlwill processes
- LBMA good delivery: 99.5% minimum purity
- Doré bars: 80-95% gold, shipped to refinery

### Precious Stones
- Diamond grading: 4Cs (Carat, Color D-Z, Clarity FL-I3, Cut Excellent-Poor)
- Tanzanite: Only sourced from Merelani Hills, Tanzania; AAA blue $1,500+/ct
- Rubies: Pigeon blood (Myanmar) most valuable at $50,000+/ct; Mozambique emerging
- Emeralds: Colombia (Muzo) finest; Zambia (Kagem) largest producer
- Tsavorite: Rarer than emerald; only East African deposits (Tanzania/Kenya)

### Rare Earth Elements
- Critical for clean energy (EVs, wind turbines), defense, electronics
- China dominates 60% of global production
- East African deposits: Kibara Belt (DRC), Wigu Hill/Tunduru (Tanzania), Karako-Kayah (Kenya)
- Processing requires multi-stage solvent extraction with radioactive waste management
- Nd, Dy, Tb most valuable for permanent magnets

### Market Intelligence
- Track live gold prices (Kitco, World Gold Council, Bloomberg)
- Monitor gold/silver ratio (historically 60-80)
- Follow central bank buying trends (major price driver)
- Track tanzanite supply constraints (single-source, 25 years remaining)
- Diamond market: Lab-grown vs natural premium analysis

### Equipment Monitoring
- CAT 797F: Engine temp 82-93°C normal, alarm at 99°C
- Haul trucks: Oil pressure 55-75 PSI, tire pressure 88-96 PSI
- Conveyor belts: Speed 1.5-5.0 m/s, belt tracking >25mm misalignment requires action
- Ball mills: 75% charge optimal, vibration <4.5 mm/s
- Crushers: CSS adjustment for target P80

### Safety
- MSHA/Occupational Safety standards
- Underground refuge chambers, gas monitoring (O2, LEL, CO, H2S)
- PPE: Hard hat, high-vis, steel toe boots, respirator, eye/ear protection
- Emergency response: Evacuation protocols, fire suppression, first aid
- Cyanide safety: pH >10, HCN detection, antidote kits

### Geology & Exploration
- Soil sampling: Ridge, stream sediment, auger methods
- Pathfinder elements: Au (As, Sb, Bi, Te), diamonds (G10 garnet, Cr-diopside)
- Geophysical methods: IP, magnetic, EM, resistivity
- Exploration stages: Reconnaissance → Prospecting → Discovery → Delineation → Feasibility
- Drill types: Diamond (HQ/NQ/BQ), RC, AC, RAB
- Assaying: Fire assay (standard), ICP-MS, ICP-OES, AAS

### Environmental
- Water discharge limits: Cu <0.05 mg/L, pH 6.5-8.5
- Cyanide management: International Cyanide Management Code (ICMC)
- Tailings management: Dam safety, water recycling, zero discharge preferred
- NORM (Naturally Occurring Radioactive Material) handling for REE deposits
- Budget variance thresholds: Green ±5%, Amber -5% to -15%, Red >-15%

## Geographic Focus
- Primary: South Sudan, Kenya, Uganda, DRC, Tanzania
- Secondary: Zimbabwe, Mozambique, Zambia, Ethiopia, Rwanda, Burundi
- Global context: Australia, Canada, USA, Russia, China, Ghana, South Africa

## User Context
- Phone: {phone_number}
- Session: {session_id}
- Interaction Mode: {interaction_mode}
{user_profile_section}
{rag_context_section}"""


class AIOrchestrator:
    """
    AI Orchestrator coordinates flows using LangGraph.
    Routes between voice processing, vision/OCR extraction,
    research, document generation, and domain databases.
    Uses RAG context and memory for intelligent responses.
    Supports WhatsApp chat, voice calls, and video calls.
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

        return graph.compile()

    def _build_system_prompt(self, state: AgentState) -> str:
        """Builds the rich system prompt with user context and RAG results."""
        phone = state.get("phone_number", "unknown")
        session = state.get("session_id", "unknown")
        interaction_mode = state.get("interaction_mode", "whatsapp_chat")

        user_profile_section = ""
        try:
            profile = self.memory_engine.retrieve_user_profile(phone)
            if profile:
                profile_lines = [f"- {k}: {v}" for k, v in profile.items()]
                user_profile_section = "User Profile:\n" + "\n".join(profile_lines)
            else:
                user_profile_section = "User Profile: No prior information stored."
        except Exception:
            user_profile_section = "User Profile: Unable to retrieve."

        rag_context_section = ""
        try:
            last_human = ""
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    last_human = msg.content
                    break

            if last_human:
                from ingestion.embeddings import embed_text
                query_vector = embed_text(last_human)
                if query_vector:
                    rag_results = self.mining_engine.vector_client.search_similarity(
                        "company_knowledge",
                        query_vector,
                        limit=5
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

        return SYSTEM_PROMPT_TEMPLATE.format(
            phone_number=phone,
            session_id=session,
            interaction_mode=interaction_mode,
            user_profile_section=user_profile_section,
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
                logger.info(f"Transcribed voice attachment: '{transcript}'")
                updated_messages.append(HumanMessage(content=f"[Voice Note Transcript]: {transcript}"))

            elif "image" in mime or uri.endswith(".png") or uri.endswith(".jpg"):
                ocr_text = self.vision_service.run_ocr(raw_bytes, attach.get("name", ""))
                extracted["ocr_text"] = ocr_text
                v_analysis = self.vision_service.analyze_image_objects(raw_bytes, attach.get("name", ""))
                extracted["vision_objects"] = v_analysis
                extracted["image_path"] = attach.get("storage_uri", "")
                logger.info("Executed image analysis and OCR extraction.")

        return {"messages": updated_messages, "extracted_data": extracted}

    def node_agent(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Node: Invoking AI adapter...")

        system_prompt = self._build_system_prompt(state)

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
                import json
                gem_path = os.path.join(os.path.dirname(__file__), "..", "datasets", "precious_stones", "gemstones.json")
                with open(gem_path) as f:
                    gem_data = json.load(f)
                gemstones = gem_data.get("gemstones", {})
                for name, info in list(gemstones.items())[:4]:
                    price = info.get("market_price", {})
                    results.append(f"{name}: ${price.get('per_carat_usd', 'N/A')}/ct - {info.get('description', '')[:100]}")
            except Exception as e:
                logger.warning(f"Gemstone data failed: {e}")
                results.append("Gemstone data unavailable. Contact geology team for current pricing.")

        if any(kw in query.lower() for kw in ["soil", "sample", "exploration", "assay", "drill"]):
            try:
                import json
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
                import asyncio
                from research.market_scraper import get_market_scraper
                scraper = get_market_scraper()
                if scraper:
                    loop = asyncio.new_event_loop()
                    prices = loop.run_until_complete(scraper.get_all_prices())
                    loop.close()
                    if prices:
                        gold = prices.get("gold", {})
                        silver = prices.get("silver", {})
                        results.append(f"Live Market Data:\n"
                                     f"Gold: ${gold.get('price', 'N/A')}/oz ({gold.get('change', 'N/A')})\n"
                                     f"Silver: ${silver.get('price', 'N/A')}/oz ({silver.get('change', 'N/A')})\n"
                                     f"Source: {gold.get('source', 'Market data')}")
                    else:
                        results.append("Market data temporarily unavailable. Using cached prices.")
            except Exception as e:
                logger.warning(f"Market data failed: {e}")
                results.append("Market data unavailable. Check Kitco or Bloomberg for current prices.")

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
            elif "procurement" in query_lower:
                proc = self.finance_engine.submit_procurement_request("system", "Query", 0)
                results.append(f"Procurement System: {proc}")
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
        }

        return routing_map.get(call_name, "end")

    def run(self, session_id: str, phone_number: str, text_message: str, attachments: Optional[List[Dict[str, Any]]] = None, interaction_mode: str = "whatsapp_chat") -> AgentState:
        """
        Triggers the graph execution loop.
        Checks for slash commands first, then falls through to LLM.
        """
        from commands.handler import handle_command, command_service
        from commands.service import CommandState

        session = command_service.get_session(phone_number)

        if text_message.strip().startswith("/") or session.state != CommandState.IDLE:
            try:
                cmd_result = handle_command(
                    phone_number=phone_number,
                    text=text_message,
                    attachments=attachments or []
                )
                if cmd_result and cmd_result.get("type") == "command_response":
                    return AgentState(
                        messages=[AIMessage(content=cmd_result["text"])],
                        session_id=session_id,
                        phone_number=phone_number,
                        attachments=attachments or [],
                        extracted_data={},
                        output_report=None,
                        next_step="",
                        interaction_mode=interaction_mode
                    )
            except Exception as e:
                logger.error(f"Command handling failed: {e}")
                return AgentState(
                    messages=[AIMessage(content="Command error. Type /help for available commands.")],
                    session_id=session_id,
                    phone_number=phone_number,
                    attachments=attachments or [],
                    extracted_data={},
                    output_report=None,
                    next_step="",
                    interaction_mode=interaction_mode
                )

        initial_state = AgentState(
            messages=[HumanMessage(content=text_message)],
            session_id=session_id,
            phone_number=phone_number,
            attachments=attachments or [],
            extracted_data={},
            output_report=None,
            next_step="",
            interaction_mode=interaction_mode
        )

        try:
            return self.workflow.invoke(initial_state, {"recursion_limit": 15})
        except Exception as e:
            logger.error(f"Orchestrator execution failed: {e}", exc_info=True)
            return AgentState(
                messages=[AIMessage(content="I apologize, but I encountered an error processing your request. Please try again or rephrase your question.")],
                session_id=session_id,
                phone_number=phone_number,
                attachments=attachments or [],
                extracted_data={},
                output_report=None,
                next_step="",
                interaction_mode=interaction_mode
            )

    def stream(self, session_id: str, phone_number: str, text_message: str, attachments: Optional[List[Dict[str, Any]]] = None, interaction_mode: str = "whatsapp_chat") -> Iterator[Dict[str, Any]]:
        """
        Stream graph execution yielding state updates as they happen.
        Used for real-time responses via Server-Sent Events (SSE).
        """
        initial_state = AgentState(
            messages=[HumanMessage(content=text_message)],
            session_id=session_id,
            phone_number=phone_number,
            attachments=attachments or [],
            extracted_data={},
            output_report=None,
            next_step="",
            interaction_mode=interaction_mode
        )

        try:
            for event in self.workflow.stream(initial_state, {"recursion_limit": 15}):
                yield event
        except Exception as e:
            logger.error(f"Orchestrator streaming failed: {e}", exc_info=True)
            yield {
                "error": True,
                "messages": [AIMessage(content=f"I apologize, but I encountered an error processing your request. Please try again or rephrase your question. Error: {str(e)[:200]}")]
            }

    async def arun(self, session_id: str, phone_number: str, text_message: str, attachments: Optional[List[Dict[str, Any]]] = None, interaction_mode: str = "whatsapp_chat") -> AgentState:
        """Async wrapper for orchestrator.run() using thread executor."""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.run(session_id, phone_number, text_message, attachments, interaction_mode)
        )
