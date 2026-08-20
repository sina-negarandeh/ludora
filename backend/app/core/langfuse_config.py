"""Bridges Settings' LANGFUSE_* fields into the process environment, since
the langfuse SDK (both the `langfuse.openai` drop-in client and the
Langfuse() client it looks up internally) reads its credentials via
os.environ directly, not via this app's pydantic-settings object --
pydantic-settings loads backend/.env into Settings' own fields, it
doesn't mutate os.environ for other libraries to see.

Only sets them when both keys are actually present: setting
LANGFUSE_PUBLIC_KEY to an empty string would NOT trigger the SDK's own
"no key configured, disable tracing" branch (it checks `is None`, and
`"" or os.environ.get(...)` already short-circuits past a falsy default
before that check even runs) -- omitting the env var entirely is what
correctly reaches that graceful no-op path.
"""
import os

from app.core.config import settings


def configure_langfuse() -> None:
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_BASE_URL"] = settings.LANGFUSE_BASE_URL
