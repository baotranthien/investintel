from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import time
import os
import httpx
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    scheduler_task = None
    analyst_task = None
    
    # In cloud mode and pytest, in-process loops are disabled; cron-job.org triggers idempotent jobs on cloud
    is_pytest = "PYTEST_CURRENT_TEST" in os.environ
    is_cloud = os.getenv("CLOUD_MODE", "false").lower() in {"1", "true", "yes"} or os.getenv("APP_ENV") == "production"
    enable_in_process = os.getenv("ENABLE_IN_PROCESS_SCHEDULER", "false" if (is_cloud or is_pytest) else "true").lower() in {"1", "true", "yes"}
    
    if enable_in_process:
        if os.getenv("INGESTION_SCHEDULER_ENABLED", "true").lower() in {"1", "true", "yes"}:
            from services.ingestion.scheduler import scheduled_ingestion_loop
            scheduler_task = asyncio.create_task(scheduled_ingestion_loop(stop_event))
        if os.getenv("ANALYST_AUTOMATION_ENABLED", "false").lower() in {"1", "true", "yes"}:
            from services.ai.scheduler import scheduled_analyst_automation_loop
            analyst_task = asyncio.create_task(scheduled_analyst_automation_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        tasks = [t for t in (scheduler_task, analyst_task) if t is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Investment Intelligence API", version="0.1.0", lifespan=lifespan)

# Setup logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

from fastapi.middleware.cors import CORSMiddleware
from services.auth.middleware import AuthenticationMiddleware, get_allowed_origins

# 1. Custom Authentication & CSRF & Private Cache-Control Middleware
app.add_middleware(AuthenticationMiddleware)

# 2. CORS allowlist
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

try:
    from routers import data, fundamentals, valuation, factors, macro, risk, events, opportunity, ai, market, research, portfolio, watchlist, decision, automation, auth, cron
except ImportError:
    from apps.api.routers import data, fundamentals, valuation, factors, macro, risk, events, opportunity, ai, market, research, portfolio, watchlist, decision, automation, auth, cron

app.include_router(auth.router)
app.include_router(cron.router)
app.include_router(data.router)
app.include_router(fundamentals.router)
app.include_router(valuation.router)
app.include_router(factors.router)
app.include_router(macro.router)
app.include_router(risk.router)
app.include_router(events.router)
app.include_router(opportunity.router)
app.include_router(ai.router)
app.include_router(market.router)
app.include_router(research.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(decision.router)
app.include_router(automation.router)

from database.connection import check_database_health, check_redis_health

# Middlewares (e.g. structured logging)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"method={request.method} path={request.url.path} status={response.status_code} duration={process_time:.4f}s")
    return response

@app.get("/health")
def health_check():
    db_health = check_database_health()
    if not db_health.get("connected"):
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": db_health})
    return {"status": "ok"}

@app.get("/api/v1/health")
def health_check_v1():
    db_health = check_database_health()
    redis_health = check_redis_health()
    if not db_health.get("connected"):
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": "Database connection failed",
                "database": db_health,
                "redis": redis_health
            }
        )
    return {
        "status": "ok",
        "message": "API is healthy",
        "database": db_health,
        "redis": redis_health
    }

@app.get("/api/v1/system/info")
async def system_info():
    db_health = check_database_health()
    redis_health = check_redis_health()
    ai_status = "AI unavailable / AI tạm thời không khả dụng"
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Ping ollama
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{ollama_base}/api/tags")
            if resp.status_code == 200:
                ai_status = "AI available"
    except Exception:
        pass

    db_status_str = f"connected ({db_health.get('backend')}, {db_health.get('latency_ms')}ms)" if db_health.get("connected") else f"error ({db_health.get('error', 'disconnected')})"
    redis_status_str = f"connected ({redis_health.get('latency_ms')}ms)" if redis_health.get("connected") else f"error ({redis_health.get('error', 'disconnected')})"

    return {
        "version": "0.1.0",
        "environment": os.getenv("APP_ENV", "development"),
        "timestamp": time.time(),
        "database_status": db_status_str,
        "database_health": db_health,
        "redis_status": redis_status_str,
        "redis_health": redis_health,
        "ai_provider_status": ai_status
    }


@app.get("/api/v1/system/observability")
async def system_observability():
    db_health = check_database_health()
    redis_health = check_redis_health()

    # Database status
    if not db_health.get("connected"):
        db_status = "UNAVAILABLE"
    elif db_health.get("backend") == "sqlite" and os.getenv("DATABASE_URL", "").startswith("postgres"):
        db_status = "DEGRADED"
    else:
        db_status = "HEALTHY"

    # Redis status
    if not redis_health.get("connected"):
        redis_status = "NOT_CONFIGURED" if redis_health.get("status") == "not_configured" else "UNAVAILABLE"
    else:
        redis_status = "HEALTHY"

    # AI Provider status
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ai_status = "UNAVAILABLE"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{ollama_base}/api/tags")
            if resp.status_code == 200:
                ai_status = "HEALTHY"
    except Exception:
        ai_status = "UNAVAILABLE"

    # Background Job & Data Freshness statistics
    job_stats = {"total": 0, "success": 0, "failed": 0, "running": 0}
    ingestion_stats = {"total_runs": 0, "successful_runs": 0, "failed_runs": 0}
    freshness = {"latest_price_date": None, "latest_macro_date": None}

    if db_health.get("connected"):
        try:
            from database.models import AnalystAutomationJob, DataRun, Price, MacroObservation
            from database.connection import SessionLocal
            session = SessionLocal()
            try:
                from sqlalchemy import func
                job_stats["total"] = session.query(AnalystAutomationJob).count()
                job_stats["success"] = session.query(AnalystAutomationJob).filter_by(status="SUCCESS").count()
                job_stats["failed"] = session.query(AnalystAutomationJob).filter_by(status="FAILED").count()
                job_stats["running"] = session.query(AnalystAutomationJob).filter_by(status="RUNNING").count()

                ingestion_stats["total_runs"] = session.query(DataRun).count()
                ingestion_stats["successful_runs"] = session.query(DataRun).filter_by(status="SUCCESS").count()
                ingestion_stats["failed_runs"] = session.query(DataRun).filter_by(status="FAILURE").count()

                latest_price = session.query(func.max(Price.observation_date)).scalar()
                if latest_price:
                    freshness["latest_price_date"] = latest_price.isoformat()

                latest_macro = session.query(func.max(MacroObservation.observation_date)).scalar()
                if latest_macro:
                    freshness["latest_macro_date"] = latest_macro.isoformat()
            finally:
                session.close()
        except Exception:
            pass

    overall = "HEALTHY"
    if db_status == "UNAVAILABLE":
        overall = "UNAVAILABLE"
    elif db_status == "DEGRADED" or ai_status == "UNAVAILABLE" or job_stats["failed"] > 0:
        overall = "DEGRADED"

    return {
        "status": overall,
        "components": {
            "database": {
                "status": db_status,
                "backend": db_health.get("backend", "unknown"),
                "latency_ms": db_health.get("latency_ms"),
            },
            "redis": {
                "status": redis_status,
                "latency_ms": redis_health.get("latency_ms"),
            },
            "ai_provider": {
                "status": ai_status,
                "provider": "Ollama",
                "endpoint": ollama_base,
            },
        },
        "background_jobs": job_stats,
        "ingestion": ingestion_stats,
        "data_freshness": freshness,
        "environment": os.getenv("APP_ENV", "development"),
        "timestamp": time.time(),
    }

