import os
import uuid
import time
import hmac
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from backend.config import settings
from backend.file_reader import extract_text
from database.postgres_client import PostgresClient
from vector_db.qdrant_client import VectorDBClient

from local_model.adapter import LocalLLMAdapter
from research.service import ResearchService
from document_service.service import DocumentService
from vision_service.service import VisionService
from voice_service.service import VoiceService
from mining_engine.service import MiningEngineService
from finance_engine.service import FinanceEngineService
from memory_engine.service import MemoryEngineService
from scheduler.cron_jobs import OperatingSystemScheduler
from orchestrator.graph import AIOrchestrator

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ai_os.api_gateway")

# ---------- Rate Limiter (Thread-Safe) ----------
class RateLimiter:
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        async with self._lock:
            now = time.time()
            self._requests[key] = [t for t in self._requests[key] if now - t < window_seconds]
            if len(self._requests[key]) >= limit:
                return False
            self._requests[key].append(now)
            return True

rate_limiter = RateLimiter()

async def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not await rate_limiter.is_allowed(client_ip, settings.RATE_LIMIT_PER_MINUTE):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

# ---------- Auth (Timing-Safe) ----------
def verify_api_key(request: Request):
    """Verify API key using timing-safe comparison. Skipped in dev when unconfigured."""
    if not settings.API_KEY:
        if settings.is_production:
            raise HTTPException(status_code=503, detail="API key not configured")
        return

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.headers.get("X-API-Key", "")

    if not token or not hmac.compare_digest(token, settings.API_KEY):
        logger.warning(f"Failed auth attempt from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ---------- Initialize Infrastructure (All Local) ----------
# Database: uses SQLite locally (auto-fallback in PostgresClient)
postgres_client = PostgresClient(dsn="")

# Vector DB: local Qdrant or in-memory fallback
vector_client = VectorDBClient(host="localhost", port=6333, url="", api_key="")

# LLM: your local Ollama or any OpenAI-compatible server
llm = LocalLLMAdapter(model_name=settings.LOCAL_LLM_MODEL, api_url=settings.LOCAL_LLM_URL)
research_service = ResearchService(serper_api_key=settings.SERPER_API_KEY)
doc_service = DocumentService(minio_client=None)
vision_service = VisionService()
voice_service = VoiceService()
mining_engine = MiningEngineService(postgres_client=postgres_client, vector_client=vector_client)
finance_engine = FinanceEngineService(postgres_client=postgres_client)
memory_engine = MemoryEngineService(postgres_client=postgres_client, vector_client=vector_client)

scheduler = OperatingSystemScheduler(mining_service=mining_engine, finance_service=finance_engine, gpu_manager=llm._gpu_manager)

orchestrator = AIOrchestrator(
    llm=llm,
    research_service=research_service,
    doc_service=doc_service,
    vision_service=vision_service,
    voice_service=voice_service,
    mining_engine=mining_engine,
    finance_engine=finance_engine,
    memory_engine=memory_engine
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production:
        settings.validate_production_config()
    scheduler.start()
    try:
        from ingestion.loader import run_full_ingestion
        indexed = run_full_ingestion(vector_client)
        logger.info(f"Dataset ingestion complete. {indexed} documents indexed.")
    except Exception as e:
        logger.warning(f"Dataset ingestion skipped: {e}")
    yield
    scheduler.shutdown()

app = FastAPI(
    title="AI Mining Operating System",
    description="Web-based AI assistant for gold mining, precious stones, rare earths, and financial intelligence.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Security Headers Middleware ----------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ---------- Request Size Limit Middleware ----------
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(status_code=413, content={"detail": "Request too large"})
    return await call_next(request)

# ---------- Pydantic Models ----------
class TaskRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    assignee: Optional[str] = Field(None, max_length=100)

class ProcurementRequest(BaseModel):
    item: str = Field(..., min_length=1, max_length=500)
    cost: float = Field(..., gt=0, le=10000000)

class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    num_results: int = Field(default=5, ge=1, le=20)

class ChatStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str = Field(default="anonymous", max_length=100)
    interaction_mode: str = Field(default="web_chat", pattern=r"^(web_chat|voice_note)$")
    attachment_id: str = Field(default="", max_length=300, description="File id from a prior /api/documents/upload")


def _uploads_dir() -> Path:
    base = Path(settings.UPLOAD_DIR)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent / base
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_uploaded_file(file_id: str) -> Optional[Dict[str, Any]]:
    """Find a previously uploaded file and return its metadata + extracted text."""
    if not file_id:
        return None
    for path in _uploads_dir().iterdir():
        if path.name.startswith(file_id + "_"):
            name = path.name[len(file_id) + 1:]
            try:
                text = extract_text(name, path.read_bytes())
            except Exception:
                logger.warning(f"Failed to re-extract text from {path.name}")
                text = ""
            mime = "text/plain"
            low = name.lower()
            if low.endswith(".pdf"):
                mime = "application/pdf"
            elif low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                mime = "image/" + low.rsplit(".", 1)[-1]
            return {"file_id": file_id, "name": name, "mime_type": mime, "storage_uri": str(path), "text": text}
    return None

# ---------- Helpers ----------
def _sanitize_error(e: Exception) -> str:
    """Return a safe error message that doesn't leak internals."""
    safe_errors = {
        ValueError: "Invalid request parameters",
        KeyError: "Missing required data",
        TimeoutError: "Request timed out",
        ConnectionError: "Service temporarily unavailable",
    }
    for exc_type, msg in safe_errors.items():
        if isinstance(e, exc_type):
            return msg
    return "An internal error occurred. Please try again."

# ---------- Routes ----------
@app.get("/", tags=["Diagnostic"])
def get_system_status():
    return {
        "status": "online",
        "system": "AI Mining Operating System v2.0.0",
        "version": "2.0.0"
    }

@app.get("/health", tags=["Diagnostic"])
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/files/{file_path:path}", tags=["Media"], dependencies=[Depends(verify_api_key)])
def get_stored_file(file_path: str):
    local_dir = settings.storage_dir
    full_path = os.path.realpath(os.path.join(local_dir, file_path))
    if not full_path.startswith(os.path.realpath(local_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)

# ---------- Tasks & Procurement ----------
@app.post("/tasks", tags=["Management"], dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
def create_task(req: TaskRequest):
    task_id = postgres_client.create_task(req.description, req.assignee)
    return {"status": "success", "task_id": task_id}

@app.get("/tasks", tags=["Management"], dependencies=[Depends(verify_api_key)])
def list_tasks():
    return {"tasks": postgres_client.list_tasks()}

@app.post("/procurement", tags=["Management"], dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
def create_procurement(req: ProcurementRequest):
    return finance_engine.submit_procurement_request("authenticated_user", req.item, req.cost)

# ---------- Streaming Chat ----------
@app.post("/api/chat/stream", tags=["Streaming"], dependencies=[Depends(check_rate_limit)])
async def stream_chat(req: ChatStreamRequest):
    """Server-Sent Events (SSE) streaming endpoint for real-time LLM responses."""
    session_id = req.session_id

    def event_generator():
        import json
        from langchain_core.messages import HumanMessage, AIMessage

        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"

        assistant_content = ""
        tool_calls = []
        try:
            # Load prior history (excluding the message being sent right now).
            raw_history = postgres_client.get_conversation(session_id) or []
            history = []
            for msg_data in raw_history:
                if msg_data.get("role") == "user":
                    history.append(HumanMessage(content=msg_data.get("content", "")))
                elif msg_data.get("role") == "assistant":
                    history.append(AIMessage(content=msg_data.get("content", "")))

            # Persist the user message immediately so it's never lost, even if
            # the reply fails or the client disconnects mid-stream.
            postgres_client.save_user_message(session_id, req.session_id, req.message)

            # Load any uploaded file so the agent can read it during the turn.
            attachments = []
            if req.attachment_id:
                file_info = load_uploaded_file(req.attachment_id)
                if file_info:
                    attachments.append(file_info)
                    logger.info(f"Chat attachment loaded: {file_info['name']} ({len(file_info.get('text', ''))} chars)")

            # Stream tokens from the LLM (fast first token, ChatGPT-like).
            for ev in orchestrator.stream_conversation(
                session_id=session_id,
                phone_number=req.session_id,
                text_message=req.message,
                interaction_mode=req.interaction_mode,
                history=history,
                attachments=attachments,
            ):
                if ev["type"] == "content":
                    assistant_content += ev["content"]
                    yield f"data: {json.dumps({'type': 'message', 'content': ev['content']})}\n\n"
                elif ev["type"] == "tool_call":
                    tool_calls.append({"name": ev["name"], "args": ev["args"]})
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': ev['name'], 'args': ev['args']})}\n\n"
                # 'done' events carry no payload; the assistant text already streamed.

            # Persist the assistant reply so the session can be resumed later.
            if assistant_content:
                postgres_client.append_conversation(
                    session_id,
                    req.session_id,
                    [{"role": "assistant", "content": assistant_content}],
                )

            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {_sanitize_error(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

# ---------- Web Research ----------
@app.post("/api/research/search", tags=["Research"], dependencies=[Depends(verify_api_key)])
async def web_search(req: WebSearchRequest):
    loop = asyncio.get_event_loop()
    sources = await loop.run_in_executor(None, lambda: research_service.search(req.query))
    result = await loop.run_in_executor(None, lambda: research_service.rank_and_verify(sources, req.query))
    return result

@app.get("/api/research/market-prices", tags=["Research"], dependencies=[Depends(verify_api_key)])
async def get_market_prices():
    try:
        from research.market_scraper import get_market_scraper
        scraper = get_market_scraper()
        if scraper:
            prices = await scraper.get_all_prices()
            summary = await scraper.get_market_summary()
            return {"prices": prices, "summary": summary}
    except Exception as e:
        logger.error(f"Market scraper error: {_sanitize_error(e)}")
    return {"prices": {}, "summary": "Market data temporarily unavailable"}

@app.get("/api/research/gold-price", tags=["Research"], dependencies=[Depends(verify_api_key)])
async def get_gold_price():
    try:
        from research.market_scraper import get_market_scraper
        scraper = get_market_scraper()
        if scraper:
            prices = await scraper.get_all_prices()
            return {"gold": prices.get("gold", {}), "silver": prices.get("silver", {})}
    except Exception as e:
        logger.error(f"Gold price error: {_sanitize_error(e)}")
    return {"gold": {}, "silver": {}}

# ---------- UI Integration Routes ----------
@app.get("/api/chat/sessions", tags=["UI Integration"], dependencies=[Depends(verify_api_key)])
def get_chat_sessions():
    sessions = postgres_client.get_chat_sessions(limit=50)
    return {"sessions": sessions}

@app.get("/api/chat/history/{session_id}", tags=["UI Integration"], dependencies=[Depends(verify_api_key)])
def get_chat_history(session_id: str):
    messages = postgres_client.get_conversation(session_id) or []
    for i, msg in enumerate(messages):
        msg.setdefault("id", f"{session_id}_{i}")
    return {"messages": messages}

@app.get("/api/system/telemetry", tags=["UI Integration"], dependencies=[Depends(verify_api_key)])
def get_telemetry():
    cpu_percent = 45.2
    mem_usage = 16.4
    if HAS_PSUTIL:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        mem_usage = round(mem.used / (1024**3), 1)

    return {
        "cpu_percent": cpu_percent,
        "memory_gb": mem_usage,
        "vector_latency_ms": 12,
        "network_gbps": 1.2,
        "active_tasks": len(postgres_client.list_tasks()),
        "llm_model": settings.LOCAL_LLM_MODEL,
        "llm_status": "Online",
        "memory_core_status": "Online"
    }

@app.post("/api/documents/upload", tags=["Knowledge Base"], dependencies=[Depends(verify_api_key)])
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "upload.bin"
    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        file_id = uuid.uuid4().hex[:16]
        content = extract_text(filename, raw)

        # Save raw file to disk so the chat attachment path can re-read it later.
        save_path = _uploads_dir() / f"{file_id}_{filename}"
        save_path.write_bytes(raw)
        logger.info(f"Uploaded file saved: {save_path.name} ({len(raw)} bytes)")

        # Index into vector DB (chunked for KB retrieval).
        chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
        docs_to_index = []
        import hashlib
        for idx, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{filename}_{idx}".encode()).hexdigest()
            docs_to_index.append({
                "id": doc_id,
                "text": chunk,
                "payload": {"source": "knowledge_base", "filename": filename, "chunk_index": idx}
            })

        from ingestion.loader import index_documents_to_vector_db
        count = index_documents_to_vector_db(vector_client, docs_to_index, collection_name="company_knowledge")

        return {
            "status": "success",
            "filename": filename,
            "file_id": file_id,
            "mime": file.content_type or "application/octet-stream",
            "chars": len(content),
            "text_preview": content[:2000],
            "chunks_indexed": count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing uploaded document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MemoryStoreRequest(BaseModel):
    memory_type: str = Field(..., description="operator, feedback, project, reference, shift, equipment")
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    tags: List[str] = Field(default_factory=list)

class MemoryRecallRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)

class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    task_type: str = Field(default="analysis")
    priority: str = Field(default="medium")

class TaskUpdateRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    activity: str = Field(default="")


@app.get("/api/tasks", tags=["Task Management"])
async def list_tasks(current_user=Depends(verify_api_key)):
    try:
        from task_manager.manager import TaskManager
        tm = TaskManager()
        tasks = tm.active_tasks()
        summary = tm.task_summary()
        return {
            "status": "success",
            "tasks": [t.model_dump() for t in tasks],
            "summary": summary
        }
    except Exception as e:
        logger.error(f"List tasks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks", tags=["Task Management"])
async def create_task(req: TaskCreateRequest, current_user=Depends(verify_api_key)):
    try:
        from task_manager.manager import TaskManager, TaskType, TaskPriority
        tm = TaskManager()
        try:
            ttype = TaskType(req.task_type)
        except ValueError:
            ttype = TaskType.ANALYSIS
        try:
            priority = TaskPriority(req.priority)
        except ValueError:
            priority = TaskPriority.MEDIUM
        task = tm.create_task(req.title, req.description, ttype, priority)
        tm.start_task(task.id)
        return {"status": "success", "task": task.model_dump()}
    except Exception as e:
        logger.error(f"Create task failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/update", tags=["Task Management"])
async def update_task(req: TaskUpdateRequest, current_user=Depends(verify_api_key)):
    try:
        from task_manager.manager import TaskManager
        tm = TaskManager()
        task = tm.update_progress(req.task_id, activity=req.activity)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "task": task.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update task failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memory", tags=["Memory System"])
async def get_memory_stats(current_user=Depends(verify_api_key)):
    try:
        from memory_engine.persistent import MemoryEngine
        mem = MemoryEngine()
        stats = mem.get_memory_stats()
        return {"status": "success", "stats": stats}
    except Exception as e:
        logger.error(f"Memory stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/memory/store", tags=["Memory System"])
async def store_memory(req: MemoryStoreRequest, current_user=Depends(verify_api_key)):
    try:
        from memory_engine.persistent import MemoryEngine
        from memory_engine.types import MemoryType
        mem = MemoryEngine()
        try:
            mtype = MemoryType(req.memory_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid memory_type: {req.memory_type}")
        entry = mem.store(mtype, req.title, req.content, req.tags)
        return {"status": "success", "entry": entry.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store memory failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/memory/recall", tags=["Memory System"])
async def recall_memory(req: MemoryRecallRequest, current_user=Depends(verify_api_key)):
    try:
        from memory_engine.persistent import MemoryEngine
        mem = MemoryEngine()
        entries = mem.recall(req.query, limit=req.limit)
        return {
            "status": "success",
            "entries": [e.model_dump() for e in entries],
            "count": len(entries)
        }
    except Exception as e:
        logger.error(f"Recall memory failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memory/index", tags=["Memory System"])
async def memory_index(current_user=Depends(verify_api_key)):
    try:
        from memory_engine.persistent import MemoryEngine
        mem = MemoryEngine()
        index = mem.build_memory_index()
        return {"status": "success", "index": index}
    except Exception as e:
        logger.error(f"Memory index failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/coordinator/agents", tags=["Coordinator"])
async def list_agents(current_user=Depends(verify_api_key)):
    from coordinator.mining_coordinator import MINING_AGENTS
    agents = []
    for role, definition in MINING_AGENTS.items():
        agents.append({
            "role": role,
            "name": definition.name,
            "description": definition.description,
            "tools": definition.tools,
            "priority": definition.priority
        })
    return {"status": "success", "agents": agents}


# Session Memory endpoints
@app.get("/api/session/memory", tags=["Session Memory"])
async def get_session_memory(
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from session_memory.manager import SessionMemoryManager
    sm = SessionMemoryManager()
    section = sm.build_prompt_section(session_id)
    return {"status": "success", "session_id": session_id, "section": section or "No session memory yet."}


@app.post("/api/session/memory/update", tags=["Session Memory"])
async def update_session_memory(
    request: Request,
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from session_memory.manager import SessionMemoryManager
    body = await request.json()
    sm = SessionMemoryManager()
    sm.update_section(
        session_id=session_id,
        section_name=body.get("section", "current_state"),
        content=body.get("content", ""),
        append=body.get("append", False)
    )
    return {"status": "success", "message": "Session memory updated"}


# Plan endpoints
@app.post("/api/plans", tags=["Planning"])
async def create_plan_endpoint(
    request: Request,
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from services.plan_mode import PlanMode
    body = await request.json()
    pm = PlanMode()
    plan = pm.create_plan(
        session_id=session_id,
        title=body.get("title", ""),
        description=body.get("description", ""),
        plan_type=body.get("plan_type", "general")
    )
    return {"status": "success", "plan": plan}


@app.get("/api/plans", tags=["Planning"])
async def get_plan_endpoint(
    plan_id: str = "",
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from services.plan_mode import PlanMode
    pm = PlanMode()
    if plan_id:
        plan = pm.get_plan(plan_id)
    else:
        plan = pm.get_active_plan_for_session(session_id)
    if plan:
        rendered = pm.render_plan(plan["id"])
        return {"status": "success", "plan": plan, "rendered": rendered}
    return {"status": "success", "plan": None, "rendered": "No active plan found."}


@app.post("/api/plans/approve", tags=["Planning"])
async def approve_plan_endpoint(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.plan_mode import PlanMode
    body = await request.json()
    pm = PlanMode()
    success = pm.approve_plan(
        body.get("plan_id", ""),
        approved_by=body.get("approved_by", "api")
    )
    return {"status": "success" if success else "error", "approved": success}


# Todo endpoints
@app.post("/api/todos", tags=["Todo"])
async def add_todo_endpoint(
    request: Request,
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from services.todo_manager import TodoManager
    body = await request.json()
    tm = TodoManager()
    todo = tm.add_todo(
        session_id=session_id,
        content=body.get("content", ""),
        priority=body.get("priority", "medium"),
        category=body.get("category", "general"),
        assignee=body.get("assignee", "")
    )
    return {"status": "success", "todo_id": todo.id, "content": todo.content}


@app.put("/api/todos/{todo_id}", tags=["Todo"])
async def update_todo_endpoint(
    todo_id: str,
    request: Request,
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from services.todo_manager import TodoManager
    body = await request.json()
    tm = TodoManager()
    todo = tm.update_todo(
        session_id=session_id,
        todo_id=todo_id,
        status=body.get("status"),
        notes=body.get("notes")
    )
    if todo:
        return {"status": "success", "todo_id": todo.id, "content": todo.content}
    return {"status": "error", "message": "Todo not found"}


@app.get("/api/todos", tags=["Todo"])
async def list_todos_endpoint(
    session_id: str = "default",
    status_filter: str = None,
    category_filter: str = None,
    current_user=Depends(verify_api_key)
):
    from services.todo_manager import TodoManager
    tm = TodoManager()
    todos = tm.list_todos(session_id, status=status_filter, category=category_filter)
    return {"status": "success", "todos": [t.content for t in todos]}


@app.get("/api/todos/safety-checklist", tags=["Todo"])
async def safety_checklist_endpoint(
    session_id: str = "default",
    current_user=Depends(verify_api_key)
):
    from services.todo_manager import TodoManager
    tm = TodoManager()
    tm.get_safety_checklist(session_id)
    rendered = tm.render_todos(session_id)
    return {"status": "success", "rendered": rendered}


# Skills endpoint
@app.get("/api/skills", tags=["Skills"])
async def list_skills_endpoint(
    query: str = "",
    current_user=Depends(verify_api_key)
):
    from services.skills import SkillManager
    sm = SkillManager()
    if query:
        skill = sm.match_skill_to_query(query)
        if skill:
            return {"status": "success", "matched_skill": skill.name, "description": skill.description}
        return {"status": "success", "matched_skill": None}
    return {"status": "success", "all_skills": [s.name for s in sm.list_skills()]}


# Cost report endpoint
@app.get("/api/costs/report", tags=["Cost Tracking"])
async def cost_report_endpoint(
    current_user=Depends(verify_api_key)
):
    from services.cost_tracker import CostTracker
    ct = CostTracker()
    return {"status": "success", "report": ct.format_cost_report()}


# Prompt suggestions endpoint
@app.get("/api/suggestions", tags=["Intelligence"])
async def suggestions_endpoint(
    query: str = "",
    current_user=Depends(verify_api_key)
):
    from services.prompt_suggestion import PromptSuggestionEngine
    from services.skills import SkillManager
    sm = SkillManager()
    engine = PromptSuggestionEngine(sm)
    suggestions = engine.suggest(query)
    return {"status": "success", "suggestions": suggestions}


# Anomaly Detection endpoints
@app.get("/api/anomalies", tags=["Anomaly Detection"])
async def get_anomalies(
    query: str = "all",
    current_user=Depends(verify_api_key)
):
    from services.anomaly_detector import MiningAnomalySystem
    system = MiningAnomalySystem()
    system.initialize_sample_data()
    result = system.analyze_query(query)
    return {"status": "success", "data": result}


@app.get("/api/anomalies/health", tags=["Anomaly Detection"])
async def anomaly_health(
    current_user=Depends(verify_api_key)
):
    from services.anomaly_detector import MiningAnomalySystem
    system = MiningAnomalySystem()
    system.initialize_sample_data()
    return {"status": "success", "health": system.detector.get_health_summary()}


# Alert System endpoints
@app.get("/api/alerts", tags=["Alert System"])
async def get_alerts(
    category: str = "all",
    current_user=Depends(verify_api_key)
):
    from services.alert_system import AlertSystem
    alert_system = AlertSystem()
    alerts = alert_system.get_active_alerts(category if category != "all" else None)
    return {
        "status": "success",
        "alerts": [
            {
                "id": a.id,
                "title": a.title,
                "message": a.message,
                "severity": a.severity.value,
                "category": a.category,
                "created_at": a.created_at.isoformat()
            }
            for a in alerts
        ]
    }


@app.get("/api/alerts/statistics", tags=["Alert System"])
async def alert_statistics(
    current_user=Depends(verify_api_key)
):
    from services.alert_system import AlertSystem
    alert_system = AlertSystem()
    return {"status": "success", "statistics": alert_system.get_alert_statistics()}


@app.post("/api/alerts/{alert_id}/acknowledge", tags=["Alert System"])
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.alert_system import AlertSystem
    body = await request.json()
    alert_system = AlertSystem()
    success = alert_system.acknowledge_alert(alert_id, body.get("user", "api"), body.get("notes", ""))
    return {"status": "success" if success else "error", "acknowledged": success}


# Document Intelligence endpoints
@app.post("/api/documents/analyze", tags=["Document Intelligence"])
async def analyze_document(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.document_intelligence import DocumentIntelligence, AnalysisType
    body = await request.json()
    di = DocumentIntelligence()

    filepath = body.get("filepath", "")
    if filepath:
        reg_result = di.register_document(filepath)
        if "error" not in reg_result:
            doc_id = reg_result["document_id"]
            analysis_type_str = body.get("analysis_type", "summary")
            try:
                analysis_type = AnalysisType(analysis_type_str)
            except ValueError:
                analysis_type = AnalysisType.SUMMARY
            analysis = di.analyze_document(doc_id, analysis_type)
            if analysis:
                return {"status": "success", "analysis": di.format_analysis_for_display(analysis)}

    return {"status": "error", "message": "Document not found or analysis failed"}


@app.get("/api/documents/analytics", tags=["Document Intelligence"])
async def document_analytics(
    current_user=Depends(verify_api_key)
):
    from services.document_intelligence import DocumentIntelligence
    di = DocumentIntelligence()
    return {"status": "success", "analytics": di.get_analytics()}


# Audit Trail endpoints
@app.get("/api/audit", tags=["Audit Trail"])
async def get_audit_log(
    query_type: str = "recent",
    user_id: str = "",
    limit: int = 20,
    current_user=Depends(verify_api_key)
):
    from services.audit_trail import AuditTrail, AuditQuery
    audit = AuditTrail()

    if query_type == "statistics":
        return {"status": "success", "statistics": audit.get_statistics()}
    elif query_type == "security":
        return {"status": "success", "events": audit.get_security_events()}
    elif query_type == "ai_decisions":
        return {"status": "success", "decisions": audit.get_ai_decision_log()}
    else:
        query = AuditQuery(limit=limit)
        if user_id:
            query.user_id = user_id
        entries = audit.query_entries(query)
        return {
            "status": "success",
            "entries": [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.action_name,
                    "user": e.user_id,
                    "description": e.description,
                    "status": e.status.value
                }
                for e in entries
            ]
        }


# Report Generator endpoints
@app.get("/api/reports/templates", tags=["Report Generator"])
async def list_report_templates(
    current_user=Depends(verify_api_key)
):
    from services.report_generator import ReportGenerator
    rg = ReportGenerator()
    return {"status": "success", "templates": rg.get_templates()}


@app.post("/api/reports/generate", tags=["Report Generator"])
async def generate_report(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.report_generator import ReportGenerator, ReportData
    body = await request.json()
    rg = ReportGenerator()

    report_type = body.get("report_type", "production")
    title = body.get("title", None)

    report_data = ReportData(
        production={"tonnage_mined": 25000, "tonnage_milled": 24000, "gold_grade": 5.2, "recovery_rate": 92.5, "gold_produced": 350},
        safety={"incidents": 0, "near_misses": 2, "inspections": 15, "score": 95},
        financial={"revenue": 700000, "operating_costs": 450000, "cost_per_ounce": 1250, "margin": 750},
        equipment={"Excavator 1": {"availability": 92, "hours": 18}, "Haul Truck 3": {"availability": 88, "hours": 16}}
    )

    template_map = {
        "production": "daily_production",
        "safety": "weekly_safety",
        "financial": "monthly_financial",
        "shift": "shift_handover",
        "equipment": "equipment_status"
    }
    template_name = template_map.get(report_type, "daily_production")

    result = rg.generate_report(
        template_name=template_name,
        data=report_data,
        title=title
    )

    return {"status": "success", "report": result}


# Satellite Remote Sensing Endpoints
@app.post("/api/satellite/search", tags=["Satellite"])
async def search_satellite_data(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.satellite_data_source import SatelliteDataSourceManager, SearchQuery, BoundingBox
    from datetime import datetime, timedelta
    body = await request.json()

    bbox = BoundingBox(
        west=body.get("west", 0),
        south=body.get("south", 0),
        east=body.get("east", 1),
        north=body.get("north", 1)
    )
    query = SearchQuery(
        bbox=bbox,
        start_date=datetime.fromisoformat(body.get("start_date", (datetime.now() - timedelta(days=90)).isoformat())),
        end_date=datetime.fromisoformat(body.get("end_date", datetime.now().isoformat())),
        max_cloud_cover=body.get("max_cloud_cover", 20),
        limit=body.get("limit", 10)
    )

    manager = SatelliteDataSourceManager()
    results = manager.search_all(query)
    return {"status": "success", "results": manager.format_search_results(results)}


@app.post("/api/satellite/spectral", tags=["Satellite"])
async def analyze_spectral(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.spectral_analysis import SpectralCalculator
    body = await request.json()

    calc = SpectralCalculator()

    if body.get("analyze_all", False):
        results = calc.calculate_all_indices(body.get("bands", {}))
    elif body.get("exploration_assessment", False):
        results = calc.get_exploration_assessment(body.get("bands", {}))
    else:
        index_name = body.get("index", "NDVI")
        results = calc.calculate_index(index_name, body.get("bands", {}))

    return {"status": "success", "results": results}


@app.post("/api/satellite/terrain", tags=["Satellite"])
async def analyze_terrain(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.terrain_analysis import TerrainAnalyzer
    body = await request.json()

    analyzer = TerrainAnalyzer()

    if body.get("full_analysis", False):
        results = analyzer.get_terrain_assessment(body.get("dem", []))
    else:
        product = body.get("product", "slope")
        dem = body.get("dem", [])
        if product == "slope":
            results = analyzer.compute_slope(dem)
        elif product == "aspect":
            results = analyzer.compute_aspect(dem)
        elif product == "hillshade":
            results = analyzer.compute_hillshade(dem)
        elif product == "drainage":
            results = analyzer.analyze_drainage(dem)
        elif product == "tpi":
            results = analyzer.compute_tpi(dem)
        else:
            results = analyzer.compute_slope(dem)

    return {"status": "success", "results": results}


@app.post("/api/satellite/features", tags=["Satellite"])
async def extract_features(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.feature_extraction import FeatureExtractor
    body = await request.json()

    extractor = FeatureExtractor()
    dem = body.get("dem", [])
    bands = body.get("bands", None)

    if body.get("extract_all", False):
        results = extractor.extract_all_features(dem, bands)
    elif body.get("exploration_targets", False):
        all_features = extractor.extract_all_features(dem, bands)
        targets = extractor.get_exploration_targets(all_features)
        results = {"features": all_features, "targets": targets}
    else:
        results = extractor.extract_lineaments(dem)

    return {"status": "success", "results": results}


@app.post("/api/satellite/process", tags=["Satellite"])
async def process_satellite_image(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.satellite_processor import SatelliteProcessor, CompositeType
    body = await request.json()

    processor = SatelliteProcessor()
    band_data = body.get("bands", {})

    operation = body.get("operation", "enhancement")

    if operation == "composite":
        composite_type = body.get("composite_type", "true_color")
        try:
            ct = CompositeType(composite_type)
        except ValueError:
            ct = CompositeType.TRUE_COLOR
        results = processor.create_composite(band_data, ct)
    elif operation == "mineral_composite":
        results = processor.create_mineral_exploration_composite(band_data)
    elif operation == "enhancement":
        method = body.get("method", "linear_stretch")
        results = processor.apply_enhancement(band_data, method)
    elif operation == "atmospheric":
        results = processor.apply_atmospheric_correction(band_data)
    elif operation == "quality":
        results = processor.calculate_image_quality(band_data)
    elif operation == "recommendations":
        purpose = body.get("purpose", "mineral_exploration")
        results = processor.get_processing_recommendations(purpose)
    elif operation == "band_math":
        formula = body.get("formula", "B08 - B04")
        results = processor.compute_band_math(band_data, formula)
    else:
        results = {"error": f"Unknown operation: {operation}"}

    return {"status": "success", "results": results}


@app.post("/api/satellite/spatial", tags=["Satellite"])
async def spatial_query(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.gis_engine import SpatialEngine, SpatialPoint, SpatialQueryBuilder, CoordinateTransformer
    from services.satellite_data_source import BoundingBox
    body = await request.json()

    engine = SpatialEngine()
    query_builder = SpatialQueryBuilder(engine)

    operation = body.get("operation", "nearest")

    if operation == "distance":
        p1 = SpatialPoint(body.get("point1", {}).get("x", 0), body.get("point1", {}).get("y", 0))
        p2 = SpatialPoint(body.get("point2", {}).get("x", 0), body.get("point2", {}).get("y", 0))
        distance = engine.haversine_distance(p1, p2)
        results = {"distance_m": distance, "distance_km": distance / 1000}

    elif operation == "buffer":
        center = SpatialPoint(body.get("center", {}).get("x", 0), body.get("center", {}).get("y", 0))
        radius = body.get("radius_m", 1000)
        polygon = engine.buffer_point(center, radius)
        results = {"area_km2": polygon.area_km2, "vertices": len(polygon.vertices)}

    elif operation == "nearest":
        target = SpatialPoint(body.get("target", {}).get("x", 0), body.get("target", {}).get("y", 0))
        deposits = body.get("deposits", [])
        results = query_builder.nearest_deposit(target, deposits)

    elif operation == "grid":
        bbox = BoundingBox(
            body.get("bbox", {}).get("west", 0),
            body.get("bbox", {}).get("south", 0),
            body.get("bbox", {}).get("east", 1),
            body.get("bbox", {}).get("north", 1)
        )
        spacing = body.get("spacing_m", 100)
        results = query_builder.drill_hole_grid(bbox, spacing)

    elif operation == "transform":
        lon = body.get("longitude", 0)
        lat = body.get("latitude", 0)
        crs, x, y = CoordinateTransformer.wgs84_to_utm(lon, lat)
        results = {"utm_crs": crs, "easting": x, "northing": y}

    else:
        results = {"error": f"Unknown spatial operation: {operation}"}

    return {"status": "success", "results": results}


# Multi-Temporal Analysis Endpoints
@app.post("/api/satellite/temporal/detect-changes", tags=["Satellite"])
async def detect_temporal_changes(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.multitemporal_analysis import MultiTemporalAnalyzer, TemporalImage
    from datetime import datetime
    body = await request.json()

    analyzer = MultiTemporalAnalyzer()

    for img_data in body.get("images", []):
        analyzer.add_image(TemporalImage(
            date=datetime.fromisoformat(img_data["date"]),
            bands=img_data.get("bands", {}),
            cloud_cover=img_data.get("cloud_cover", 0)
        ))

    band = body.get("band", "NIR")
    threshold = body.get("threshold", 0.2)
    results = analyzer.detect_changes(band, threshold)

    return {"status": "success", "results": results}


@app.post("/api/satellite/temporal/ndvi-timeseries", tags=["Satellite"])
async def ndvi_timeseries(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.multitemporal_analysis import MultiTemporalAnalyzer, TemporalImage
    from datetime import datetime
    body = await request.json()

    analyzer = MultiTemporalAnalyzer()

    for img_data in body.get("images", []):
        analyzer.add_image(TemporalImage(
            date=datetime.fromisoformat(img_data["date"]),
            bands=img_data.get("bands", {})
        ))

    results = analyzer.compute_ndvi_timeseries()
    return {"status": "success", "results": results}


@app.post("/api/satellite/temporal/vegetation-stress", tags=["Satellite"])
async def vegetation_stress(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.multitemporal_analysis import MultiTemporalAnalyzer, TemporalImage
    from datetime import datetime
    body = await request.json()

    analyzer = MultiTemporalAnalyzer()

    for img_data in body.get("images", []):
        analyzer.add_image(TemporalImage(
            date=datetime.fromisoformat(img_data["date"]),
            bands=img_data.get("bands", {})
        ))

    results = analyzer.detect_vegetation_stress()
    return {"status": "success", "results": results}


@app.post("/api/satellite/temporal/mining-impact", tags=["Satellite"])
async def mining_impact(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.multitemporal_analysis import MultiTemporalAnalyzer, TemporalImage
    from datetime import datetime
    body = await request.json()

    analyzer = MultiTemporalAnalyzer()

    for img_data in body.get("images", []):
        analyzer.add_image(TemporalImage(
            date=datetime.fromisoformat(img_data["date"]),
            bands=img_data.get("bands", {})
        ))

    results = analyzer.detect_mining_impact()
    return {"status": "success", "results": results}


@app.post("/api/satellite/classify", tags=["Satellite"])
async def classify_image(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.multitemporal_analysis import ImageClassifier
    body = await request.json()

    n_classes = body.get("n_classes", 5)
    classifier = ImageClassifier(n_classes=n_classes)

    results = classifier.classify(body.get("bands", {}))

    if "class_statistics" in results:
        identifications = classifier.identify_classes(results["class_statistics"])
        results["identifications"] = identifications

    return {"status": "success", "results": results}


@app.post("/api/satellite/export/geojson", tags=["Satellite"])
async def export_geojson(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.satellite_export import GeoJSONExporter
    body = await request.json()

    exporter = GeoJSONExporter()
    export_type = body.get("type", "targets")

    if export_type == "targets":
        geojson = exporter.export_exploration_targets(body.get("data", []))
    elif export_type == "drill_grid":
        geojson = exporter.export_drill_grid(body.get("data", []))
    elif export_type == "lineaments":
        geojson = exporter.export_lineaments(body.get("data", []))
    elif export_type == "alteration":
        geojson = exporter.export_alteration_zones(body.get("data", []))
    elif export_type == "drainage":
        geojson = exporter.export_drainage_network(body.get("data", {}))
    else:
        geojson = exporter.create_feature_collection([])

    return {"status": "success", "geojson": geojson}


@app.post("/api/satellite/export/kml", tags=["Satellite"])
async def export_kml(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.satellite_export import KMLExporter
    body = await request.json()

    exporter = KMLExporter()
    name = body.get("name", "Mining Analysis Export")
    features = body.get("features", [])
    description = body.get("description", "")

    kml_content = exporter.create_kml(name, features, description)

    return {"status": "success", "kml": kml_content}


@app.post("/api/satellite/export/csv", tags=["Satellite"])
async def export_csv(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.satellite_export import CSVExporter
    body = await request.json()

    exporter = CSVExporter()
    import tempfile, os

    filepath = os.path.join(tempfile.gettempdir(), f"export_{body.get('name', 'data')}.csv")

    if body.get("type") == "time_series":
        exporter.export_time_series(body.get("data", []), filepath)
    else:
        geojson = body.get("geojson", {"features": []})
        exporter.export_feature_collection(geojson, filepath)

    with open(filepath, 'r') as f:
        csv_content = f.read()

    os.remove(filepath)

    return {"status": "success", "csv": csv_content}


@app.post("/api/satellite/report", tags=["Satellite"])
async def generate_satellite_report(
    request: Request,
    current_user=Depends(verify_api_key)
):
    from services.satellite_export import ReportGenerator
    body = await request.json()

    generator = ReportGenerator()
    report_type = body.get("type", "mineral")

    if report_type == "mineral":
        report = generator.generate_mineral_report(
            spectral=body.get("spectral", {}),
            terrain=body.get("terrain", {}),
            features=body.get("features", {}),
            temporal=body.get("temporal")
        )
    elif report_type == "environmental":
        report = generator.generate_environmental_report(
            ndvi_timeseries=body.get("ndvi_timeseries", {}),
            vegetation_stress=body.get("vegetation_stress", {}),
            mining_impact=body.get("mining_impact", {})
        )
    elif report_type == "terrain":
        report = generator.generate_terrain_report(
            terrain=body.get("terrain", {}),
            drainage=body.get("drainage", {})
        )
    else:
        report = "# Unknown Report Type"

    return {"status": "success", "report": report}


# Knowledge Base Endpoints
@app.get("/api/knowledge/documents", tags=["Knowledge"])
async def list_knowledge_documents(current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    docs = kb.list_all_documents()
    return {"status": "success", "documents": docs}


@app.get("/api/knowledge/statistics", tags=["Knowledge"])
async def knowledge_statistics(current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    return {"status": "success", "stats": kb.get_statistics()}


@app.post("/api/knowledge/search", tags=["Knowledge"])
async def search_knowledge(request: Request, current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    body = await request.json()
    query = body.get("query", "")
    category = body.get("category")
    if category:
        docs = kb.search_by_category(category)
        results = [{"document": d, "score": 1.0} for d in docs if query.lower() in d.get("filename", "").lower() or query.lower() in d.get("content_text", "").lower()[:500]]
    else:
        results = kb.search(query)
    return {"status": "success", "results": results}


@app.get("/api/knowledge/recent", tags=["Knowledge"])
async def recent_documents(limit: int = 20, current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    docs = kb.get_recent_documents(limit)
    return {"status": "success", "documents": docs}


@app.post("/api/knowledge/read", tags=["Knowledge"])
async def read_document(request: Request, current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    from services.document_reader import DocumentReader
    body = await request.json()
    kb = KnowledgeBase()
    doc_id = body.get("doc_id")
    file_path = body.get("file_path")
    if doc_id:
        doc = kb.get_document(doc_id)
        if doc:
            file_path = doc.get("file_path") or doc.get("original_filename")
    reader = DocumentReader()
    result = reader.read_document(file_path) if file_path else {"error": "No file path provided"}
    return {"status": "success", "result": result}


@app.post("/api/knowledge/understand", tags=["Knowledge"])
async def understand_document(request: Request, current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    from services.document_reader import DocumentReader
    body = await request.json()
    kb = KnowledgeBase()
    doc_id = body.get("doc_id")
    file_path = body.get("file_path")
    if doc_id:
        doc = kb.get_document(doc_id)
        if doc:
            file_path = doc.get("file_path") or doc.get("original_filename")
    reader = DocumentReader()
    result = reader.read_and_understand(file_path) if file_path else {"error": "No file path provided"}
    return {"status": "success", "result": result}


@app.get("/api/knowledge/summary", tags=["Knowledge"])
async def knowledge_summary(current_user=Depends(verify_api_key)):
    from services.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    return {"status": "success", "summary": kb.get_knowledge_summary()}


# Annotation Endpoints
_annotation_engine = None

def get_annotation_engine():
    global _annotation_engine
    if _annotation_engine is None:
        from services.annotation_engine import AnnotationEngine
        _annotation_engine = AnnotationEngine()
    return _annotation_engine


@app.post("/api/satellite/annotations/create", tags=["Satellite"])
async def create_annotation(request: Request, current_user=Depends(verify_api_key)):
    engine = get_annotation_engine()
    body = await request.json()
    from services.annotation_engine import Annotation, AnnotationType, Coordinate, Style
    from datetime import datetime
    raw_type = body.get("annotation_type", "point").upper()
    ann_type = AnnotationType[raw_type] if raw_type in AnnotationType.__members__ else AnnotationType.POINT
    now = datetime.now()
    raw_coords = body.get("coordinates", [[0, 0]])
    coordinates = []
    for c in raw_coords:
        if isinstance(c, (list, tuple)):
            coordinates.append(Coordinate(x=c[0], y=c[1], z=c[2] if len(c) > 2 else None))
        elif isinstance(c, dict):
            coordinates.append(Coordinate(x=c.get("x", 0), y=c.get("y", 0), z=c.get("z")))
        else:
            coordinates.append(c)
    raw_style = body.get("style", {})
    style = Style(
        fill_color=raw_style.get("fill", "#CCCCCC"),
        stroke_color=raw_style.get("stroke", "#999999"),
        stroke_width=float(raw_style.get("strokeWidth", 2)),
        opacity=float(raw_style.get("opacity", 0.5)),
    )
    annotation = Annotation(
        annotation_id="",
        annotation_type=ann_type,
        image_id=body.get("image_id", "default"),
        coordinates=coordinates,
        properties=body.get("properties", {}),
        style=style,
        created_at=now,
        updated_at=now,
        author=body.get("author", "user")
    )
    engine._store(annotation)
    return {"status": "success", "annotation": annotation.to_geojson()}


@app.post("/api/satellite/annotations/auto-annotate", tags=["Satellite"])
async def auto_annotate(request: Request, current_user=Depends(verify_api_key)):
    engine = get_annotation_engine()
    body = await request.json()
    image_id = body.get("image_id", "default")
    analysis_type = body.get("analysis_type", "spectral")
    results = body.get("results", {})

    if analysis_type == "spectral":
        annotations = engine.auto_annotate_spectral(results, image_id)
    elif analysis_type == "terrain":
        annotations = engine.auto_annotate_terrain(results, image_id)
    elif analysis_type == "features":
        annotations = engine.auto_annotate_features(results, image_id)
    elif analysis_type == "exploration":
        annotations = engine.auto_annotate_from_exploration_assessment(results, image_id)
    else:
        annotations = []

    return {"status": "success", "annotations_created": len(annotations)}


@app.get("/api/satellite/annotations/{image_id}", tags=["Satellite"])
async def get_annotations(image_id: str, current_user=Depends(verify_api_key)):
    engine = get_annotation_engine()
    geojson = engine.get_annotations_geojson(image_id)
    return {"status": "success", "annotations": geojson}


@app.delete("/api/satellite/annotations/{image_id}/{annotation_id}", tags=["Satellite"])
async def delete_annotation(image_id: str, annotation_id: str, current_user=Depends(verify_api_key)):
    engine = get_annotation_engine()
    success = engine.delete_annotation(image_id, annotation_id)
    return {"status": "success" if success else "error", "deleted": success}


# Image Reader Endpoints
_image_reader = None
_image_collection = None

def get_image_reader():
    global _image_reader
    if _image_reader is None:
        from services.satellite_image_reader import SatelliteImageReader
        _image_reader = SatelliteImageReader()
    return _image_reader

def get_image_collection():
    global _image_collection
    if _image_collection is None:
        from services.satellite_image_reader import ImageCollection
        _image_collection = ImageCollection()
    return _image_collection


@app.post("/api/satellite/image/load", tags=["Satellite"])
async def load_satellite_image(request: Request, current_user=Depends(verify_api_key)):
    reader = get_image_reader()
    collection = get_image_collection()
    body = await request.json()
    import numpy as np
    band_data = {}
    for name, data in body.get("bands", {}).items():
        band_data[name] = np.array(data, dtype=np.float64)
    metadata = body.get("metadata", {})
    image = reader.load_from_arrays(band_data, metadata)
    image_id = body.get("image_id", f"img_{hash(str(band_data)) % 100000}")
    collection.add_image(image_id, image)
    return {"status": "success", "image_id": image_id, "summary": reader.get_summary()}


@app.post("/api/satellite/image/analyze", tags=["Satellite"])
async def analyze_satellite_image(request: Request, current_user=Depends(verify_api_key)):
    reader = get_image_reader()
    body = await request.json()
    stats = reader.get_image_stats()
    composites = {}
    try:
        composites["true_color"] = reader.get_true_color_composite()
        composites["false_color"] = reader.get_false_color_composite()
        composites["mineral"] = reader.get_mineral_composite()
    except Exception:
        pass
    return {"status": "success", "stats": stats, "composites": composites, "summary": reader.get_summary()}


@app.post("/api/satellite/image/detect", tags=["Satellite"])
async def detect_features_in_image(request: Request, current_user=Depends(verify_api_key)):
    reader = get_image_reader()
    body = await request.json()
    detection_type = body.get("detection_type", "all")
    results = {}
    if detection_type in ("clouds", "all"):
        results["clouds"] = reader.detect_clouds()
    if detection_type in ("water", "all"):
        results["water"] = reader.detect_water()
    if detection_type in ("vegetation", "all"):
        results["vegetation"] = reader.detect_vegetation()
    if detection_type in ("bare_soil", "all"):
        results["bare_soil"] = reader.detect_bare_soil()
    return {"status": "success", "results": results}


@app.post("/api/satellite/image/pixel", tags=["Satellite"])
async def get_pixel_info(request: Request, current_user=Depends(verify_api_key)):
    reader = get_image_reader()
    body = await request.json()
    lon = body.get("longitude", 0)
    lat = body.get("latitude", 0)
    result = reader.get_pixel_value(lon, lat)
    return {"status": "success", "result": result}


@app.post("/api/satellite/image/thumbnail", tags=["Satellite"])
async def get_image_thumbnail(request: Request, current_user=Depends(verify_api_key)):
    reader = get_image_reader()
    body = await request.json()
    width = body.get("width", 256)
    height = body.get("height", 256)
    result = reader.generate_thumbnail(width, height)
    return {"status": "success", "thumbnail": result}


@app.post("/api/satellite/full-analysis", tags=["Satellite"])
async def full_satellite_analysis(request: Request, current_user=Depends(verify_api_key)):
    body = await request.json()
    bands = body.get("bands", {})
    dem = body.get("dem", [])

    from services.spectral_analysis import SpectralCalculator
    from services.terrain_analysis import TerrainAnalyzer
    from services.feature_extraction import FeatureExtractor
    from services.satellite_export import ReportGenerator

    spectral_calc = SpectralCalculator()
    terrain_analyzer = TerrainAnalyzer()
    feature_extractor = FeatureExtractor()
    report_gen = ReportGenerator()

    spectral_results = spectral_calc.get_exploration_assessment(bands)
    terrain_results = terrain_analyzer.get_terrain_assessment(dem)
    feature_results = feature_extractor.extract_all_features(dem, bands)
    targets = feature_extractor.get_exploration_targets(feature_results)
    feature_results["exploration_targets"] = targets

    engine = get_annotation_engine()
    image_id = body.get("image_id", "full_analysis")
    engine.auto_annotate_from_exploration_assessment(spectral_results, image_id)
    engine.auto_annotate_terrain(terrain_results, image_id)
    engine.auto_annotate_features(feature_results, image_id)

    report = report_gen.generate_mineral_report(
        spectral=spectral_results,
        terrain=terrain_results,
        features=feature_results
    )

    annotations = engine.get_annotations_geojson(image_id)

    return {
        "status": "success",
        "results": {
            "spectral": spectral_results,
            "terrain": terrain_results,
            "features": feature_results,
            "annotations": annotations,
            "report": report
        }
    }
