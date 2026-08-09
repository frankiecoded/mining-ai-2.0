from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_KEY: str = Field(default="", description="API key for authenticated endpoints - REQUIRED in production")
    SECRET_KEY: str = Field(default="", description="Secret key for session signing - REQUIRED in production")
    ENVIRONMENT: str = Field(default="development", description="development, staging, production")
    DEBUG: bool = Field(default=False)

    WHATSAPP_TOKEN: str = Field(default="", description="Meta WhatsApp Cloud API token")
    WHATSAPP_VERIFY_TOKEN: str = Field(default="", description="Webhook verification token - REQUIRED for WhatsApp")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="", description="WhatsApp business phone number ID")

    DATABASE_URL: str = Field(default="")

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = Field(default="", description="Qdrant Cloud endpoint URL (overrides host/port when set)")
    QDRANT_API_KEY: str = Field(default="", description="Qdrant Cloud API key")

    REDIS_URL: str = "redis://localhost:6379/0"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET_NAME: str = "ai-os-storage"

    LOCAL_LLM_URL: str = "http://localhost:11434/v1"
    LOCAL_LLM_MODEL: str = "llama3.1:8b"
    LOCAL_LLM_API_KEY: str = Field(default="", description="Optional API key for hosted OpenAI-compatible LLM endpoints")
    MOCK_LLM: bool = False

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384

    GCP_PROJECT: str = ""
    GCP_ZONE: str = ""
    GCP_INSTANCE_NAME: str = ""
    GPU_IDLE_TIMEOUT_MINUTES: int = 15

    SERPER_API_KEY: str = ""

    CORS_ORIGINS: str = Field(default="http://localhost:3000", description="Comma-separated allowed origins - never use * in production")
    ALLOWED_HOSTS: str = Field(default="localhost,127.0.0.1", description="Comma-separated allowed hosts")

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_WEBHOOK_PER_MINUTE: int = 30

    BASE_URL: str = Field(default="http://localhost:8000", description="Base URL for generated links")

    STORAGE_LOCAL_DIR: str = Field(default="", description="Local storage directory (auto-detected if empty)")

    WHATSAPP_API_VERSION: str = "v18.0"

    PROCESSING_MODE: str = Field(default="sync", description="sync = process webhook inline, queue = enqueue to wa_inbox for the worker")
    WORKER_POLL_INTERVAL: float = 3.0
    WORKER_BATCH_SIZE: int = 5
    WORKER_MAX_ATTEMPTS: int = 3
    WORKER_IDLE_TASKS: bool = Field(default=True, description="Run self-improvement tasks when the inbox is empty")
    IDLE_TASK_BUDGET_SECONDS: float = 6.0

    WHISPER_MODEL_SIZE: str = "base"
    TTS_ENGINE: str = "gtts"
    TTS_VOICE: str = "en"

    CURRENCY_SYMBOL: str = "$"
    CURRENCY_CODE: str = "USD"

    BUDGET_ALERT_THRESHOLD_PERCENT: float = 10.0
    EQUIPMENT_TEMP_ALARM_CELSIUS: float = 99.0
    PROCURE_MENT_AUTO_APPROVE_THRESHOLD: float = 10000.0
    CFO_SIGNOFF_THRESHOLD: float = 50000.0

    @property
    def cors_origins_list(self) -> list:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> list:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def storage_dir(self) -> str:
        if self.STORAGE_LOCAL_DIR:
            return self.STORAGE_LOCAL_DIR
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "local_buckets")

    def validate_production_config(self):
        """Validate required config in production mode."""
        if not self.is_production:
            return
        missing = []
        if not self.API_KEY:
            missing.append("API_KEY")
        if not self.SECRET_KEY:
            missing.append("SECRET_KEY")
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if missing:
            raise ValueError(f"Production mode requires: {', '.join(missing)}. Set these in .env or environment.")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
