from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+psycopg2://finresearch:finresearch@localhost:5432/finresearch"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    LOG_LEVEL: str = "INFO"
    SEC_USER_AGENT: str = "FinResearch vakil.ad@northeastern.edu"
    RERANK_ENABLED: bool = False
    VECTOR_SEARCH_LIMIT: int = 20
    HYBRID_ALPHA: float = 0.5
    APP_ENV: str = "development"


settings = Settings()
