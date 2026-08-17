from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_KEY: str = Field(default="", description="API key for authenticated endpoints")
    SECRET_KEY: str = Field(default="", description="Secret key for session signing")
    ENVIRONMENT: str = Field(default="development", description="development or production")
    DEBUG: bool = Field(default=False)

    # --- Local LLM (Ollama or any OpenAI-compatible server) ---
    LOCAL_LLM_URL: str = "http://localhost:11434/v1"
    LOCAL_LLM_MODEL: str = "qwen3-coder:30b"
    LOCAL_LLM_API_KEY: str = Field(default="", description="Optional API key for hosted OpenAI-compatible LLM endpoints")
    REASONING_EFFORT: str = Field(default="", description="Reasoning effort for hosted reasoning models (e.g. 'low', 'medium', 'high'). Empty disables the param.")
    MOCK_LLM: bool = False

    # --- Embedding ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384

    # --- External Search ---
    SERPER_API_KEY: str = ""

    # --- Database ---
    DATABASE_URL: str = Field(default="", description="PostgreSQL connection string (e.g. postgresql://user:pass@host:5432/db). Empty falls back to local SQLite.")

    # --- Server / CORS ---
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000", description="Comma-separated allowed origins")
    RATE_LIMIT_PER_MINUTE: int = 60
    BASE_URL: str = Field(default="http://localhost:8000", description="Base URL for generated links")

    # --- Local Storage ---
    STORAGE_LOCAL_DIR: str = Field(default="", description="Local storage directory (auto-detected if empty)")
    UPLOAD_DIR: str = Field(default="data/uploads", description="Directory for uploaded files (relative to project root)")

    # --- Finance/Mining Thresholds ---
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
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def storage_dir(self) -> str:
        if self.STORAGE_LOCAL_DIR:
            return self.STORAGE_LOCAL_DIR
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "local_data")

    def validate_production_config(self):
        """Validate required config in production mode."""
        if not self.is_production:
            return
        missing = []
        if not self.API_KEY:
            missing.append("API_KEY")
        if not self.SECRET_KEY:
            missing.append("SECRET_KEY")
        if missing:
            raise ValueError(f"Production mode requires: {', '.join(missing)}. Set these in .env or environment.")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
