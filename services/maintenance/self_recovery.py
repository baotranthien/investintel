"""
InvestIntel Local Monitoring, Structured Logging & Self-Recovery Engine
Phase 6F: Error Classification, Safe Remediation Handlers, and Operational Runbooks.
"""

import enum
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ErrorCategory(str, enum.Enum):
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    DATA_PROVIDER_FAILURE = "DATA_PROVIDER_FAILURE"
    OLLAMA_MODEL_FAILURE = "OLLAMA_MODEL_FAILURE"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    BACKGROUND_JOB_FAILURE = "BACKGROUND_JOB_FAILURE"
    STORAGE_FAILURE = "STORAGE_FAILURE"
    UNKNOWN = "UNKNOWN"


ERROR_RUNBOOK: Dict[ErrorCategory, Dict[str, Any]] = {
    ErrorCategory.SERVICE_UNAVAILABLE: {
        "severity": "CRITICAL",
        "description": "One of the local services (FastAPI, Next.js, or Ollama) is not responding on its designated port.",
        "safe_auto_recovery": "Verify project process ownership and restart the specific stopped service.",
        "runbook_instruction": "Run .\\Start-InvestIntel.bat or scripts\\local\\doctor-investintel.ps1 to diagnose port conflicts.",
    },
    ErrorCategory.DATABASE_FAILURE: {
        "severity": "CRITICAL",
        "description": "Local SQLite database failed integrity check or connection error occurred.",
        "safe_auto_recovery": "Re-attempt connection with exponential backoff up to 3 times; roll back uncommitted transactions.",
        "runbook_instruction": "Run .\\scripts\\local\\restore-investintel-db.ps1 -Latest to restore from verified snapshot.",
    },
    ErrorCategory.DATA_PROVIDER_FAILURE: {
        "severity": "WARNING",
        "description": "External market data provider returned HTTP 4xx/5xx or timed out.",
        "safe_auto_recovery": "Graceful fallback to local HOSE CSV cache; abort downstream opportunity scanning to prevent stale data masking.",
        "runbook_instruction": "Check network connectivity or retry after stock exchange maintenance window.",
    },
    ErrorCategory.OLLAMA_MODEL_FAILURE: {
        "severity": "WARNING",
        "description": "Ollama is running but primary model qwen3.5:9b-q4_K_M is not loaded or missing.",
        "safe_auto_recovery": "Send warm-up ping to trigger model layer allocation into GPU VRAM.",
        "runbook_instruction": "Run 'ollama pull qwen3.5:9b-q4_K_M' and verify VRAM available via nvidia-smi.",
    },
    ErrorCategory.INFERENCE_TIMEOUT: {
        "severity": "WARNING",
        "description": "Local inference exceeded configured timeout (120s) under heavy VRAM/CPU contention.",
        "safe_auto_recovery": "Cancel stranded HTTP request; reduce prompt context window to 2048 tokens.",
        "runbook_instruction": "Close heavy 3D applications or games competing for the RTX 3050 GPU.",
    },
    ErrorCategory.INVALID_EVIDENCE: {
        "severity": "WARNING",
        "description": "Hallucination Guard or Evidence Grounding rejected LLM answer due to ungrounded claims.",
        "safe_auto_recovery": "Block ungrounded claims; return structured fallback metrics with explicit citations.",
        "runbook_instruction": "Ensure financial statement data has been ingested for the target ticker.",
    },
    ErrorCategory.BACKGROUND_JOB_FAILURE: {
        "severity": "WARNING",
        "description": "A scheduled background pipeline step encountered an exception.",
        "safe_auto_recovery": "Record failure in job history; increment retry count (max 3); release scheduler lock.",
        "runbook_instruction": "Inspect .run/job_history.json and trigger manual run via trigger-automation.ps1.",
    },
    ErrorCategory.STORAGE_FAILURE: {
        "severity": "CRITICAL",
        "description": "Disk space critically low (< 500MB) or backup directory inaccessible.",
        "safe_auto_recovery": "Prune old backups according to retention policy (preserving newest snapshot).",
        "runbook_instruction": "Free disk space on drive C: to ensure database snapshots can be persisted.",
    },
}


def classify_error(exc: Exception, context: str = "") -> Dict[str, Any]:
    """
    Classifies a runtime exception into an institutional ErrorCategory with recovery guidance.
    """
    msg = str(exc).lower()
    cat = ErrorCategory.UNKNOWN

    if "connection refused" in msg or "not responding" in msg or "10048" in msg or "socket" in msg:
        cat = ErrorCategory.SERVICE_UNAVAILABLE
    elif "sqlite" in msg or "database" in msg or "integrity" in msg or "corrupt" in msg:
        cat = ErrorCategory.DATABASE_FAILURE
    elif "timeout" in msg or "timed out" in msg:
        if "ollama" in msg or "generate" in msg:
            cat = ErrorCategory.INFERENCE_TIMEOUT
        else:
            cat = ErrorCategory.DATA_PROVIDER_FAILURE
    elif "provider" in msg or "entrade" in msg or "http 4" in msg or "http 5" in msg:
        cat = ErrorCategory.DATA_PROVIDER_FAILURE
    elif "model" in msg or "qwen" in msg or "not found" in msg:
        cat = ErrorCategory.OLLAMA_MODEL_FAILURE
    elif "hallucination" in msg or "citation" in msg or "grounding" in msg:
        cat = ErrorCategory.INVALID_EVIDENCE
    elif "disk" in msg or "space" in msg or "enospc" in msg:
        cat = ErrorCategory.STORAGE_FAILURE

    meta = ERROR_RUNBOOK.get(cat, {
        "severity": "WARNING",
        "description": f"Unhandled exception: {exc}",
        "safe_auto_recovery": "Log exception and notify operator.",
        "runbook_instruction": "Inspect logs/api.log for full stack trace.",
    })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": cat.value,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "context": context,
        "severity": meta["severity"],
        "description": meta["description"],
        "safe_auto_recovery": meta["safe_auto_recovery"],
        "runbook_instruction": meta["runbook_instruction"],
    }

