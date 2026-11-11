"""How a request obtains its verified Identity.

DEVELOPMENT ONLY until authentication (component 13): when ``RAG_DEV_IDENTITY_ENABLED`` is true the
caller's identity is read from ``X-Dev-Tenant``, ``X-Dev-User`` and ``X-Dev-Groups`` headers. Anyone who
can send a request can claim any identity, so this must never be enabled outside local development; the
settings validator refuses it in production and the dependency refuses it again at request time.
Component 13 replaces this function with token validation; callers depend only on the returned Identity.
"""

from __future__ import annotations

from fastapi import Request
from pydantic import ValidationError

from rag_service.core.config import Settings
from rag_service.core.errors import AppError
from rag_service.db.identity import Identity


def get_identity(request: Request) -> Identity:
    settings: Settings = request.app.state.settings
    if settings.is_production or not settings.dev_identity_enabled:
        raise AppError("unauthenticated", "Authentication required", 401)
    tenant = request.headers.get("x-dev-tenant")
    user = request.headers.get("x-dev-user")
    if not tenant or not user:
        raise AppError("unauthenticated", "Authentication required", 401)
    groups = tuple(g for g in request.headers.get("x-dev-groups", "").split(",") if g)
    try:
        return Identity(tenant_id=tenant, user_id=user, groups=groups)  # type: ignore[arg-type]
    except ValidationError:
        raise AppError("unauthenticated", "Authentication required", 401) from None
