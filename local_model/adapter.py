import os
import json
import logging
from typing import List, Dict, Any, Optional, Iterator
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

logger = logging.getLogger("ai_os.local_model")

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_url = os.getenv("LOCAL_LLM_URL", self.api_url)
        self.model_name = os.getenv("LOCAL_LLM_MODEL", self.model_name)
        self.api_key = os.getenv("LOCAL_LLM_API_KEY", "")
        self.use_mock = os.getenv("MOCK_LLM", "false").lower() == "true"

        from local_model.gpu_manager import GPUManager
        object.__setattr__(self, "_gpu_manager", GPUManager(
            project=os.getenv("GCP_PROJECT", "gcp-project"),
            zone=os.getenv("GCP_ZONE", "us-central1-a"),
            instance_name=os.getenv("GCP_INSTANCE_NAME", "gpu-vm-instance"),
            idle_timeout_minutes=int(os.getenv("GPU_IDLE_TIMEOUT_MINUTES", "5")),
            health_check_url=self.api_url
        ))

    def _headers(self) -> Dict[str, str]:
        """Auth headers for OpenAI-compatible hosted endpoints."""
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        return {"Content-Type": "application/json"}

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
        self._gpu_manager.start_gpu()
        self._gpu_manager.wait_for_health()
        self._gpu_manager.update_last_request_time()

        # Force mock in test environment or when explicitly configured
        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "true"

        if not self.use_mock and not is_testing:
            try:
                return self._call_real_llm(messages, **kwargs)
            except Exception as e:
                logger.warning(f"Real LLM call failed: {e}. Falling back to mock reasoning.")

        return self._call_mock_llm(messages, **kwargs)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream tokens from the LLM via OpenAI-compatible streaming API."""
        self._gpu_manager.start_gpu()
        self._gpu_manager.wait_for_health()
        self._gpu_manager.update_last_request_time()

        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "true"

        if not self.use_mock and not is_testing:
            try:
                yield from self._stream_real_llm(messages, **kwargs)
                return
            except Exception as e:
                logger.warning(f"Streaming LLM call failed: {e}. Falling back to mock.")

        result = self._call_mock_llm(messages, **kwargs)
        yield ChatGenerationChunk(message=result.generations[0].message)

    def _stream_real_llm(self, messages: List[BaseMessage], **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        """Stream response from LLM using SSE (Server-Sent Events) from OpenAI-compatible API."""
        import httpx

        api_messages = []
        for msg in messages:
            role = msg.type
            if role == "ai":
                role = "assistant"
            elif role == "human":
                role = "user"
            elif role == "system":
                role = "system"
            elif role == "tool":
                role = "tool"

            msg_dict = {"role": role, "content": msg.content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if hasattr(msg, "tool_call_id"):
                msg_dict["tool_call_id"] = msg.tool_call_id
            api_messages.append(msg_dict)

        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": kwargs.get("temperature", 0.1),
            "stream": True
        }

        url = f"{self.api_url.rstrip('/')}/chat/completions"
        logger.info(f"Streaming LLM from {url} with {len(api_messages)} messages")

        accumulated_tool_calls = {}

        with httpx.stream("POST", url, json=payload, headers=self._headers(), timeout=120.0) as response:
            if response.status_code != 200:
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
        import httpx

        api_messages = []
        for msg in messages:
            role = msg.type
            if role == "ai":
                role = "assistant"
            elif role == "human":
                role = "user"
            elif role == "system":
                role = "system"
            elif role == "tool":
                role = "tool"

            msg_dict = {"role": role, "content": msg.content}

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls

            if hasattr(msg, "tool_call_id"):
                msg_dict["tool_call_id"] = msg.tool_call_id

            api_messages.append(msg_dict)

        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": kwargs.get("temperature", 0.1),
            "stream": False
        }

        url = f"{self.api_url.rstrip('/')}/chat/completions"
        logger.info(f"Calling LLM at {url} with {len(api_messages)} messages and {len(TOOL_DEFINITIONS)} tools")

        response = httpx.post(url, json=payload, headers=self._headers(), timeout=120.0)

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

    def _call_mock_llm(self, messages: List[BaseMessage], **kwargs: Any) -> ChatResult:
        """
        Intelligent mock reasoning engine for offline/testing mode.
        Uses keyword detection and conversation state analysis to route tool calls
        and synthesize responses.
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
                elif "report generated" in content_lower or "report generated" in content_lower:
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

        user_lower = user_msg.lower()

        if completed_tools:
            synthesis_parts = tool_outputs
            response_text = "Analysis completed. Here are the results:\n\n" + "\n\n".join(synthesis_parts)
            ai_msg = AIMessage(content=response_text)
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        tool_calls = []
        response_text = ""

        if any(k in user_lower for k in ["drilling", "production", "equipment", "sop", "shaft", "grade", "mining", "conveyor", "ore"]):
            if "mining" not in completed_tools:
                response_text = "Querying the mining database for relevant information."
                tool_calls = [{"name": "query_mining_database", "args": {"query": user_msg}, "id": "call_mining_1"}]
            elif "knowledge" not in completed_tools:
                response_text = "Searching the knowledge base for related standards and procedures."
                tool_calls = [{"name": "search_knowledge_base", "args": {"query": user_msg}, "id": "call_kb_1"}]
            else:
                response_text = "Generating a comprehensive report based on the mining data."
                tool_calls = [{"name": "generate_report", "args": {"title": "Mining Analysis Report", "content": "\n\n".join(tool_outputs), "file_type": "pdf"}, "id": "call_doc_1"}]

        elif any(k in user_lower for k in ["budget", "finance", "payroll", "procurement", "cost", "spend", "variance"]):
            response_text = "Accessing financial database for budget and spending information."
            tool_calls = [{"name": "query_finance_database", "args": {"query": user_msg}, "id": "call_finance_1"}]

        elif any(k in user_lower for k in ["search", "internet", "news", "regulation", "current", "latest", "update"]):
            response_text = "Searching the internet for current information."
            tool_calls = [{"name": "search_internet", "args": {"query": user_msg}, "id": "call_search_1"}]

        elif any(k in user_lower for k in ["ocr", "image", "analyze image", "extract text", "invoice", "photo"]):
            response_text = "Running image analysis and OCR extraction."
            tool_calls = [{"name": "analyze_image", "args": {"image_path": "latest_attachment", "analysis_type": "full_analysis"}, "id": "call_vision_1"}]

        elif any(k in user_lower for k in ["report", "document", "pdf", "generate", "summary", "export"]):
            response_text = "Generating the requested document."
            tool_calls = [{"name": "generate_report", "args": {"title": "Generated Report", "content": f"Report requested: {user_msg}", "file_type": "pdf"}, "id": "call_doc_1"}]

        elif any(k in user_lower for k in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            response_text = "Hello! I am your AI OS Mining Assistant. I can help you with:\n\n- Mining operations data and SOPs\n- Financial reports and budget analysis\n- Equipment status and maintenance\n- Document and report generation\n- Image and document analysis\n- Internet search for current information\n\nHow can I assist you today?"
            ai_msg = AIMessage(content=response_text)
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        else:
            response_text = "Let me search for relevant information and retrieve your context."
            tool_calls = [{"name": "search_knowledge_base", "args": {"query": user_msg}, "id": "call_kb_1"}]

        ai_kwargs = {}
        if tool_calls:
            ai_kwargs["tool_calls"] = [
                {"name": tc["name"], "args": tc["args"], "id": tc["id"], "type": "tool_call"}
                for tc in tool_calls
            ]

        ai_msg = AIMessage(content=response_text, **ai_kwargs)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def extract_user_facts(self, conversation_text: str) -> Dict[str, str]:
        """
        Uses the LLM to extract user-relevant facts from a conversation
        for long-term memory storage.
        """
        if self.use_mock:
            return self._mock_extract_facts(conversation_text)

        import httpx

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
                "stream": False
            }
            url = f"{self.api_url.rstrip('/')}/chat/completions"
            response = httpx.post(url, json=payload, headers=self._headers(), timeout=30.0)
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
