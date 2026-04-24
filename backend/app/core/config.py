from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MetaGuard API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    app_mode: str = "mock"
    openmetadata_url: str = "https://sandbox.open-metadata.org"
    openmetadata_jwt: str = ""
    openmetadata_api_path: str = "/api/v1"
    openmetadata_verify_ssl: bool = True
    zhipu_api_key: str = ""
    zhipu_model_default: str = "glm-4-plus"
    zhipu_model_passport: str = "glm-4-plus"
    google_api_key: str = ""
    gemini_model_default: str = "gemini-2.5-flash"
    gemini_model_passport: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model_default: str = "llama-3.3-70b-versatile"
    groq_model_passport: str = "llama-3.3-70b-versatile"
    poll_interval_seconds: int = 60
    lineage_depth: int = 10
    cache_ttl_minutes: int = 15
    dead_data_threshold_days: int = 90
    cost_per_gb_month: float = 0.023
    default_spreadsheet_id: str = ""
    slack_bot_token: str = ""
    
    @property
    def google_api_key_list(self) -> list[str]:
        if not self.google_api_key:
            return []
        return [k.strip() for k in self.google_api_key.split(",") if k.strip()]

    @property
    def groq_api_key_list(self) -> list[str]:
        if not self.groq_api_key:
            return []
        return [k.strip() for k in self.groq_api_key.split(",") if k.strip()]

    @property
    def zhipu_api_key_list(self) -> list[str]:
        if not self.zhipu_api_key:
            return []
        return [k.strip() for k in self.zhipu_api_key.split(",") if k.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    return Settings()
