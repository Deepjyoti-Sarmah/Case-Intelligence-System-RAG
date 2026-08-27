from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    debug_trace: bool = False

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/rag"

    # LLM
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-5"
    anthropic_api_key: str | None = None

    # Embeddings / Reranker
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_provider: str = "local"
    reranker_model: str = "BAAI/bge-reranker-base"
    enable_reranker: bool = True

    # Retrieval tuning
    top_k_lexical: int = 30
    top_k_dense: int = 30
    top_k_rerank: int = 10
    max_context_tokens: int = 8000
    rrf_k: int = 60


settings = Settings()
