from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://ludora:ludorapassword@localhost:5432/ludoradb"

    # Local OpenAI-compatible LLM server (assistant + summarization services).
    # Infra knobs, not ML hyperparameters — see app.core.ml_config for those.
    OPENAI_BASE_URL: str = "http://localhost:8080/v1"
    OPENAI_API_KEY: str = "not-needed-for-local"
    LLM_MODEL_NAME: str = "Qwen/Qwen3-30B-A3B-MLX-4bit"

    class Config:
        env_file = ".env"

settings = Settings()
