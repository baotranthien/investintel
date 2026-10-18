from dataclasses import dataclass
from ipaddress import ip_address
import os
from urllib.parse import urlparse, urlunparse


def _is_loopback_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.hostname.lower() == "localhost":
        return True
    try:
        return ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    fast_model: str = "qwen2.5:0.5b"
    primary_model: str = "qwen2.5:0.5b"
    reasoning_model: str = "qwen2.5:0.5b"
    timeout_seconds: float = 75.0
    connect_timeout_seconds: float = 3.0
    retries: int = 1
    num_ctx: int = 2048
    num_predict: int = 512
    keep_alive: str = "5m"

    def __post_init__(self) -> None:
        if not _is_loopback_url(self.base_url):
            raise ValueError("Ollama must use a loopback URL; external model endpoints are blocked for privacy.")
        if not all((self.fast_model.strip(), self.primary_model.strip(), self.reasoning_model.strip())):
            raise ValueError("Ollama model names must not be empty.")
        if self.timeout_seconds <= 0 or self.connect_timeout_seconds <= 0:
            raise ValueError("Ollama timeouts must be positive.")
        if self.retries < 0 or self.retries > 2:
            raise ValueError("Ollama retries must be between 0 and 2.")
        if self.num_ctx < 256 or self.num_predict < 1:
            raise ValueError("Ollama context and output limits are outside the supported range.")

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        default_model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
        configured_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed_url = urlparse(configured_url)
        if parsed_url.hostname and parsed_url.hostname.lower() == "localhost":
            netloc = f"127.0.0.1:{parsed_url.port}" if parsed_url.port else "127.0.0.1"
            configured_url = urlunparse(parsed_url._replace(netloc=netloc)).rstrip("/")
        return cls(
            base_url=configured_url,
            fast_model=os.getenv("OLLAMA_FAST_MODEL", default_model),
            primary_model=os.getenv("OLLAMA_PRIMARY_MODEL", default_model),
            reasoning_model=os.getenv("OLLAMA_REASONING_MODEL", default_model),
            timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "75")),
            connect_timeout_seconds=float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "3")),
            retries=int(os.getenv("OLLAMA_RETRIES", "1")),
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "2048")),
            num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "512")),
            keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "5m"),
        )


def redact_secrets(text: str) -> str:
    """Scrub potential API keys or tokens from string to prevent logging secrets."""
    if not text:
        return text
    # Redact known environment keys if present
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and len(gemini_key) > 6:
        text = text.replace(gemini_key, "[REDACTED_GEMINI_KEY]")
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and len(openai_key) > 6:
        text = text.replace(openai_key, "[REDACTED_OPENAI_KEY]")
    # Redact generic authorization or key patterns
    import re
    text = re.sub(r"(AIza[0-9A-Za-z-_]{30,})", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(AQ\.[0-9A-Za-z-_]{15,})", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(sk-[0-9A-Za-z-_]{20,})", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(bearer\s+)[0-9A-Za-z-_\.]+", r"\1[REDACTED_TOKEN]", text, flags=re.IGNORECASE)
    text = re.sub(r"(api[_-]?key[\"'\s:=]+)[0-9A-Za-z-_\.]+", r"\1[REDACTED_KEY]", text, flags=re.IGNORECASE)
    return text


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str | None = None
    model: str = "gemini-3.8-flash"
    fallback_model: str = "gemini-3.6-flash"
    preview_model: str = "gemini-3-flash-preview"
    enable_preview_models: bool = False
    enabled: bool = True
    timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 5.0
    # Retries for the primary model. Together with the initial attempt = 5 total (capped by MAX_GEMINI_UPSTREAM_ATTEMPTS).
    retries: int = 4
    max_output_tokens: int = 2048
    temperature: float = 0.2
    allow_paid_apis: bool = False
    monthly_budget_usd: float = 0.0

    @property
    def is_configured(self) -> bool:
        if not self.enabled or not self.api_key:
            return False
        clean = self.api_key.strip()
        if not clean or clean.startswith("PASTE_") or clean == "NOT_CONFIGURED":
            return False
        return True

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        raw_key = os.getenv("GEMINI_API_KEY")
        key = raw_key.strip() if raw_key else None
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
        fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
        preview_model = os.getenv("GEMINI_PREVIEW_MODEL", "gemini-3-flash-preview").strip() or "gemini-3-flash-preview"
        enable_preview = os.getenv("GEMINI_ENABLE_PREVIEW_MODELS", "false").lower() in ("true", "1", "yes")
        enabled_str = os.getenv("GEMINI_ENABLED", "true").lower()
        enabled = enabled_str in ("true", "1", "yes")
        allow_paid = os.getenv("AI_ALLOW_PAID_APIS", "false").lower() in ("true", "1", "yes")
        try:
            budget = float(os.getenv("AI_MONTHLY_BUDGET_USD", "0"))
        except ValueError:
            budget = 0.0
        return cls(
            api_key=key,
            model=model,
            fallback_model=fallback_model,
            preview_model=preview_model,
            enable_preview_models=enable_preview,
            enabled=enabled,
            timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30")),
            connect_timeout_seconds=float(os.getenv("GEMINI_CONNECT_TIMEOUT_SECONDS", "5")),
            retries=int(os.getenv("GEMINI_RETRIES", "4")),
            max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048")),
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
            allow_paid_apis=allow_paid,
            monthly_budget_usd=budget,
        )


@dataclass(frozen=True)
class GatewayConfig:
    provider_priority: tuple[str, ...] = ("gemini", "groq", "openrouter", "ollama")
    cooldown_seconds: float = 60.0
    transient_cooldown_seconds: float = 30.0
    # Five total HTTP attempts including the initial request (not five retries plus initial).
    # Controlled by MAX_GEMINI_UPSTREAM_ATTEMPTS env var.
    max_upstream_attempts: int = 5

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        order_env = os.getenv("AI_PROVIDER_ORDER")
        if order_env:
            providers = tuple(p.strip().lower() for p in order_env.split(",") if p.strip())
        else:
            providers = ("gemini", "groq", "openrouter", "ollama")
        # MAX_GEMINI_UPSTREAM_ATTEMPTS: five total HTTP attempts (initial + up to 4 retries)
        max_attempts = int(
            os.getenv("MAX_GEMINI_UPSTREAM_ATTEMPTS")
            or os.getenv("AI_GATEWAY_MAX_UPSTREAM_ATTEMPTS")
            or "5"
        )
        return cls(
            provider_priority=providers,
            cooldown_seconds=float(os.getenv("AI_GATEWAY_COOLDOWN_SECONDS", "60")),
            transient_cooldown_seconds=float(os.getenv("AI_GATEWAY_TRANSIENT_COOLDOWN_SECONDS", "30")),
            max_upstream_attempts=max_attempts,
        )