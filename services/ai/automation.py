from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from database.models import AnalystBrief, WatchlistItem


class AnalystAutomationService:
    """Background-oriented analyst automation service for 6H briefs, thesis monitoring, and alerts."""

    def __init__(self, session: Session | None = None):
        self.session = session

    @staticmethod
    def _claim_type_for(item: dict[str, Any]) -> str:
        claim_type = item.get("claim_type")
        if claim_type in {"FACT", "MODEL_OUTPUT", "INTERPRETATION", "HYPOTHESIS", "UNCERTAINTY"}:
            return claim_type
        if item.get("source") and item.get("data_origin") not in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}:
            return "FACT"
        if item.get("freshness") in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}:
            return "UNCERTAINTY"
        return "MODEL_OUTPUT"

    @staticmethod
    def _is_evidence_usable(item: dict[str, Any] | None) -> bool:
        if not item:
            return False
        if not item.get("source"):
            return False
        if item.get("data_origin") in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}:
            return False
        if item.get("freshness") in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}:
            return False
        return True

    def generate_brief(self, brief_type: str, symbol: str | None, as_of: date, context: dict[str, Any]) -> dict[str, Any]:
        evidence = context.get("evidence") or []
        usable = [item for item in evidence if self._is_evidence_usable(item)]
        if brief_type in {"DAILY", "WEEKLY", "MONTHLY"} and not usable:
            return {
                "brief_type": brief_type,
                "status": "INSUFFICIENT_DATA",
                "symbol": symbol,
                "as_of_date": as_of.isoformat(),
                "sections": {},
                "claims": [],
                "uncertainty": ["No source-backed evidence is available for this brief."],
            }

        sections = {
            "market": context.get("market", {}),
            "regime": context.get("regime", {}),
            "macro": context.get("macro", {}),
            "events": context.get("events", []),
            "portfolio": context.get("portfolio", {}),
            "opportunities": context.get("opportunities", context.get("portfolio", {})),
        }

        claims = []
        for item in usable[:5]:
            metric = item.get("metric") or item.get("responsible_module") or "evidence"
            value = item.get("value")
            claims.append({
                "claim_type": self._claim_type_for(item),
                "text": f"{metric}: {value!s} (as of {item.get('observation_date') or as_of.isoformat()}).",
                "citation_ids": [f"B-{hashlib.sha1(str(item).encode('utf-8')).hexdigest()[:8]}"],
                "source": item.get("source"),
                "value": value,
                "metric": metric,
            })

        if not claims:
            return {
                "brief_type": brief_type,
                "status": "INSUFFICIENT_DATA",
                "symbol": symbol,
                "as_of_date": as_of.isoformat(),
                "sections": sections,
                "claims": [],
                "uncertainty": ["No qualified evidence could be mapped to a claim."],
            }

        return {
            "brief_type": brief_type,
            "status": "AVAILABLE",
            "symbol": symbol,
            "as_of_date": as_of.isoformat(),
            "sections": sections,
            "claims": claims,
            "uncertainty": [],
        }

    @staticmethod
    def detect_snapshot_changes(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        changes: dict[str, Any] = {}

        def walk(prefix: str, prev: Any, curr: Any) -> None:
            if isinstance(prev, dict) and isinstance(curr, dict):
                for key in sorted(set(prev) | set(curr)):
                    next_prefix = f"{prefix}.{key}" if prefix else str(key)
                    if key in prev and key in curr:
                        walk(next_prefix, prev[key], curr[key])
                    elif key in prev:
                        changes[next_prefix] = {"previous": prev[key], "current": None}
                    else:
                        changes[next_prefix] = {"previous": None, "current": curr[key]}
                return

            if prev != curr:
                changes[prefix] = {"previous": prev, "current": curr}

        walk("", previous, current)
        return changes

    def monitor_thesis(
        self,
        watchlist_item: WatchlistItem,
        *,
        evidence: list[dict[str, Any]],
        contradicting_evidence: list[dict[str, Any]],
        catalysts: list[str],
        invalidation: str | None,
        confidence: float,
    ) -> dict[str, Any]:
        if not evidence:
            return {
                "status": "INSUFFICIENT_DATA",
                "thesis": watchlist_item.thesis,
                "confidence": confidence,
                "updated": False,
                "reason": "No source-backed supporting evidence is available to update the thesis.",
            }

        if not any(self._is_evidence_usable(item) for item in evidence):
            return {
                "status": "INSUFFICIENT_DATA",
                "thesis": watchlist_item.thesis,
                "confidence": confidence,
                "updated": False,
                "reason": "The supporting evidence is stale, untraced, or lacks a source.",
            }

        # Monitoring records a review; only a user-authored revision may change the thesis.
        watchlist_item.last_reviewed_at = datetime.utcnow()
        if self.session is not None:
            self.session.add(watchlist_item)
            self.session.commit()

        return {
            "status": "REVIEWED",
            "thesis": watchlist_item.thesis,
            "confidence": confidence,
            "updated": False,
            "evidence": evidence,
            "contradicting_evidence": contradicting_evidence,
            "catalysts": catalysts,
            "invalidation": invalidation,
            "last_reviewed_at": watchlist_item.last_reviewed_at.isoformat() if watchlist_item.last_reviewed_at else None,
        }

    @staticmethod
    def evaluate_alerts(
        context: dict[str, Any],
        *,
        previous: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]],
        prior_alerts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        prior_alerts = prior_alerts or []
        seen = {item.get("alert_id") for item in prior_alerts if item.get("alert_id")}
        alerts: list[dict[str, Any]] = []
        for metric_name in ["valuation", "risk", "opportunity"]:
            current = context.get(metric_name)
            before = (previous or {}).get(metric_name)
            if not isinstance(current, dict) or not isinstance(before, dict):
                continue
            current_value = current.get("score")
            previous_value = before.get("score")
            source = current.get("source")
            if current_value is None or previous_value is None or current_value == previous_value or not source:
                continue
            relevant_evidence = [item for item in evidence if item.get("source") == source and AnalystAutomationService._is_evidence_usable(item)]
            if not relevant_evidence:
                continue
            identity = {
                "kind": f"{metric_name}_change",
                "previous": previous_value,
                "current": current_value,
                "source": source,
            }
            alert_id = hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]
            if alert_id in seen:
                continue
            alerts.append({
                "alert_id": alert_id,
                "kind": identity["kind"],
                "status": "OPEN",
                "summary": f"{metric_name.title()} changed from {previous_value} to {current_value}.",
                "evidence": relevant_evidence,
                "previous": previous_value,
                "current": current_value,
                "source": source,
            })
            seen.add(alert_id)
        return alerts

    def persist_brief(self, brief_type: str, as_of: date, payload: dict[str, Any], *, idempotency_key: str) -> AnalystBrief:
        if self.session is None:
            raise ValueError("A database session is required to persist an analyst brief.")
        existing = self.session.query(AnalystBrief).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing
        brief = AnalystBrief(
            brief_type=brief_type,
            as_of_date=as_of,
            status=payload.get("status", "INSUFFICIENT_DATA"),
            payload=payload,
            idempotency_key=idempotency_key,
        )
        self.session.add(brief)
        self.session.commit()
        return brief


__all__ = ["AnalystAutomationService"]
