from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://ludora:ludorapassword@localhost:5432/ludoradb"

    # Local OpenAI-compatible LLM server for the AI Assistant — live,
    # request-time calls from the chat sidebar. Infra knobs, not ML
    # hyperparameters — see app.core.ml_config for those.
    OPENAI_BASE_URL: str = "http://localhost:8080/v1"
    OPENAI_API_KEY: str = "not-needed-for-local"
    LLM_MODEL_NAME: str = "Qwen/Qwen3-30B-A3B-MLX-4bit"

    # Separate config for summarization (scripts/generate_summaries.py) —
    # deliberately not shared with the assistant settings above. Summarization
    # is an offline, precomputed batch job; the assistant serves live user
    # requests. Keeping them independent means a batch run can point at a
    # different server/instance (or just a different, faster model) without
    # ever needing to agree with what's serving live traffic.
    SUMMARIZATION_OPENAI_BASE_URL: str = "http://localhost:8080/v1"
    SUMMARIZATION_OPENAI_API_KEY: str = "not-needed-for-local"
    SUMMARIZATION_MODEL_NAME: str = "Qwen/Qwen3-4B-MLX-4bit"

    class Config:
        env_file = ".env"

settings = Settings()
