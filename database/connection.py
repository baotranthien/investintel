import logging
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base

logger = logging.getLogger(__name__)

# Load environment variables from .env if present
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "trading.db"
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


class DatabaseConnectionError(RuntimeError):
    """Raised when database connection establishment fails or times out."""
    pass


class DatabaseQuotaError(Exception):
    """Raised when database storage quota or maximum connections are exceeded."""
    pass


def is_cloud_mode() -> bool:
    return (
        os.getenv("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
        or os.getenv("APP_ENV", "development").lower() == "production"
    )


def normalize_database_url(url: str) -> str:
    """Normalize legacy postgres:// or add SSL requirements if remote."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def get_database_url() -> str:
    raw_env_url = os.getenv("DATABASE_URL")
    env_url = normalize_database_url(raw_env_url)

    # In cloud mode, SQLite fallback is strictly forbidden
    if is_cloud_mode():
        if not env_url or env_url == "NOT_CONFIGURED" or env_url.startswith("sqlite"):
            raise RuntimeError(
                "Cloud mode requires a valid PostgreSQL DATABASE_URL. Refusing to run or fall back to SQLite in cloud mode."
            )

    if not env_url or env_url == "NOT_CONFIGURED":
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return DEFAULT_SQLITE_URL

    if env_url.startswith("postgresql"):
        # Neon cold-start resilience: bounded retry for connection establishment
        max_attempts = int(os.getenv("DB_CONNECT_RETRIES", "3"))
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                import psycopg2
                conn = psycopg2.connect(dsn=env_url, connect_timeout=4)
                conn.close()
                return env_url
            except Exception as exc:
                last_exc = exc
                err_msg = str(exc).lower()
                if "quota" in err_msg or "exceeded" in err_msg:
                    logger.error(f"Neon database quota error detected: {exc}")
                    raise DatabaseQuotaError(f"Database quota exceeded: {exc}") from exc
                logger.warning(
                    f"PostgreSQL connection attempt {attempt}/{max_attempts} failed (possible cold start): {exc}"
                )
                if attempt < max_attempts:
                    time.sleep(1.5 * attempt)

        raise DatabaseConnectionError(
            "Configured PostgreSQL is unavailable after cold-start retries; refusing to fall back to SQLite."
        ) from last_exc

    return env_url


DATABASE_URL = get_database_url()

engine_kwargs = {"echo": False, "future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql"):
    # Conservative pool limits suitable for Neon Free (20 max connections)
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "300"))

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def check_database_health() -> dict:
    """Check actual database health and latency."""
    t0 = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.time() - t0) * 1000, 2)
        backend = "postgresql" if "postgresql" in DATABASE_URL else "sqlite"
        return {
            "status": "healthy",
            "backend": backend,
            "latency_ms": latency_ms,
            "connected": True
        }
    except Exception as e:
        err_msg = str(e).lower()
        status_name = "quota_exceeded" if ("quota" in err_msg or "limit" in err_msg) else "unhealthy"
        return {
            "status": status_name,
            "error": str(e),
            "connected": False
        }


def check_redis_health() -> dict:
    """Check actual Redis health and latency with timeout and graceful failure."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url or redis_url == "NOT_CONFIGURED":
        return {
            "status": "not_configured",
            "connected": False,
            "message": "REDIS_URL is not configured"
        }
    try:
        import redis
        t0 = time.time()
        r = redis.from_url(redis_url, socket_timeout=1.5, socket_connect_timeout=1.5)
        is_ok = r.ping()
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "status": "healthy" if is_ok else "unhealthy",
            "latency_ms": latency_ms,
            "connected": bool(is_ok)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e)
        }


ALLOW_PRODUCTION_DB_WRITE = os.getenv("ALLOW_PRODUCTION_DB_WRITE", "false").lower() in ("1", "true", "yes")


def is_production_database_target() -> bool:
    """Returns True if DATABASE_URL points to the Neon cloud PostgreSQL production cluster."""
    url = os.getenv("DATABASE_URL", "").lower()
    return "neon.tech" in url or "ep-" in url
