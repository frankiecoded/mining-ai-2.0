import os
import json
import time
import logging
from typing import List, Dict, Any, Optional, Iterator, Tuple
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

logger = logging.getLogger("ai_os.local_model")

# Small-talk / greeting tokens that should get a fast conversational reply
# instead of a heavy knowledge-base lookup.
GREETING_TOKENS = (
    "hello", "hi", "hey", "howdy", "yo", "hiya",
    "good morning", "good afternoon", "good evening",
    "how are you", "how's it going", "how are u", "how r u",
    "what's up", "whats up", "wassup", "sup", "how is it going",
)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_mining_database",
            "description": "Query the mining database for production logs, SOPs (Standard Operating Procedures), equipment status, geological data, grade control results, or safety protocols. Use this for any question about mining operations, drilling, processing, equipment, or geological data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific query about mining operations. Examples: 'drilling report for Shaft 2', 'equipment status of truck TRK-88', 'SOP for flotation circuit', 'production last week'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_finance_database",
            "description": "Query the finance database for budget data, payroll summaries, procurement requests, department spending, or cost analysis. Use this for any financial or budget-related question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific financial query. Examples: 'exploration department budget', 'payroll for June 2026', 'procurement history', 'operations budget variance'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the company knowledge base for regulations, equipment manuals, geological standards, organizational policies, and general mining industry knowledge. Use this for questions about standards, regulations, procedures, equipment specifications, or general industry knowledge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the knowledge base. Examples: 'EPA water discharge regulations', 'CAT 797F specifications', 'copper grade classification', 'MSHA safety requirements'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate a PDF, DOCX, or XLSX report document. Use this when the user asks for a report, document, summary document, or any file output. The report will be saved and a download link provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the report"
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content/text of the report in plain text format"
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["pdf", "docx", "xlsx"],
                        "description": "Output format. Default is pdf."
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_image",
            "description": "Analyze an image using OCR (optical character recognition) or visual analysis. Use this for invoices, documents, conveyor belt images, rock samples, mine maps, or any image analysis request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path or identifier of the image to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["ocr", "object_detection", "full_analysis"],
                        "description": "Type of analysis: 'ocr' for text extraction, 'object_detection' for identifying objects, 'full_analysis' for both."
                    }
                },
                "required": ["image_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Search the internet for real-time information. Use this for current events, latest regulations, market prices, news, or any information not in the local knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for internet search"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_user_memory",
            "description": "Retrieve stored memories and profile information about the current user. Use this to recall the user's name, role, preferences, or past conversation context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "Phone number of the user to look up"
                    }
                },
                "required": ["phone_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_archived_reports",
            "description": "Search historical/archived reports and documents from the company knowledge base. Use this to find past reports, analyses, geological assessments, or historical data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for archived reports. Examples: '2024 geological assessment Shaft 1', 'historical production data', 'past environmental audit'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": "Delegate a task to a specialized mining agent for domain-specific analysis. Available agents: geological_agent (ore grades, drilling, assaying), equipment_agent (equipment monitoring, diagnostics), safety_agent (safety compliance, incident analysis), financial_agent (budgets, costs, AISC), market_agent (commodity prices, market trends), document_agent (report generation), research_agent (regulations, standards).",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_role": {
                        "type": "string",
                        "enum": ["geological_agent", "equipment_agent", "safety_agent", "financial_agent", "market_agent", "document_agent", "research_agent"],
                        "description": "The specialized agent to delegate to"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The specific analysis task for the agent to perform"
                    }
                },
                "required": ["agent_role", "prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_results",
            "description": "Retrieve the results from a previously delegated agent task. Use after delegate_to_agent to get the agent's findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_role": {
                        "type": "string",
                        "enum": ["geological_agent", "equipment_agent", "safety_agent", "financial_agent", "market_agent", "document_agent", "research_agent"],
                        "description": "The agent whose results to retrieve"
                    }
                },
                "required": ["agent_role"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_memory",
            "description": "Store an important finding, lesson, or piece of information in persistent memory for future reference. Use this to remember equipment patterns, operator feedback, safety incidents, project updates, or reference information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["operator", "feedback", "project", "reference", "shift", "equipment"],
                        "description": "Type of memory: operator (user preferences), feedback (corrections), project (active work), reference (external systems), shift (handover context), equipment (equipment learnings)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Short title for this memory"
                    },
                    "content": {
                        "type": "string",
                        "description": "The detailed content to remember"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for easy retrieval"
                    }
                },
                "required": ["memory_type", "title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Recall relevant memories from persistent storage. Use this to check for past findings, equipment history, operator preferences, or project context related to the current query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant memories"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a tracked background task for multi-step analysis. Use this when a query requires investigation across multiple domains or when you need to track progress on a complex analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the task"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what needs to be done"
                    },
                    "task_type": {
                        "type": "string",
                        "enum": ["geological", "equipment", "safety", "financial", "market", "document", "research", "analysis", "coordination"],
                        "description": "Category of the task"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Task priority level"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update progress on an active task. Use this to report step completion, current activity, or progress percentage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to update"
                    },
                    "activity": {
                        "type": "string",
                        "description": "Description of the current activity or progress"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List all active tasks and their current status. Use this to check what analyses are in progress or what needs attention.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_memory",
            "description": "Get the live mine state document for the current session. This tracks active drilling targets, equipment status, safety concerns, geological findings, and recent decisions.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_session_memory",
            "description": "Update a section of the live mine state document. Sections: current_state, active_targets, equipment_status, safety_concerns, geological_findings, active_workflows, recent_decisions, pending_actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["current_state", "active_targets", "equipment_status", "safety_concerns", "geological_findings", "active_workflows", "recent_decisions", "pending_actions"],
                        "description": "Which section to update"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write or append to the section"
                    },
                    "append": {
                        "type": "boolean",
                        "description": "If true, append to existing content. If false, replace.",
                        "default": False
                    }
                },
                "required": ["section", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_plan",
            "description": "Create a structured plan for a complex mining operation. Plans have phases (research, analysis, design, review, approval, execution) and require approval before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Plan title (e.g., 'Blast Pattern Design for Bench 3')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what the plan covers"
                    },
                    "plan_type": {
                        "type": "string",
                        "enum": ["blast_design", "ventilation", "drill_program", "capital_expenditure", "emergency_response", "environmental", "general"],
                        "description": "Type of mining plan"
                    }
                },
                "required": ["title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_plan",
            "description": "Retrieve the current active plan or a specific plan by ID. Shows all steps, their status, and dependencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Plan ID to retrieve. If empty, gets the active plan for this session."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "approve_plan",
            "description": "Approve a plan so it can be executed. Plans require operator approval before any execution steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Plan ID to approve"
                    }
                },
                "required": ["plan_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_todo",
            "description": "Add a task to the shift task list. Use for operational tasks, safety checks, maintenance items, or any action items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Task priority"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["safety", "maintenance", "geological", "financial", "operations", "environmental", "general"],
                        "description": "Task category"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Who is responsible"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_todo",
            "description": "Update a task's status or details. Mark as in_progress, completed, blocked, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "todo_id": {
                        "type": "string",
                        "description": "Task ID to update"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "blocked", "cancelled"],
                        "description": "New status"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes"
                    }
                },
                "required": ["todo_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_todos",
            "description": "List all tasks in the shift task list. Optionally filter by status or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "blocked", "cancelled"],
                        "description": "Filter by status"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_safety_checklist",
            "description": "Generate a standard safety checklist for the current shift. Includes PPE, gas monitoring, equipment inspection, and emergency readiness items.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cost_report",
            "description": "Get the current cost report showing API usage, token consumption, and budget status for this session and shift.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_next_actions",
            "description": "Get proactive suggestions for what to do next based on the current conversation context and mining operation state.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compact_context",
            "description": "Compress the conversation history to free up context space. Useful when the conversation is getting long and you need to maintain focus.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_anomalies",
            "description": "Check for anomalies in production, safety, equipment, and financial data using ML-based pattern detection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to check (e.g., 'production', 'safety', 'equipment', 'all')"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_alerts",
            "description": "Check active alerts and notifications from the alert system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["safety", "production", "equipment", "financial", "all"], "description": "Filter alerts by category"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_document",
            "description": "Analyze a document for insights, compliance, or risk assessment using AI-powered document intelligence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "The document ID to analyze"},
                    "analysis_type": {"type": "string", "enum": ["summary", "extraction", "compliance", "risk_assessment"], "description": "Type of analysis to perform"}
                },
                "required": ["document_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_audit_log",
            "description": "Query the audit trail for system activity, AI decisions, security events, and user actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {"type": "string", "enum": ["recent", "security", "ai_decisions", "user_activity", "statistics"], "description": "Type of audit query"},
                    "user_id": {"type": "string", "description": "Filter by user ID"},
                    "limit": {"type": "integer", "description": "Number of entries to return (default: 20)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report_from_data",
            "description": "Generate a comprehensive report from current mine data using automated report generator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {"type": "string", "enum": ["production", "safety", "financial", "shift", "equipment", "custom"], "description": "Type of report to generate"},
                    "title": {"type": "string", "description": "Custom report title (optional)"}
                },
                "required": ["report_type"]
            }
        }
    }
]


