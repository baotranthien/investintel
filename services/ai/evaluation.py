from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from .config import OllamaConfig
from .providers import OllamaProvider
from .tools import AITools, TOOL_NAMES


class AIEvaluationFramework:
    """Deterministic guard checks; runtime availability is reported separately."""

    def __init__(self, session: Session):
        self.session = session

    def run_all(self) -> dict[str, Any]:
        results = []
        expected_tools = {
            "asset", "fundamentals", "valuation", "factors", "risk", "macro", "regime",
            "events", "opportunity", "portfolio", "watchlist", "historical_snapshot",
            "evidence", "document_retrieval",
        }
        results.append({
            "test_id": "TOOLS_001",
            "passed": expected_tools.issubset(set(TOOL_NAMES)),
            "detail": "Whitelisted AI tool catalog covers requested research domains.",
        })

        unknown = AITools.get_stock_snapshot("UNREGISTERED_AI_EVAL_SYMBOL", session=self.session)
        results.append({
            "test_id": "GROUND_001",
            "passed": unknown.get("status") == "INSUFFICIENT_DATA" and unknown.get("opportunity_score") is None and unknown.get("risk_score") is None,
            "detail": "Unregistered assets produce insufficient data without model scores.",
        })

        document_context = AITools.get_context(
            symbol=None,
            as_of=date.today(),
            tool_names=["document_retrieval"],
            session=self.session,
        )
        document_result = document_context["tools"][0]
        results.append({
            "test_id": "RAG_001",
            "passed": document_result["status"] == "INSUFFICIENT_DATA",
            "detail": "Document retrieval stays unavailable until the Phase 6G index exists.",
        })

        try:
            OllamaConfig(base_url="https://remote.example")
            local_only = False
        except ValueError:
            local_only = True
        results.append({
            "test_id": "PRIVACY_001",
            "passed": local_only,
            "detail": "Non-loopback LLM endpoints are rejected to protect personal portfolio data.",
        })

        runtime = OllamaProvider().status()
        passed = sum(1 for result in results if result["passed"])
        return {
            "eval_version": "6f_guardrails_v1",
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "verdict": "PASS" if passed == len(results) else "FAIL",
            "runtime": runtime,
            "results": results,
            "runtime_note": "Guardrail PASS does not imply Ollama inference or analyst quality was benchmarked.",
        }