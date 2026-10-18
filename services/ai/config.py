from dataclasses import dataclass
from ipaddress import ip_address
import os
import re
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
        default_model = (
            os.getenv("OLLAMA_MODEL")
            or os.getenv("OLLAMA_DEFAULT_MODEL")
            or os.getenv("OLLAMA_PRIMARY_MODEL")
            or "qwen2.5:0.5b"
        ).strip()
        configured_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed_url = urlparse(configured_url)
        if parsed_url.hostname and parsed_url.hostname.lower() == "localhost":
            netloc = f"127.0.0.1:{parsed_url.port}" if parsed_url.port else "127.0.0.1"
            configured_url = urlunparse(parsed_url._replace(netloc=netloc)).rstrip("/")
        return cls(
            base_url=configured_url,
            fast_model=os.getenv("OLLAMA_FAST_MODEL", default_model).strip() or default_model,
            primary_model=os.getenv("OLLAMA_PRIMARY_MODEL", default_model).strip() or default_model,
            reasoning_model=os.getenv("OLLAMA_REASONING_MODEL", default_model).strip() or default_model,
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
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and len(openai_key) > 6:
        text = text.replace(openai_key, "[REDACTED_OPENAI_KEY]")
    # Redact generic authorization or key patterns
    text = re.sub(r"(AIza[0-9A-Za-z-_]{30,})", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(AQ\.[0-9A-Za-z-_]{15,})", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(sk-[0-9A-Za-z-_]{20,})", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(bearer\s+)[0-9A-Za-z-_\.]+", r"\1[REDACTED_TOKEN]", text, flags=re.IGNORECASE)
    text = re.sub(r"(api[_-]?key[\"'\s:=]+)[0-9A-Za-z-_\.]+", r"\1[REDACTED_KEY]", text, flags=re.IGNORECASE)
    return text


@dataclass(frozen=True)
class GatewayConfig:
    provider_priority: tuple[str, ...] = ("ollama",)
    cooldown_seconds: float = 60.0
    transient_cooldown_seconds: float = 30.0
    max_upstream_attempts: int = 2

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        order_env = os.getenv("AI_PROVIDER_ORDER")
        if order_env:
            providers = tuple(
                p.strip().lower()
                for p in order_env.split(",")
                if p.strip() and p.strip().lower() == "ollama"
            )
            if not providers:
                providers = ("ollama",)
        else:
            providers = ("ollama",)
        max_attempts = int(os.getenv("AI_GATEWAY_MAX_UPSTREAM_ATTEMPTS", "2"))
        return cls(
            provider_priority=providers,
            cooldown_seconds=float(os.getenv("AI_GATEWAY_COOLDOWN_SECONDS", "60")),
            transient_cooldown_seconds=float(os.getenv("AI_GATEWAY_TRANSIENT_COOLDOWN_SECONDS", "30")),
            max_upstream_attempts=max_attempts,
        )