class LocalLLMAdapter(BaseChatModel):
    """
    Adapter for locally-hosted LLM via Ollama/vLLM OpenAI-compatible API.
    Inherits from LangChain's BaseChatModel for seamless LangGraph integration.
    Supports real tool calling via the OpenAI function calling protocol.
    Falls back to intelligent mock reasoning when LLM server is unavailable.
    """
    model_name: str = "llama3.1:8b"
    api_url: str = "http://localhost:11434/v1"
    use_mock: bool = False
    api_key: str = ""
    reasoning_effort: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            from backend.config import settings
            _cfg = settings
        except Exception:
            _cfg = None

        def _env(key: str, default: str = "") -> str:
            val = os.getenv(key)
            if val is not None:
                return val
            if _cfg is not None:
                return str(getattr(_cfg, key, "") or "")
            return default

        self.api_url = _env("LOCAL_LLM_URL", self.api_url)
        self.model_name = _env("LOCAL_LLM_MODEL", self.model_name)
        self.api_key = _env("LOCAL_LLM_API_KEY", "")
        self.reasoning_effort = _env("REASONING_EFFORT", "")
        self.use_mock = (_env("MOCK_LLM", "false") or "false").lower() == "true"
        # Health-check once per process; the server state doesn't change between
        # rapid requests, so skipping this removes ~0.5-1s of overhead per turn.
        object.__setattr__(self, "_health_verified", False)

        import httpx
        _limits = httpx.Limits(max_connections=5, max_keepalive_connections=5)
        object.__setattr__(self, "_http_client", httpx.Client(timeout=120.0, limits=_limits))

        from local_model.gpu_manager import GPUManager
        object.__setattr__(self, "_gpu_manager", GPUManager(
            project=os.getenv("GCP_PROJECT", "gcp-project"),
            zone=os.getenv("GCP_ZONE", "us-central1-a"),
            instance_name=os.getenv("GCP_INSTANCE_NAME", "gpu-vm-instance"),
            idle_timeout_minutes=int(os.getenv("GPU_IDLE_TIMEOUT_MINUTES", "5")),
            health_check_url=self.api_url
        ))

    def _ensure_server(self):
        """Start/verify the LLM server once per process, then just stamp time."""
        if not self._health_verified:
            self._gpu_manager.start_gpu()
            self._gpu_manager.wait_for_health()
            object.__setattr__(self, "_health_verified", True)
        self._gpu_manager.update_last_request_time()

    def _headers(self) -> Dict[str, str]:
        """Auth headers for OpenAI-compatible hosted endpoints."""
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        return {"Content-Type": "application/json"}

    def _payload_extras(self) -> Dict[str, Any]:
        """Extra optional payload params (e.g. reasoning_effort for hosted reasoning models)."""
        extras: Dict[str, Any] = {}
        if getattr(self, "reasoning_effort", ""):
            extras["reasoning_effort"] = self.reasoning_effort
        return extras

    def _keep_alive(self) -> Dict[str, Any]:
        """keep_alive is Ollama-only; hosted endpoints reject it."""
        host = self.api_url.split("://")[-1].split("/")[0]
        if host.startswith("localhost") or host.startswith("127.0.0.1") or host.startswith("0.0.0.0"):
            return {"keep_alive": "30m"}
        return {}

    def _serialize_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Convert LangChain-style tool calls to the OpenAI-compatible wire format.

        LangChain tool calls are dicts like {"name", "args", "id", "type"}.
        OpenAI/Ollama expects: {"id", "type": "function", "function": {"name", "arguments" (string)}}.
        """
        serialized = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            if isinstance(args, dict):
                args_str = json.dumps(args)
            else:
                args_str = str(args)
            serialized.append({
                "id": tc.get("id") or f"call_{name}",
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            })
        return serialized

    def _message_to_api_dict(self, msg: BaseMessage) -> Dict[str, Any]:
        """Serialize a LangChain message to an OpenAI-compatible message dict."""
        role = msg.type
        if role == "ai":
            role = "assistant"
        elif role == "human":
            role = "user"
        elif role == "tool":
            role = "tool"

        msg_dict: Dict[str, Any] = {"role": role}

        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            msg_dict["content"] = None
            msg_dict["tool_calls"] = self._serialize_tool_calls(tool_calls)
        else:
            msg_dict["content"] = msg.content

        tool_call_id = getattr(msg, "tool_call_id", None)
        if tool_call_id:
            msg_dict["tool_call_id"] = tool_call_id

        return msg_dict

    @property
    def _llm_type(self) -> str:
        return "ollama_local_llm"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._ensure_server()

        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "true"

        if not self.use_mock and not is_testing:
            backoffs = [0.5, 1.0, 2.0]
            last_exc = None
            for attempt, delay in enumerate(backoffs):
                try:
                    return self._call_real_llm(messages, **kwargs)
                except Exception as e:
                    last_exc = e
                    logger.warning(
                        f"LLM call attempt {attempt + 1}/{len(backoffs)} failed: {e}. "
                        + (f"Retrying in {delay}s..." if attempt < len(backoffs) - 1 else "All retries exhausted.")
                    )
                    if attempt < len(backoffs) - 1:
                        time.sleep(delay)
            logger.warning(f"Falling back to mock reasoning after {len(backoffs)} failed attempts: {last_exc}")

        return self._call_mock_llm(messages, **kwargs)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream tokens from the LLM via OpenAI-compatible streaming API."""
        self._ensure_server()

        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "true"

        if not self.use_mock and not is_testing:
            backoffs = [0.5, 1.0, 2.0]
            for attempt, delay in enumerate(backoffs):
                try:
                    yield from self._stream_real_llm(messages, **kwargs)
                    return
                except Exception as e:
                    logger.warning(
                        f"Streaming attempt {attempt + 1}/{len(backoffs)} failed: {e}. "
                        + (f"Retrying in {delay}s..." if attempt < len(backoffs) - 1 else "All retries exhausted.")
                    )
                    if attempt < len(backoffs) - 1:
                        time.sleep(delay)
            logger.warning(f"All streaming attempts failed, falling back to mock.")

        yield from self._stream_mock_tokens(messages, **kwargs)

    def _manage_context_window(self, messages: List[BaseMessage], max_tokens: int = 6000) -> List[BaseMessage]:
        """
        Truncate conversation history to fit within context window.
        Always keeps: system message (first), last user message, last 3 exchanges.
        Summarizes older messages to preserve context.
        """
        if not messages:
            return messages

        # Estimate token count (rough: 1 token ≈ 4 chars)
        def estimate_tokens(msgs):
            return sum(len(str(m.content)) // 4 for m in msgs)

        total = estimate_tokens(messages)
        if total <= max_tokens:
            return messages

        # Always keep system message (index 0)
        system_msg = [messages[0]] if messages[0].type == "system" else []
        non_system = [m for m in messages if m.type != "system"]

        if len(non_system) <= 4:
            return messages  # Too few to truncate

        # Keep last 6 messages (3 exchanges)
        recent = non_system[-6:]
        old = non_system[:-6]

        # Summarize old messages into a single context message
        old_summary_parts = []
        for msg in old:
            role = "User" if msg.type == "human" else "Assistant" if msg.type == "ai" else msg.type
            content = str(msg.content)[:200]  # Truncate each old message
            old_summary_parts.append(f"{role}: {content}")

        summary = "[Earlier conversation summary]\n" + "\n".join(old_summary_parts)
        summary_msg = SystemMessage(content=summary)

        result = system_msg + [summary_msg] + recent
        logger.info(f"Context window managed: {len(messages)} -> {len(result)} messages (saved ~{total - estimate_tokens(result)} tokens)")
        return result

    def _stream_real_llm(self, messages: List[BaseMessage], **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        """Stream response from LLM using SSE (Server-Sent Events) from OpenAI-compatible API."""

        # Manage context window before sending
        messages = self._manage_context_window(messages)
        api_messages = [self._message_to_api_dict(msg) for msg in messages]

        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": kwargs.get("temperature", 0.1),
            "stream": True,
            **self._payload_extras(),
            **self._keep_alive()
        }

        url = f"{self.api_url.rstrip('/')}/chat/completions"
        logger.info(f"Streaming LLM from {url} with {len(api_messages)} messages")

        accumulated_tool_calls = {}

        with self._http_client.stream("POST", url, json=payload, headers=self._headers()) as response:
            if response.status_code != 200:
                body = response.read().decode("utf-8", errors="replace")[:800]
                logger.warning(
                    f"LLM streaming API returned {response.status_code}. Body={body}. Payload={json.dumps(payload)[:2000]}"
                )
                raise Exception(f"LLM streaming API returned {response.status_code}")

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                delta = chunk.get("choices", [{}])[0].get("delta", {})

                content = delta.get("content", "")
                if content:
                    yield ChatGenerationChunk(message=AIMessageChunk(content=content))

                tool_calls = delta.get("tool_calls", [])
                for tc in tool_calls:
                    tc_idx = tc.get("index", 0)
                    if tc_idx not in accumulated_tool_calls:
                        accumulated_tool_calls[tc_idx] = {
                            "id": tc.get("id", ""),
                            "name": "",
                            "args": ""
                        }
                    if "id" in tc and tc["id"]:
                        accumulated_tool_calls[tc_idx]["id"] = tc["id"]
                    func = tc.get("function", {})
                    if "name" in func:
                        accumulated_tool_calls[tc_idx]["name"] = func["name"]
                    if "arguments" in func:
                        accumulated_tool_calls[tc_idx]["args"] += func["arguments"]

        if accumulated_tool_calls:
            parsed_tool_calls = []
            for idx in sorted(accumulated_tool_calls.keys()):
                tc = accumulated_tool_calls[idx]
                try:
                    args = json.loads(tc["args"]) if tc["args"] else {}
                except json.JSONDecodeError:
                    args = {"query": tc["args"]}
                parsed_tool_calls.append({
                    "name": tc["name"],
                    "args": args,
                    "id": tc["id"] or f"call_{tc['name']}_{idx}",
                    "type": "tool_call"
                })

            ai_chunk = AIMessageChunk(
                content="",
                tool_calls=parsed_tool_calls
            )
            yield ChatGenerationChunk(message=ai_chunk)

    def _call_real_llm(self, messages: List[BaseMessage], **kwargs: Any) -> ChatResult:
        """
        Calls the real LLM via OpenAI-compatible API with tool definitions.
        Parses tool_calls from the response and returns structured AIMessage.
        """

        # Manage context window before sending
        messages = self._manage_context_window(messages)
        api_messages = [self._message_to_api_dict(msg) for msg in messages]

        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": kwargs.get("temperature", 0.1),
            "stream": False,
            **self._payload_extras(),
            **self._keep_alive()
        }

        url = f"{self.api_url.rstrip('/')}/chat/completions"
        logger.info(f"Calling LLM at {url} with {len(api_messages)} messages and {len(TOOL_DEFINITIONS)} tools")

        response = self._http_client.post(url, json=payload, headers=self._headers())

        if response.status_code != 200:
            raise Exception(f"LLM API returned status {response.status_code}: {response.text[:200]}")

        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]

        content = message.get("content", "") or ""
        raw_tool_calls = message.get("tool_calls", [])

        parsed_tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args_str = func.get("arguments", "{}")

            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {"query": args_str}

            parsed_tool_calls.append({
                "name": name,
                "args": args,
                "id": tc.get("id", f"call_{name}_{len(parsed_tool_calls)}"),
                "type": "tool_call"
            })

        ai_kwargs = {}
        if parsed_tool_calls:
            ai_kwargs["tool_calls"] = parsed_tool_calls

        ai_msg = AIMessage(content=content, **ai_kwargs)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def _mock_response(self, messages: List[BaseMessage]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Decides a mock reply (text + optional tool calls).

        Conversational messages (greetings, small talk, short/casual text) get a
        direct, natural reply. Domain queries still route to tools. This keeps the
        assistant chatty and fast without dragging casual conversation into tools.
        """
        completed_tools = set()
        tool_outputs = []
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                break
            if isinstance(msg, ToolMessage):
                content = msg.content
                content_lower = content.lower()
                if "mining" in content_lower or "sop" in content_lower or "production" in content_lower:
                    completed_tools.add("mining")
                elif "verified" in content_lower or "based on" in content_lower or "internet source" in content_lower:
                    completed_tools.add("research")
                elif "report generated" in content_lower:
                    completed_tools.add("document")
                elif "ocr" in content_lower or "image" in content_lower:
                    completed_tools.add("vision")
                elif "memory" in content_lower or "profile" in content_lower:
                    completed_tools.add("memory")
                elif "financial" in content_lower or "budget" in content_lower or "payroll" in content_lower or "ledger" in content_lower:
                    completed_tools.add("finance")
                elif "archived" in content_lower or "archive" in content_lower:
                    completed_tools.add("archive")
                tool_outputs.append(content)

        user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        user_lower = user_msg.lower().strip()
        words = [w for w in user_lower.replace("?", "").split() if w]

        # Tool outputs are ready — synthesize a concise answer from them.
        if completed_tools:
            response_text = "\n\n".join(tool_outputs)
            if not response_text:
                response_text = "I don't have the data you're looking for yet. Could you be more specific?"
            return response_text, []

        # --- Fast conversational path (no tools) ---
        is_greeting = any(tok in user_lower for tok in GREETING_TOKENS)
        casual = len(words) <= 4

        if is_greeting:
            return (
                "Hello! I'm your AI Operating System. I can help with your mining operations, "
                "market prices, geology, financials, or just have a conversation. What would you like to know?"
            ), []

        if casual and not any(
            k in user_lower for k in ["price", "gold", "silver", "market", "budget", "task",
                                      "production", "report", "mining", "equipment", "grade"]
        ):
            return (
                "Got it. Ask me anything — about your operations, current markets, geology, "
                "budgets, or just talk. I'll answer precisely and won't guess."
            ), []

        # --- Domain tool routing ---
        if any(k in user_lower for k in ["drilling", "production", "equipment", "sop", "shaft", "grade", "mining", "conveyor", "ore"]):
            return "Let me pull the relevant data from your operations database.", [
                {"name": "query_mining_database", "args": {"query": user_msg}, "id": "call_mining_1", "type": "tool_call"}
            ]

        if any(k in user_lower for k in ["budget", "finance", "payroll", "procurement", "cost", "spend", "variance"]):
            return "Checking your financial records now.", [
                {"name": "query_finance_database", "args": {"query": user_msg}, "id": "call_finance_1", "type": "tool_call"}
            ]

        if any(k in user_lower for k in ["search", "internet", "news", "regulation", "current", "latest", "update"]):
            return "Searching for the latest information.", [
                {"name": "search_internet", "args": {"query": user_msg}, "id": "call_search_1", "type": "tool_call"}
            ]

        if any(k in user_lower for k in ["ocr", "image", "analyze image", "extract text", "invoice", "photo"]):
            return "Running image analysis and OCR extraction.", [
                {"name": "analyze_image", "args": {"image_path": "latest_attachment", "analysis_type": "full_analysis"}, "id": "call_vision_1", "type": "tool_call"}
            ]

        if any(k in user_lower for k in ["report", "document", "pdf", "generate", "summary", "export"]):
            return "Generating the requested document.", [
                {"name": "generate_report", "args": {"title": "Generated Report", "content": f"Report requested: {user_msg}", "file_type": "pdf"}, "id": "call_doc_1", "type": "tool_call"}
            ]

        if any(k in user_lower for k in ["price", "gold", "silver", "market"]):
            return "Fetching live market data.", [
                {"name": "search_internet", "args": {"query": user_msg}, "id": "call_market_1", "type": "tool_call"}
            ]

        # Generic fallback — stay conversational, no assumptions, no forced tools.
        return (
            "I can help with that. Could you give me a bit more detail so I give you an accurate answer "
            "rather than guessing?"
        ), []

    def _call_mock_llm(self, messages: List[BaseMessage], **kwargs: Any) -> ChatResult:
        """
        Intelligent mock reasoning engine for offline/testing mode.
        """
        response_text, tool_calls = self._mock_response(messages)

        ai_kwargs = {}
        if tool_calls:
            ai_kwargs["tool_calls"] = tool_calls

        ai_msg = AIMessage(content=response_text, **ai_kwargs)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def _stream_mock_tokens(self, messages: List[BaseMessage], **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        """Streams the mock reply token-by-token so the UI stays responsive."""
        response_text, tool_calls = self._mock_response(messages)

        words = response_text.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield ChatGenerationChunk(message=AIMessageChunk(content=token))
            time.sleep(0.008)  # tiny pacing so streaming feels live without lag

        if tool_calls:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="", tool_calls=tool_calls)
            )

    def extract_user_facts(self, conversation_text: str) -> Dict[str, str]:
        """
        Uses the LLM to extract user-relevant facts from a conversation
        for long-term memory storage.
        """
        if self.use_mock:
            return self._mock_extract_facts(conversation_text)

        extraction_prompt = [
            {"role": "system", "content": (
                "Extract key facts about the user from this conversation. "
                "Return ONLY a JSON object with key-value pairs of facts to remember. "
                "Examples: {\"name\": \"John\", \"role\": \"geologist\", \"preference\": \"prefers PDF reports\"}. "
                "Return {} if no user-specific facts found."
            )},
            {"role": "user", "content": conversation_text}
        ]

        try:
            payload = {
                "model": self.model_name,
                "messages": extraction_prompt,
                "temperature": 0.0,
                "stream": False,
                **self._payload_extras(),
                **self._keep_alive()
            }
            url = f"{self.api_url.rstrip('/')}/chat/completions"
            response = self._http_client.post(url, json=payload, headers=self._headers(), timeout=30.0)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # Try to parse JSON from the response
                import re
                json_match = re.search(r'\{[^}]*\}', content)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")

        return self._mock_extract_facts(conversation_text)

    def _mock_extract_facts(self, text: str) -> Dict[str, str]:
        """Simple keyword-based fact extraction for mock mode."""
        facts = {}
        text_lower = text.lower()

        if "my name is" in text_lower:
            idx = text_lower.index("my name is") + 11
            name = text[idx:].split()[0].strip(".,!?")
            facts["name"] = name

        if "i am a" in text_lower or "i'm a" in text_lower:
            for prefix in ["i am a ", "i'm a "]:
                if prefix in text_lower:
                    idx = text_lower.index(prefix) + len(prefix)
                    role = text[idx:].split(".")[0].split(",")[0].strip()
                    facts["role"] = role
                    break

        if "i work in" in text_lower or "i work at" in text_lower:
            for prefix in ["i work in ", "i work at "]:
                if prefix in text_lower:
                    idx = text_lower.index(prefix) + len(prefix)
                    dept = text[idx:].split(".")[0].split(",")[0].strip()
                    facts["department"] = dept
                    break

        return facts
