"""
Worker Mode - polls the wa_inbox queue and processes WhatsApp messages on demand.

Designed to run on a disposable compute node (e.g. Google Colab):
  * WhatsApp messages are enqueued into PostgreSQL by the always-on webhook relay
    (backend/main.py in "queue" mode, or deployment/cloudflare-worker.js).
  * This worker polls the queue, runs the orchestrator, sends the reply back to
    WhatsApp via the Graph API, and marks the message as done.
  * If the worker restarts, pending messages simply resume - nothing is lost because
    conversation memory lives in PostgreSQL and datasets/models live in persistent storage.

Run: python -m backend.worker
"""
import asyncio
import logging
import time
import traceback
from typing import Dict, Any, Optional

from backend.config import settings
from backend.main import (
    orchestrator,
    postgres_client,
    minio_client,
    scheduler,
    llm,
    send_whatsapp_message_async,
)
from backend.tasks import IdleTaskRunner

logger = logging.getLogger("ai_os.worker")


def _build_idle_runner() -> Optional[IdleTaskRunner]:
    if not settings.WORKER_IDLE_TASKS:
        return None
    return IdleTaskRunner(
        postgres_client,
        llm=llm,
        budget_seconds=settings.IDLE_TASK_BUDGET_SECONDS,
    )


def _fetch_whatsapp_media(media_id: str) -> Optional[Dict[str, Any]]:
    """Download a WhatsApp media object, store it, and return an attachment dict."""
    if not settings.WHATSAPP_TOKEN:
        return None
    import httpx
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
    meta_url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{media_id}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(meta_url, headers=headers)
        resp.raise_for_status()
        download_url = resp.json().get("url")
        if not download_url:
            return None
        data = client.get(download_url, headers=headers, timeout=60.0)
        data.raise_for_status()
        content_type = data.headers.get("content-type", "application/octet-stream")
        storage_uri = minio_client.upload_file(media_id, data.content, content_type)
        return {"storage_uri": storage_uri, "mime_type": content_type, "name": media_id}


def _process_message(row: Dict[str, Any]) -> None:
    msg_id = row["id"]
    phone = row["phone_number"]
    msg_type = row.get("msg_type", "text")
    text = row.get("text", "") or ""
    media_uri = row.get("media_uri", "") or ""
    media_mime = row.get("media_mime", "") or "application/octet-stream"
    media_name = row.get("media_name", "") or "media"

    postgres_client.mark_wa_message_processing(msg_id)
    session_id = f"wa_{phone}"
    logger.info(f"[{msg_id}] Processing {msg_type} from {phone}")

    attachments: List[Dict[str, Any]] = []
    if media_uri.startswith("whatsapp://media/"):
        media_id = media_uri.rsplit("/", 1)[-1]
        try:
            fetched = _fetch_whatsapp_media(media_id)
            if fetched:
                attachments.append(fetched)
                text = f"[{media_name} attached]"
            else:
                logger.warning(f"[{msg_id}] Could not fetch media {media_id}, processing text only")
        except Exception as e:
            logger.error(f"[{msg_id}] Media fetch failed: {e}")

    try:
        final_state = orchestrator.run(
            session_id=session_id,
            phone_number=phone,
            text_message=text,
            attachments=attachments,
        )
        reply = final_state["messages"][-1].content
        asyncio.run(send_whatsapp_message_async(phone, reply))
        postgres_client.complete_wa_message(msg_id, reply)
        postgres_client.log_audit(phone, "WORKER_PROCESSED", {"type": msg_type, "msg_id": msg_id})
        logger.info(f"[{msg_id}] Replied to {phone}")
    except Exception as e:
        logger.error(f"[{msg_id}] Failed: {traceback.format_exc()}")
        postgres_client.fail_wa_message(msg_id, str(e)[:500], settings.WORKER_MAX_ATTEMPTS)


def main() -> None:
    logger.info(
        f"Worker started. Polling every {settings.WORKER_POLL_INTERVAL}s "
        f"(batch {settings.WORKER_BATCH_SIZE}, max attempts {settings.WORKER_MAX_ATTEMPTS})."
    )
    idle_runner = _build_idle_runner()
    if idle_runner:
        logger.info("Idle self-improvement enabled: analytics, conversation mining, Q&A generation.")
    scheduler.start()
    last_heartbeat = time.time()
    try:
        while True:
            rows = postgres_client.fetch_pending_wa_messages(settings.WORKER_BATCH_SIZE) or []
            if rows:
                for row in rows:
                    _process_message(dict(row))
            elif idle_runner:
                idle_runner.run_one()
            if time.time() - last_heartbeat >= 60:
                logger.info(
                    f"Worker heartbeat: {len(rows)} pending, "
                    f"knowledge base = {postgres_client.knowledge_count()} entries"
                )
                last_heartbeat = time.time()
            time.sleep(settings.WORKER_POLL_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
