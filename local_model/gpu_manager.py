import os
import time
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("ai_os.gpu_manager")


class GPUManager:
    """
    Manages the lifecycle of the GPU VM or local LLM server.
    Supports both GCP Compute Engine (production) and local Ollama (development).
    Implements health-checking and idle shutdown for cost optimization.
    """
    def __init__(
        self,
        project: str = "gcp-project",
        zone: str = "us-central1-a",
        instance_name: str = "gpu-vm-instance",
        idle_timeout_minutes: int = 5,
        health_check_url: str = "http://localhost:11434/v1/models"
    ):
        self.project = os.getenv("GCP_PROJECT", project)
        self.zone = os.getenv("GCP_ZONE", zone)
        self.instance_name = os.getenv("GCP_INSTANCE_NAME", instance_name)
        self.idle_timeout_seconds = int(os.getenv("GPU_IDLE_TIMEOUT_MINUTES", str(idle_timeout_minutes))) * 60
        self.health_check_url = os.getenv("LOCAL_LLM_URL", health_check_url)
        self.api_key = os.getenv("LOCAL_LLM_API_KEY", "")

        if "/models" not in self.health_check_url and not self.health_check_url.endswith("/health"):
            self.health_check_url = f"{self.health_check_url.rstrip('/')}/models"

        self.gcp_client = None
        self.is_mocked = True
        self.mock_state = "STOPPED"
        self.last_request_time = datetime.now(timezone.utc)
        self.local_llm_running = False
        self.api_key = os.getenv("LOCAL_LLM_API_KEY", "")

    def _headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

        self.connect()

    def connect(self):
        if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "true":
            logger.info("Test environment detected. GPU Manager running in MOCK mode.")
            self.is_mocked = True
            return

        try:
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                from google.cloud import compute_v1
                self.gcp_client = compute_v1.InstancesClient()
                self.is_mocked = False
                logger.info(f"Connected to Google Compute Engine. Project: {self.project}")
            else:
                logger.info("No GCP credentials. Using local Ollama or mock mode.")
                self.is_mocked = True
        except Exception as e:
            logger.warning(f"GCP client init failed: {e}. Using local/mock mode.")
            self.is_mocked = True

    def get_status(self) -> str:
        if self.is_mocked:
            if self.local_llm_running:
                return "RUNNING"
            return self.mock_state

        try:
            instance = self.gcp_client.get(
                project=self.project, zone=self.zone, instance=self.instance_name
            )
            return instance.status
        except Exception as e:
            logger.error(f"GCE status check error: {e}")
            return self.mock_state

    def start_gpu(self) -> bool:
        status = self.get_status()
        if status in ("RUNNING", "STAGING", "PROVISIONING"):
            logger.info(f"GPU/LLM server already {status}.")
            self.update_last_request_time()
            return True

        logger.info(f"Starting GPU/LLM server (current: {status})...")

        if self.is_mocked:
            self.mock_state = "STARTING"
            logger.info("[GPU] Starting local LLM server...")

            try:
                response = httpx.get(self.health_check_url, headers=self._headers(), timeout=5.0)
                if response.status_code == 200:
                    logger.info("[GPU] Local LLM server already running at health check endpoint.")
                    self.local_llm_running = True
                    self.mock_state = "RUNNING"
                    self.update_last_request_time()
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                logger.info("[GPU] Local LLM server not detected. Running in mock mode.")
                self.mock_state = "RUNNING"
                self.local_llm_running = False
                self.update_last_request_time()
                return True

        try:
            operation = self.gcp_client.start(
                project=self.project, zone=self.zone, instance=self.instance_name
            )
            logger.info(f"GCE start operation: {operation.name}")
            self.update_last_request_time()
            return True
        except Exception as e:
            logger.error(f"Failed to start GCE instance: {e}")
            return False

    def stop_gpu(self) -> bool:
        status = self.get_status()
        if status in ("TERMINATED", "STOPPING", "STOPPED"):
            logger.info(f"GPU/LLM server already {status}.")
            return True

        logger.info(f"Stopping GPU/LLM server (current: {status})...")

        if self.is_mocked:
            self.mock_state = "STOPPING"
            time.sleep(0.5)
            self.mock_state = "STOPPED"
            self.local_llm_running = False
            logger.info("[GPU] Local LLM server stopped.")
            return True

        try:
            operation = self.gcp_client.stop(
                project=self.project, zone=self.zone, instance=self.instance_name
            )
            logger.info(f"GCE stop operation: {operation.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop GCE instance: {e}")
            return False

    def wait_for_health(self, timeout_seconds: int = 120) -> bool:
        logger.info(f"Health check: {self.health_check_url} (timeout: {timeout_seconds}s)")

        if self.is_mocked:
            if self.local_llm_running:
                try:
                    response = httpx.get(self.health_check_url, headers=self._headers(), timeout=5.0)
                    if response.status_code == 200:
                        logger.info("[GPU] Health check PASSED. LLM server ready.")
                        return True
                except (httpx.ConnectError, httpx.TimeoutException):
                    logger.info("[GPU] LLM server unreachable. Using mock reasoning.")
                    return True

            logger.info("[GPU] Mock mode. LLM health check simulated.")
            time.sleep(0.5)
            return True

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                response = httpx.get(self.health_check_url, headers=self._headers(), timeout=2.0)
                if response.status_code == 200:
                    logger.info("LLM health check PASSED. Model ready.")
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(3)

        logger.error(f"LLM health check TIMED OUT after {timeout_seconds}s.")
        return False

    def update_last_request_time(self):
        self.last_request_time = datetime.now(timezone.utc)

    def check_idle_shutdown(self) -> bool:
        status = self.get_status()
        if status not in ("RUNNING", "STARTING"):
            return False

        elapsed = (datetime.now(timezone.utc) - self.last_request_time).total_seconds()
        logger.info(f"GPU idle: {elapsed:.1f}s / {self.idle_timeout_seconds}s limit.")

        if elapsed >= self.idle_timeout_seconds:
            logger.info(f"GPU idle limit reached ({self.idle_timeout_seconds}s). Shutting down.")
            self.stop_gpu()
            return True

        return False
