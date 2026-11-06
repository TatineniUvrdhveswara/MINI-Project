from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Scientific Research Assistant API"
    api_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "development"
    request_timeout: float = 15.0
    semantic_scholar_api_key: str | None = None
    paper_storage_path: str = "./data/papers"
    metadata_db_path: str = "./data/metadata.db"
    vector_db_path: str = "./data/chroma"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    llm_provider: str = "grounded_fallback"
    llm_model: str = "grounded-fallback-v1"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    google_api_key: str | None = None
    google_model: str = "gemini-3.1-flash-lite"
    groq_api_key: str | None = None
    max_refinement_cycles: int = 2
    mcp_server_command: str = "python"
    mcp_server_script: str = "app/mcp_server.py"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
