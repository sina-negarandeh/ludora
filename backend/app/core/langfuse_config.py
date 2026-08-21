"""Registers the shared Langfuse client explicitly from Settings, rather
than mutating the process environment for the SDK to discover
credentials implicitly.

langfuse.openai's drop-in OpenAI wrapper (app.services.assistant_service)
looks up this client lazily via get_client() on each call -- confirmed
directly against the installed SDK (langfuse/_client/get_client.py):
constructing Langfuse(public_key=...) registers itself in
LangfuseResourceManager._instances, and a later no-argument get_client()
call returns that sole registered instance. Settings defaults
LANGFUSE_PUBLIC_KEY/SECRET_KEY to "" (matching this project's other
optional-infra settings, e.g. OPENAI_API_KEY), not None, so this module
does the "" -> None translation once here, since the SDK's own
Optional[str] = None constructor typing checks `is None` -- passing ""
straight through would skip its "not configured" no-op path.

Idempotent (module-level guard): safe to call from
AssistantService.__init__ on every request, not just once at app
startup, so a standalone script that never imports app.main (e.g.
backend/test_assistant.py) still gets a correctly-configured client.
"""
from langfuse import Langfuse

from app.core.config import settings

_configured = False


def configure_langfuse() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY or None,
        secret_key=settings.LANGFUSE_SECRET_KEY or None,
        host=settings.LANGFUSE_BASE_URL,
    )
