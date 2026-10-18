"""Error taxonomy for AI providers and gateway failover."""


class AIProviderError(RuntimeError):
    """Base error for all AI provider operations."""
    pass


class AIProviderTimeoutError(AIProviderError):
    """Raised when an AI provider times out."""
    pass


class AIProviderRateLimitError(AIProviderError):
    """Raised when an AI provider returns HTTP 429 / RESOURCE_EXHAUSTED."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AIProviderAuthError(AIProviderError):
    """Raised on authentication or permission failure (401/403)."""
    pass


class AIProviderInvalidRequestError(AIProviderError):
    """Raised on invalid request, schema, or model (400/404)."""
    pass


class AIProviderUnavailableError(AIProviderError):
    """Raised when a provider is unreachable, 5xx, or all failover options are exhausted."""
    pass


class AIPaidProviderBlockedError(AIProviderError):
    """Raised when a paid provider is invoked but AI_ALLOW_PAID_APIS=false."""
    pass
