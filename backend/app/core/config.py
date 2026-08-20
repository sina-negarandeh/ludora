from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://ludora:ludorapassword@localhost:5432/ludoradb"

    # Local OpenAI-compatible LLM server for the AI Assistant — live,
    # request-time calls from the chat sidebar. Infra knobs, not ML
    # hyperparameters — see app.core.ml_config for those.
    OPENAI_BASE_URL: str = "http://localhost:8080/v1"
    OPENAI_API_KEY: str = "not-needed-for-local"
    # Used by AssistantService.parse_query() -- single-shot, single-intent
    # JSON classification, exercised directly only by the /parse debug
    # route today (the live /chat path uses PLAN_MODEL_NAME below for
    # everything, single-step requests included). Kept small: this task
    # has never shown a reliability problem at this size.
    LLM_MODEL_NAME: str = "Qwen/Qwen3-4B-MLX-4bit"
    # Used by AssistantService.parse_plan() -- the model actually serving
    # /api/assistant/chat. Deliberately the larger reasoning-capable
    # model, not the small one above: parse_plan() has to decide whether
    # a request decomposes into multiple dependent steps and keep a
    # multi-object JSON plan structurally correct, and measured directly
    # against this server the small model produced real, repeated
    # failures on that harder task (a structural JSON bug, and more than
    # one intent misclassification) that the larger model didn't. Latency
    # is not a constraint for this project, so there's no reason to trade
    # correctness for speed here.
    PLAN_MODEL_NAME: str = "Qwen/Qwen3-30B-A3B-MLX-4bit"

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
