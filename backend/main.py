import os
import uuid
import time
import hashlib
import hmac
import logging
import asyncio
from typing import Dict, Any, List, Optional
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, Header, HTTPException, status, Depends
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import settings
from database.postgres_client import PostgresClient
from vector_db.qdrant_client import VectorDBClient
from storage.minio_client import MinIOClient

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
    """Verify API key using timing-safe comparison. Rejects when unconfigured in production."""
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

# ---------- Initialize Infrastructure ----------
postgres_client = PostgresClient(dsn=settings.DATABASE_URL)
vector_client = VectorDBClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT,
                               url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
minio_client = MinIOClient(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY
)

llm = LocalLLMAdapter(model_name=settings.LOCAL_LLM_MODEL, api_url=settings.LOCAL_LLM_URL)
research_service = ResearchService(serper_api_key=settings.SERPER_API_KEY)
doc_service = DocumentService(minio_client=minio_client)
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
    description="WhatsApp-integrated AI assistant for gold mining, precious stones, rare earths, and financial intelligence.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
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

class VoiceReplyRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{6,14}$")
    text: str = Field(..., min_length=1, max_length=5000)

class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    num_results: int = Field(default=5, ge=1, le=20)

class ChatStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    phone_number: str = Field(default="anonymous", max_length=20)
    interaction_mode: str = Field(default="whatsapp_chat", pattern=r"^(whatsapp_chat|voice_note)$")

