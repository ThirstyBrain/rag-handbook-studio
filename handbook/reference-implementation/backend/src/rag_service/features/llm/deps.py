"""FastAPI dependency: how any feature obtains the gateway.

from typing import Annotated
from fastapi import Depends
from rag_service.features.llm.deps import get_llm_gateway
from rag_service.features.llm import LlmGateway

async def handler(llm: Annotated[LlmGateway, Depends(get_llm_gateway)]): ...
"""

from __future__ import annotations

from fastapi import Request

from rag_service.core.errors import AppError
from rag_service.features.llm.gateway import LlmGateway


def get_llm_gateway(request: Request) -> LlmGateway:
    gateway: LlmGateway | None = getattr(request.app.state, "llm_gateway", None)
    if gateway is None:
        raise AppError(
            "llm_not_configured",
            "No LLM gateway is configured",
            503,
            "Set RAG_LLM_CONFIG_FILE to a gateway configuration file.",
        )
    return gateway
