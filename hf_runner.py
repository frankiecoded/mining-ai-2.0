"""
Hugging Face Spaces entrypoint for the AI OS WhatsApp worker.

Architecture:
  WhatsApp -> Cloudflare Worker (webhook, always-on) -> Neon queue (wa_inbox)
        -> this Space: worker polls the queue, runs the orchestrator, replies.

The Space runs two things in one container:
  1. The FastAPI app on $PORT (default 7860) so Hugging Face sees a live port
     and so /health, /files and the optional /webhook endpoints are available.
  2. The worker loop (backend.worker) in a background thread so queued
     WhatsApp messages are processed even though the API process is the entrypoint.

All state lives in external cloud services (Neon, Qdrant, MinIO), so the Space
is fully disposable - restarts and hardware changes are harmless.

Run: python hf_runner.py
"""
import logging
import os
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ai_os.hf")

PORT = int(os.environ.get("PORT", "7860"))


def _run_worker() -> None:
    """Run the WhatsApp queue worker in a background thread."""
    try:
        from backend.worker import main as worker_main
        worker_main()
    except Exception as e:
        logger.error(f"Worker thread crashed: {e}", exc_info=True)


def main() -> None:
    os.environ.setdefault("PROCESSING_MODE", "queue")

    worker_thread = threading.Thread(target=_run_worker, name="aios-worker", daemon=True)
    worker_thread.start()
    logger.info("Worker thread started.")

    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=PORT,
        workers=1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