# ---------- Helpers ----------
def verify_whatsapp_signature(request_body: bytes, signature: str) -> bool:
    """Verify WhatsApp webhook signature. Rejects when SECRET_KEY is not configured."""
    if not settings.SECRET_KEY:
        logger.warning("WhatsApp webhook received but SECRET_KEY not configured - rejecting")
        return False
    if not signature:
        return False
    if signature.startswith("sha256="):
        signature = signature[7:]
    expected = hmac.new(settings.SECRET_KEY.encode(), request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

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

async def send_whatsapp_message_async(recipient_phone: str, text: str, media_url: Optional[str] = None) -> Dict[str, Any]:
    if not settings.WHATSAPP_TOKEN:
        logger.info(f"Simulated WhatsApp post to {recipient_phone}: '{text[:80]}'")
        return {"status": "simulated_success"}

    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    if media_url:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "document",
            "document": {"link": media_url, "caption": text, "filename": "Report.pdf"}
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": text}
        }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            logger.info(f"WhatsApp API status: {response.status_code}")
            return response.json()
    except Exception as e:
        logger.error(f"WhatsApp API error: {_sanitize_error(e)}")
        return {"status": "error"}

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
    full_path = os.path.realpath(os.path.join(local_dir, settings.MINIO_BUCKET_NAME, file_path))
    if not full_path.startswith(os.path.realpath(local_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)

# ---------- WhatsApp Webhook ----------
@app.get("/webhook", tags=["WhatsApp"])
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if not settings.WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(status_code=503, detail="WhatsApp verify token not configured")
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook", tags=["WhatsApp"])
async def receive_whatsapp_message(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_whatsapp_signature(body, signature):
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Invalid signature"})

    if not await rate_limiter.is_allowed("webhook", settings.RATE_LIMIT_WEBHOOK_PER_MINUTE):
        return JSONResponse(status_code=429, content={"status": "error", "detail": "Rate limit"})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Invalid JSON"})

    if "entry" not in payload:
        return JSONResponse(status_code=200, content={"status": "ignored"})

    try:
        entry = payload["entry"][0]
        value = entry["changes"][0]["value"]
        if "messages" not in value:
            return JSONResponse(status_code=200, content={"status": "ignored"})

        msg = value["messages"][0]
        sender = msg["from"]
        msg_type = msg["type"]

        if not sender or not msg_type:
            return JSONResponse(status_code=400, content={"status": "error", "detail": "Invalid message"})

        session_id = f"wa_{sender}"
        user_text = ""
        attachments = []
        in_media_uri = ""
        in_media_mime = ""
        in_media_name = ""

        if msg_type == "text":
            user_text = msg["text"]["body"][:5000]
        elif msg_type == "audio":
            audio_id = msg["audio"]["id"]
            in_media_uri = f"whatsapp://media/{audio_id}"
            in_media_mime = msg["audio"].get("mime_type", "audio/ogg")
            in_media_name = f"{audio_id}.ogg"
            attachments.append({
                "storage_uri": f"s3://{settings.MINIO_BUCKET_NAME}/voice_notes/{audio_id}.ogg",
                "mime_type": in_media_mime,
                "name": in_media_name
            })
            user_text = "[Voice note attached]"
        elif msg_type == "image":
            image_id = msg["image"]["id"]
            in_media_uri = f"whatsapp://media/{image_id}"
            in_media_mime = msg["image"].get("mime_type", "image/png")
            in_media_name = f"image_{image_id}.png"
            attachments.append({
                "storage_uri": f"s3://{settings.MINIO_BUCKET_NAME}/images/{image_id}.png",
                "mime_type": in_media_mime,
                "name": in_media_name
            })
            user_text = msg["image"].get("caption", "Analyze this image")[:5000]
        elif msg_type == "document":
            doc_id = msg["document"]["id"]
            in_media_uri = f"whatsapp://media/{doc_id}"
            in_media_mime = msg["document"].get("mime_type", "application/pdf")
            in_media_name = msg["document"].get("filename", "document.pdf")
            attachments.append({
                "storage_uri": f"s3://{settings.MINIO_BUCKET_NAME}/documents/{doc_id}.pdf",
                "mime_type": in_media_mime,
                "name": in_media_name
            })
            user_text = f"Analyze document: {msg['document'].get('filename', 'document')}"[:5000]
        else:
            return JSONResponse(status_code=200, content={"status": "ignored"})

        if settings.PROCESSING_MODE == "queue":
            message_id = postgres_client.enqueue_wa_message(
                phone_number=sender,
                msg_type=msg_type,
                text=user_text,
                media_uri=in_media_uri,
                media_mime=in_media_mime,
                media_name=in_media_name,
            )
            logger.info(f"Queued WhatsApp message {message_id} from {sender} (worker will process)")
            return JSONResponse(status_code=200, content={"status": "queued", "message_id": message_id})

        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(None, lambda: orchestrator.run(
            session_id=session_id,
            phone_number=sender,
            text_message=user_text,
            attachments=attachments
        ))

        final_text = final_state["messages"][-1].content

        postgres_client.log_audit(phone_number=sender, action="WHATSAPP_PROCESSED", details={"type": msg_type})

        attachment_link = None
        if final_state.get("output_report"):
            raw_uri = final_state["output_report"]["storage_uri"]
            clean = raw_uri.replace(f"local://{settings.MINIO_BUCKET_NAME}/", "").replace("local://", "")
            attachment_link = f"{settings.BASE_URL}/files/{clean}"

        await send_whatsapp_message_async(sender, final_text, attachment_link)

        return JSONResponse(status_code=200, content={"status": "success", "response": {"text": final_text}})

    except Exception as e:
        logger.error(f"Webhook processing error: {_sanitize_error(e)}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": "Processing failed"})

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

# ---------- Voice Note TTS ----------
@app.post("/api/whatsapp/voice-reply", tags=["Voice"], dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
async def whatsapp_voice_reply(req: VoiceReplyRequest):
    loop = asyncio.get_event_loop()
    final_state = await loop.run_in_executor(None, lambda: orchestrator.run(
        session_id=f"wa_{req.phone_number}",
        phone_number=req.phone_number,
        text_message=req.text,
        interaction_mode="whatsapp_chat"
    ))
    response_text = final_state["messages"][-1].content
    audio_bytes = voice_service.text_to_speech(response_text)

    audio_filename = f"voice_reply_{uuid.uuid4().hex[:8]}.mp3"
    audio_dir = os.path.join(settings.storage_dir, settings.MINIO_BUCKET_NAME, "voice_replies")
    os.makedirs(audio_dir, exist_ok=True)
    with open(os.path.join(audio_dir, audio_filename), "wb") as f:
        f.write(audio_bytes)

    return {
        "text_response": response_text,
        "audio_url": f"{settings.BASE_URL}/files/voice_replies/{audio_filename}"
    }

# ---------- Streaming Chat ----------
@app.post("/api/chat/stream", tags=["Streaming"], dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
async def stream_chat(req: ChatStreamRequest):
    """Server-Sent Events (SSE) streaming endpoint for real-time LLM responses."""
    session_id = f"stream_{req.phone_number}_{uuid.uuid4().hex[:8]}"

    def event_generator():
        import json

        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"

        try:
            for event in orchestrator.stream(
                session_id=session_id,
                phone_number=req.phone_number,
                text_message=req.message,
                interaction_mode=req.interaction_mode
            ):
                if isinstance(event, dict):
                    if event.get("error"):
                        yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred processing your request'})}\n\n"
                        break

                    for node_name, node_output in event.items():
                        if node_name == "__end__":
                            continue

                        if "messages" in node_output:
                            for msg in node_output["messages"]:
                                if hasattr(msg, "content") and msg.content:
                                    yield f"data: {json.dumps({'type': 'message', 'content': msg.content})}\n\n"
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        yield f"data: {json.dumps({'type': 'tool_call', 'name': tc.get('name', ''), 'args': tc.get('args', {})})}\n\n"

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
