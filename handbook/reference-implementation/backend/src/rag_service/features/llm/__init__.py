"""LLM gateway feature. Import from here; see README.md in this folder for how to use it."""

from rag_service.features.llm.config import GatewayConfig, load_gateway_config
from rag_service.features.llm.errors import (
    AllTargetsFailed,
    BudgetExceeded,
    ContentRefused,
    InvalidRequest,
    LlmError,
    PolicyViolation,
)
from rag_service.features.llm.gateway import LlmGateway, build_gateway
from rag_service.features.llm.types import (
    ChatRequest,
    ChatResult,
    EmbedRequest,
    EmbedResult,
    Message,
    Sensitivity,
    StreamEnd,
    StreamEvent,
    TextDelta,
    Usage,
)

__all__ = [
    "AllTargetsFailed",
    "BudgetExceeded",
    "ChatRequest",
    "ChatResult",
    "ContentRefused",
    "EmbedRequest",
    "EmbedResult",
    "GatewayConfig",
    "InvalidRequest",
    "LlmError",
    "LlmGateway",
    "Message",
    "PolicyViolation",
    "Sensitivity",
    "StreamEnd",
    "StreamEvent",
    "TextDelta",
    "Usage",
    "build_gateway",
    "load_gateway_config",
]
