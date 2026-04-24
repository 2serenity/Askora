from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Аналитика заказов"
    app_secret_key: str = Field(default="super-secret-dev-key-change-me", alias="APP_SECRET_KEY")
    jwt_expire_minutes: int = 60 * 8
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/analytics_hub",
        alias="DATABASE_URL",
    )
    default_data_source_key: str = Field(default="default", alias="DEFAULT_DATA_SOURCE_KEY")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )
    llm_provider: Literal["auto", "local", "openai", "deepseek", "disabled"] = Field(default="local", alias="LLM_PROVIDER")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    llm_max_output_tokens: int = Field(default=1400, alias="LLM_MAX_OUTPUT_TOKENS")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-5.2", alias="OPENAI_MODEL")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    local_intent_model_path: str = Field(
        default="app/ai/model/local_intent_model.json",
        alias="LOCAL_INTENT_MODEL_PATH",
    )
    local_intent_min_similarity: float = Field(default=0.24, alias="LOCAL_INTENT_MIN_SIMILARITY")
    local_intent_min_margin: float = Field(default=0.01, alias="LOCAL_INTENT_MIN_MARGIN")
    query_timeout_ms: int = Field(default=5000, alias="QUERY_TIMEOUT_MS")
    max_result_rows: int = Field(default=500, alias="MAX_RESULT_ROWS")
    max_sql_complexity: int = Field(default=12, alias="MAX_SQL_COMPLEXITY")
    max_query_cost: float = Field(default=250000, alias="MAX_QUERY_COST")
    query_rate_limit_per_window: int = Field(default=30, alias="QUERY_RATE_LIMIT_PER_WINDOW")
    query_rate_limit_window_seconds: int = Field(default=60, alias="QUERY_RATE_LIMIT_WINDOW_SECONDS")
    semantic_catalog_path: str = Field(
        default="app/semantic_layer/config/catalog.yaml",
        alias="SEMANTIC_CATALOG_PATH",
    )
    semantic_templates_path: str = Field(
        default="app/semantic_layer/config/templates.yaml",
        alias="SEMANTIC_TEMPLATES_PATH",
    )
    seed_demo_data: bool = Field(default=True, alias="SEED_DEMO_DATA")
    dataset_csv_path: str = Field(default="/app/data/train.csv", alias="DATASET_CSV_PATH")
    scheduler_timezone: str = Field(default="Europe/Kaliningrad", alias="SCHEDULER_TIMEZONE")
    email_stub_sender: str = Field(default="reports@analytics.local", alias="EMAIL_STUB_SENDER")
    allow_self_registration: bool = Field(default=False, alias="ALLOW_SELF_REGISTRATION")
    auth_cookie_secure: bool | None = Field(default=None, alias="AUTH_COOKIE_SECURE")

    @property
    def access_token_ttl_seconds(self) -> int:
        return self.jwt_expire_minutes * 60

    @property
    def cookie_secure(self) -> bool:
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return self.app_env == "production"

    def validate_production_safety(self) -> None:
        if self.app_env != "production":
            return
        if self.app_secret_key == "super-secret-dev-key-change-me":
            raise RuntimeError("APP_SECRET_KEY must be overridden in production.")
        if not self.cookie_secure:
            raise RuntimeError("Secure cookies must be enabled in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
