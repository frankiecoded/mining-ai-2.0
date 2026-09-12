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

    # --- Local LLM (any OpenAI-compatible server: Ollama, vLLM, or HF Router) ---
    LOCAL_LLM_URL: str = "http://localhost:11434/v1"
    LOCAL_LLM_MODEL: str = "qwen3-coder:30b"
    LOCAL_LLM_API_KEY: str = Field(default="", description="Optional API key for hosted OpenAI-compatible LLM endpoints")
    REASONING_EFFORT: str = Field(default="", description="Reasoning effort for hosted reasoning models (e.g. 'low', 'medium', 'high'). Empty disables the param.")
    MOCK_LLM: bool = False

    # --- Hugging Face Inference Providers router ---
    # The router is OpenAI-compatible at https://router.huggingface.co/v1 with the
    # HF access token as the Bearer key. Model routing policy is suffixed to the
    # model id (":fastest", ":cheapest", or ":<provider>").
    HF_TOKEN: str = Field(default="", description="Hugging Face access token for the Inference Providers router")
    VISION_LLM_MODEL: str = Field(default="Qwen/Qwen3-VL-30B-A3B-Instruct:deepinfra", description="HF model id used for image/multimodal analysis (a vision-language model)")
    VISION_LLM_URL: str = Field(default="https://router.huggingface.co/v1", description="OpenAI-compatible base URL used for the vision model")

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

    # --- Token Conservation Policy (budgets are in estimated tokens, ~chars/4) ---
    # Hard ceiling for the whole prompt the model actually receives. History is
    # rolled up, system sections (RAG/digest) are capped at build time so the
    # system brief itself can never blow the budget.
    TOKEN_CONTEXT_BUDGET: int = Field(default=6000, description="Total context budget in estimated tokens per LLM call")
    # Smallest system prompt share that must ALWAYS survive (persona + routing).
    TOKEN_SYSTEM_MIN_CHARS: int = Field(default=1200, description="Minimum core system-prompt characters never trimmed")
    # Output cap sent as max_tokens for completions (0 disables).
    TOKEN_MAX_OUTPUT: int = Field(default=1024, description="max_tokens sent with llm completions (0 = server default)")
    # Tool-loop depth: number of full-context reverse passes allowed per turn.
    TOKEN_MAX_ROUNDS: int = Field(default=8, description="Max tool-call rounds per user message")
    # RAG breadth: top-N hits and per-hit snippet cap feeding the system prompt.
    TOKEN_RAG_LIMIT: int = Field(default=12, description="Max vector hits injected into the system prompt")
    TOKEN_RAG_SNIPPET_CHARS: int = Field(default=800, description="Max chars per RAG hit injected into the system prompt")
    # Knowledge digest: compact dataset index chars injected (0 = skip entirely).
    TOKEN_DIGEST_CHARS: int = Field(default=6000, description="Max chars of the dataset index injected into the system prompt (0 = none)")
    # History loading: recent messages pulled from the DB per session (2/turn).
    TOKEN_HISTORY_TURNS: int = Field(default=40, description="Conversation turns (rounds of 2 messages) loaded on resume")
    # Long-term-memory LLM extraction gate: min chars + min seconds between calls.
    TOKEN_FACT_MIN_CHARS: int = Field(default=20, description="Min user-message chars before running fact extraction")
    TOKEN_FACT_MIN_INTERVAL_S: float = Field(default=60.0, description="Min seconds between fact-extraction LLM calls per session")
    # RAG + team-digest query cache TTL (seconds). Repeated questions skip re-POSTs.
    TOKEN_CACHE_TTL_S: float = Field(default=300.0, description="TTL for RAG/query-context caches")
    # Tool schema policy: empty = model answers without tools (greetings only).
    TOKEN_LITE_TOOLS: bool = Field(default=True, description="Skip the 31-tool schema for casual/greeting messages")

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
