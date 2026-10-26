from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from database.models import (
    Asset,
    AssetDecisionSnapshot,
    PersonalPortfolio,
    PersonalPortfolioSnapshot,
    PortfolioTarget,
    WatchlistItem,
)
from services.macro.observations import get_latest_macro_series
from services.market.dashboard import build_market_dashboard
from services.portfolio.engine import PORTFOLIO_ID, compare_snapshots, portfolio_dashboard, portfolio_fit
from services.research.workspace import build_research_workspace
from services.universe.registry import UniverseRegistry


def _asset_lookup(session: Session, symbol: str) -> Asset | None:
    resolved = UniverseRegistry.resolve_instrument(session, symbol)
    if resolved and resolved.asset_id:
        return session.query(Asset).filter(Asset.id == resolved.asset_id).first()
    normalized = UniverseRegistry.normalize_symbol(symbol) or symbol.upper()
    return session.query(Asset).filter(Asset.symbol == normalized).first()


def _snapshot_facts(session: Session, symbol: str, research: Any, as_of: date) -> dict[str, Any]:
    if research is None:
        return {"as_of_date": as_of.isoformat(), "status": "INSUFFICIENT_DATA", "modules": {}, "evidence": {}}

    research_data = research.model_dump(mode="json")
    market_data = build_market_dashboard(session, as_of).model_dump(mode="json")
    macro_data = get_latest_macro_series(session, as_of).model_dump(mode="json")
    portfolio_data = portfolio_dashboard(session, as_of)
    fit_data = portfolio_fit(session, as_of)
    holding = next((item for item in portfolio_data["holdings"] if item["symbol"] == symbol), None)
    fit_item = next((item for item in fit_data["items"] if item["symbol"] == symbol), None)
    portfolio_facts = {
        "status": portfolio_data["status"],
        "summary": portfolio_data["summary"],
        "concentration": portfolio_data["concentration"],
        "holding": ({
            key: holding.get(key)
            for key in ("symbol", "sector", "role", "current_price", "price_as_of", "price_status", "current_weight", "target_weight")
        } if holding else None),
    }
    macro_metrics = [
        item
        for region_items in macro_data.get("regions", {}).values()
        for item in region_items
    ]
    fundamentals = research_data.get("fundamentals", {})
    valuation = research_data.get("valuation", {})
    factors = research_data.get("factors", {})
    risk = research_data.get("risk", {})
    events = sorted(
        research_data.get("events", []),
        key=lambda item: (item.get("published_at") or "", item.get("id") or ""),
    )
    for event in events:
        event_evidence = event.get("evidence", {})
        if (event_evidence.get("source") or "").upper() in {"HOSE_CSV", "MARKETDATACSV"}:
            event_evidence["claim_type"] = "UNCERTAINTY"
            event_evidence["data_origin"] = "SEEDED_OR_UNTRACED"
            event_evidence["note"] = "Seeded/static source record; not verified as a live event catalyst."
            event["evidence"] = event_evidence
    vn100 = next((item.get("metric", {}) for item in market_data.get("indexes", []) if item.get("symbol") == "VN100"), {})
    modules = {
        "price": research_data.get("price", {}),
        "fundamentals": fundamentals,
        "valuation": valuation,
        "factors": factors,
        "macro": {
            "status": macro_data.get("status", "INSUFFICIENT_DATA"),
            "company_sensitivity": research_data.get("macro_sensitivity", {}),
            "observations": macro_metrics,
        },
        "regime": {
            "status": market_data.get("status", "INSUFFICIENT_DATA"),
            "market_regime": market_data.get("market_regime", {}),
            "benchmark": vn100,
            "breadth": market_data.get("breadth", {}),
            "momentum": market_data.get("momentum", {}),
        },
        "risk": risk,
        "events": events,
        "opportunity": research_data.get("opportunity", {}),
        "portfolio_fit": fit_item or {"status": "NOT_IN_PORTFOLIO", "note": "No current holding is available for portfolio-fit comparison."},
        "portfolio": portfolio_facts,
    }
    evidence = {
        "price": [{
            "claim_type": "FACT" if modules["price"].get("value") is not None else "UNCERTAINTY",
            "metric": "price",
            "value": modules["price"].get("value"),
            "raw_close": modules["price"].get("raw_close"),
            "adjusted_close": modules["price"].get("adjusted_close"),
            "adjustment_factor": modules["price"].get("adjustment_factor"),
            "unit": modules["price"].get("unit"),
            "source": modules["price"].get("source"),
            "source_url": modules["price"].get("source_url"),
            "observation_date": modules["price"].get("as_of_date"),
            "publication_date": modules["price"].get("as_of_date"),
            "data_origin": modules["price"].get("data_origin"),
            "freshness": modules["price"].get("status", "INSUFFICIENT_DATA"),
        }],
        "fundamentals": [{
            "claim_type": metric.get("evidence", {}).get("claim_type", "UNCERTAINTY"),
            "metric": name,
            "value": metric.get("value"),
            "unit": metric.get("unit"),
            "source": metric.get("evidence", {}).get("source"),
            "observation_date": metric.get("evidence", {}).get("observation_date"),
            "publication_date": metric.get("evidence", {}).get("publication_date"),
            "retrieved_at": metric.get("evidence", {}).get("retrieved_at"),
            "data_origin": metric.get("evidence", {}).get("data_origin"),
            "freshness": metric.get("status", "INSUFFICIENT_DATA"),
            "calculation_origin": metric.get("calculation"),
            "note": metric.get("evidence", {}).get("note"),
        } for name, metric in fundamentals.get("metrics", {}).items()],
        "valuation": [{
            "claim_type": metric.get("evidence", {}).get("claim_type", "UNCERTAINTY"),
            "metric": name,
            "value": metric.get("value"),
            "unit": metric.get("unit"),
            "source": metric.get("evidence", {}).get("source"),
            "observation_date": metric.get("evidence", {}).get("observation_date"),
            "publication_date": metric.get("evidence", {}).get("publication_date"),
            "data_origin": metric.get("evidence", {}).get("data_origin"),
            "freshness": metric.get("status", "INSUFFICIENT_DATA"),
            "calculation_origin": metric.get("calculation"),
            "note": metric.get("evidence", {}).get("note"),
        } for name, metric in valuation.get("metrics", {}).items()],
        "factors": [{
            "claim_type": metric.get("evidence", {}).get("claim_type", "UNCERTAINTY"),
            "metric": name,
            "value": metric.get("value"),
            "unit": metric.get("unit"),
            "source": metric.get("evidence", {}).get("source"),
            "data_origin": metric.get("evidence", {}).get("data_origin"),
            "freshness": metric.get("status", "INSUFFICIENT_DATA"),
            "note": metric.get("evidence", {}).get("note"),
        } for name, metric in factors.get("scores", {}).items()],
        "macro": [{
            "claim_type": "FACT" if item.get("value") is not None else "UNCERTAINTY",
            "metric": item.get("series_id"),
            "value": item.get("value"),
            "unit": item.get("unit"),
            "source": item.get("source"),
            "source_url": item.get("source_url"),
            "observation_date": item.get("observation_date"),
            "publication_date": item.get("published_at") or item.get("release_date"),
            "retrieved_at": item.get("retrieved_at"),
            "data_origin": item.get("data_origin"),
            "freshness": item.get("status", "INSUFFICIENT_DATA"),
        } for item in macro_metrics],
        "regime": [{
            "claim_type": "MODEL_OUTPUT",
            "source": modules["regime"].get("market_regime", {}).get("model_version"),
            "observation_date": modules["regime"].get("market_regime", {}).get("as_of"),
            "data_origin": modules["regime"].get("benchmark", {}).get("data_origin"),
            "freshness": modules["regime"].get("market_regime", {}).get("regime", "INSUFFICIENT_DATA"),
            "note": "; ".join(modules["regime"].get("market_regime", {}).get("drivers", [])),
        }],
        "risk": [{
            "claim_type": "UNCERTAINTY" if risk.get("overall_score") is None else "MODEL_OUTPUT",
            "metric": "overall_score",
            "value": risk.get("overall_score"),
            "source": "RiskEngine",
            "data_origin": "RESEARCH_WORKSPACE",
            "freshness": risk.get("status", "INSUFFICIENT_DATA"),
            "note": risk.get("missing_data_warning"),
        }],
        "events": [item.get("evidence", {}) for item in events],
        "opportunity": [{
            "claim_type": "UNCERTAINTY" if modules["opportunity"].get("score") is None else "MODEL_OUTPUT",
            "metric": "score",
            "value": modules["opportunity"].get("score"),
            "source": "ResearchWorkspace.opportunity",
            "data_origin": "RESEARCH_WORKSPACE",
            "freshness": modules["opportunity"].get("status", "INSUFFICIENT_DATA"),
            "note": "Opportunity and confidence remain separate fields; unavailable scores are not inferred.",
        }],
        "portfolio_fit": [{
            "claim_type": "UNCERTAINTY" if not fit_item or fit_item.get("status") != "AVAILABLE" else "MODEL_OUTPUT",
            "metric": "fit_status",
            "value": (fit_item or {}).get("status"),
            "source": "portfolio_fit",
            "data_origin": "PERSONAL_PORTFOLIO_AND_RESEARCH_WORKSPACE",
            "freshness": (fit_item or {}).get("status", "NOT_IN_PORTFOLIO"),
            "note": (fit_item or {}).get("note"),
        }],
        "portfolio": [{
            "claim_type": "MODEL_OUTPUT" if holding else "UNCERTAINTY",
            "metric": "current_weight",
            "value": holding.get("current_weight") if holding else None,
            "source": "portfolio_dashboard",
            "observation_date": as_of.isoformat(),
            "data_origin": "LOCAL_PERSONAL_PORTFOLIO",
            "freshness": portfolio_data.get("status", "INSUFFICIENT_DATA"),
            "note": "Portfolio fields are local and are not submitted to an external recommendation or broker service.",
        }],
    }
    for evidence_records in evidence.values():
        for item in evidence_records:
            source_name = (item.get("source") or "").upper()
            origin = (item.get("data_origin") or "").upper()
            if source_name in {"HOSE_CSV", "MARKETDATACSV"} or origin in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}:
                item["claim_type"] = "UNCERTAINTY"
                item["data_origin"] = "SEEDED_OR_UNTRACED"
                item["note"] = item.get("note") or "Seeded/static or untraced input; not verified as live source evidence."
    return {
        "as_of_date": as_of.isoformat(),
        "status": research.status,
        "modules": modules,
        "evidence": evidence,
    }


def capture_asset_decision_snapshot(session: Session, symbol: str, as_of: date) -> AssetDecisionSnapshot | None:
    asset = _asset_lookup(session, symbol)
    if asset is None:
        return None
    research = build_research_workspace(session, asset.symbol, as_of)
    facts = _snapshot_facts(session, asset.symbol, research, as_of)
    snapshot = AssetDecisionSnapshot(asset_id=asset.id, snapshot_data={"facts": facts})
    session.add(snapshot)
    session.flush()
    return snapshot


def _unavailable_scenario(reason: str) -> dict[str, Any]:
    return {
        "claim_type": "UNCERTAINTY",
        "status": "INSUFFICIENT_DATA",
        "assumptions": [],
        "key_drivers": [],
        "valuation_range": None,
        "risks": [],
        "confidence": "INSUFFICIENT_DATA",
        "uncertainty": reason,
    }


def _flatten_snapshot(value: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence", "as_of_date"}:
                continue
            path = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten_snapshot(item, path))
    elif isinstance(value, list):
        flattened[prefix] = value
    else:
        flattened[prefix] = value
    return flattened


def _change_magnitude(before: Any, after: Any) -> dict[str, float | None] | None:
    if isinstance(before, bool) or isinstance(after, bool) or not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return None
    absolute = float(after) - float(before)
    relative_pct = absolute / abs(float(before)) * 100 if before != 0 else None
    return {"absolute": absolute, "relative_pct": relative_pct}


def _decision_claims(
    research: Any,
    modules: dict[str, Any],
    evidence_by_module: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    why_now = []
    why_not_now = []

    def has_verified_source(module_name: str) -> bool:
        return any(
            item.get("claim_type") in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"}
            and item.get("source")
            and item.get("data_origin") not in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
            and item.get("freshness") not in {"STALE", "INSUFFICIENT_DATA"}
            for item in evidence_by_module.get(module_name, [])
        )

    if research is not None:
        for claim in research.research_summary.get("why_now", []):
            if claim.get("claim_type") != "UNCERTAINTY" and claim.get("source") and has_verified_source("fundamentals"):
                why_now.append({
                    **claim,
                    "responsible_module": "fundamentals",
                    "evidence": evidence_by_module.get("fundamentals", []),
                })
        for claim in research.research_summary.get("why_not_now", []):
            if claim.get("claim_type") and claim.get("text"):
                why_not_now.append({
                    **claim,
                    "responsible_module": "research_workspace",
                    "evidence": evidence_by_module.get("fundamentals", []),
                })

    regime = modules.get("regime", {}).get("market_regime", {})
    if regime.get("regime") not in (None, "INSUFFICIENT_DATA") and has_verified_source("regime"):
        for signal in regime.get("supporting_signals", []):
            why_now.append({
                "claim_type": "MODEL_OUTPUT",
                "text": signal,
                "source": regime.get("model_version"),
                "publication_date": regime.get("as_of"),
                "responsible_module": "market_regime",
                "evidence": evidence_by_module.get("regime", []),
            })
        for signal in regime.get("conflicting_signals", []):
            why_not_now.append({
                "claim_type": "MODEL_OUTPUT",
                "text": signal,
                "source": regime.get("model_version"),
                "publication_date": regime.get("as_of"),
                "responsible_module": "market_regime",
                "evidence": evidence_by_module.get("regime", []),
            })

    for event in modules.get("events", []):
        evidence = event.get("evidence", {})
        if (
            evidence.get("claim_type") == "FACT"
            and evidence.get("data_origin") not in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
            and has_verified_source("events")
        ):
            why_now.append({
                "claim_type": "FACT",
                "text": f"Recorded event: {event.get('title', 'Untitled event')}",
                "source": evidence.get("source"),
                "publication_date": evidence.get("publication_date"),
                "responsible_module": "events",
                "evidence": [evidence],
            })

    for module_name, module in modules.items():
        if module_name in {"events", "portfolio"} or not isinstance(module, dict):
            continue
        status = module.get("status")
        if isinstance(status, str) and status in {"STALE", "PARTIAL", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}:
            note = module.get("missing_data_warning") or module.get("note") or f"{module_name} status: {status}."
            why_not_now.append({
                "claim_type": "UNCERTAINTY",
                "text": str(note),
                "source": next((item.get("source") for item in evidence_by_module.get(module_name, []) if item.get("source")), module_name),
                "status": status,
                "responsible_module": module_name,
                "evidence": evidence_by_module.get(module_name, []),
            })
    if not why_now:
        why_now.append({
            "claim_type": "UNCERTAINTY",
            "text": "No evidence-backed positive driver is available; observed facts are not treated as a recommendation.",
            "responsible_module": "decision_intelligence",
        })
    if not why_not_now:
        why_not_now.append({
            "claim_type": "UNCERTAINTY",
            "text": "No supported negative driver or data-quality blocker was identified in the available inputs.",
            "responsible_module": "decision_intelligence",
        })
    return why_now, why_not_now


def _asset_module_changes(
    session: Session,
    asset_by_id: dict[int, str],
    module_name: str,
    as_of: date,
) -> list[dict[str, Any]]:
    changes = []
    for asset_id, symbol in asset_by_id.items():
        snapshots = session.query(AssetDecisionSnapshot).filter(
            AssetDecisionSnapshot.asset_id == asset_id
        ).order_by(AssetDecisionSnapshot.id.desc()).limit(100).all()
        eligible = sorted([
            item for item in snapshots
            if (item.snapshot_data.get("facts", {}).get("as_of_date") or "") <= as_of.isoformat()
        ], key=lambda item: (
            item.snapshot_data.get("facts", {}).get("as_of_date", ""),
            item.id,
        ), reverse=True)
        if len(eligible) < 2:
            continue
        previous = eligible[1].snapshot_data.get("facts", {})
        current = eligible[0].snapshot_data.get("facts", {})
        before = _flatten_snapshot(previous.get("modules", {}).get(module_name, {}))
        after = _flatten_snapshot(current.get("modules", {}).get(module_name, {}))
        evidence = current.get("evidence", {}).get(module_name, [])
        source = next((item.get("source") for item in evidence if item.get("source")), module_name)
        for metric in sorted(before.keys() | after.keys()):
            if before.get(metric) == after.get(metric):
                continue
            changes.append({
                "claim_type": "MODEL_OUTPUT",
                "symbol": symbol,
                "responsible_module": module_name,
                "metric": metric,
                "before": before.get(metric),
                "after": after.get(metric),
                "date": current.get("as_of_date", as_of.isoformat()),
                "magnitude": _change_magnitude(before.get(metric), after.get(metric)),
                "source": source,
                "evidence": evidence,
            })
    return changes


def build_decision_context(session: Session, symbol: str, as_of: Optional[date] = None) -> dict[str, Any]:
    as_of = as_of or date.today()
    normalized_symbol = symbol.upper()
    research = build_research_workspace(session, normalized_symbol, as_of)
    asset = _asset_lookup(session, normalized_symbol)

    timeline = []
    evidence_items = []
    price_info = None
    if research is not None:
        price_info = research.price if isinstance(research.price, dict) else None
        for item in research.timeline or []:
            timeline.append({
                "id": item.id,
                "date": item.date,
                "kind": item.kind,
                "title": item.title,
                "before": item.before,
                "after": item.current,
                "status": item.status,
                "evidence": {
                    "claim_type": getattr(item.evidence, "claim_type", "UNCERTAINTY"),
                    "source": getattr(item.evidence, "source", None),
                    "publication_date": getattr(item.evidence, "publication_date", None).isoformat() if getattr(item.evidence, "publication_date", None) else None,
                    "data_origin": getattr(item.evidence, "data_origin", None),
                    "note": getattr(item.evidence, "note", None),
                },
            })
        if not timeline and price_info:
            timeline.append({
                "id": f"price-{normalized_symbol}",
                "date": price_info.get("as_of_date"),
                "kind": "PRICE_UPDATE",
                "title": f"Current price for {normalized_symbol}",
                "before": None,
                "after": price_info.get("value"),
                "status": price_info.get("status", "INSUFFICIENT_DATA"),
                "evidence": {
                    "claim_type": "FACT",
                    "source": price_info.get("source"),
                    "publication_date": price_info.get("as_of_date"),
                    "data_origin": price_info.get("data_origin"),
                    "note": "Price is the latest canonical observation available for the asset.",
                },
            })
        for value in (research.fundamentals.get("metrics") or {}).values():
            if isinstance(value, dict) and value.get("evidence"):
                evidence_items.append({
                    "claim_type": value["evidence"].get("claim_type", "UNCERTAINTY"),
                    "source": value["evidence"].get("source"),
                    "observation_date": value["evidence"].get("observation_date"),
                    "publication_date": value["evidence"].get("publication_date"),
                    "data_origin": value["evidence"].get("data_origin"),
                    "note": value["evidence"].get("note"),
                })
        if not evidence_items and price_info:
            evidence_items.append({
                "claim_type": "FACT",
                "source": price_info.get("source"),
                "observation_date": price_info.get("as_of_date"),
                "publication_date": price_info.get("as_of_date"),
                "data_origin": price_info.get("data_origin"),
                "note": "Canonical price evidence is the only source currently available.",
            })

    if not evidence_items and asset is not None:
        evidence_items.append({
            "claim_type": "UNCERTAINTY",
            "source": None,
            "observation_date": as_of.isoformat(),
            "publication_date": as_of.isoformat(),
            "data_origin": "ASSET_REGISTRY",
            "note": "No canonical evidence was available beyond the asset registry entry.",
        })
    if not timeline and asset is not None:
        timeline.append({
            "id": f"registry-{normalized_symbol}",
            "date": as_of.isoformat(),
            "kind": "ASSET_REGISTRY",
            "title": f"Asset {normalized_symbol} is present in the source registry.",
            "before": None,
            "after": asset.name,
            "status": "INSUFFICIENT_DATA",
            "evidence": {"claim_type": "UNCERTAINTY", "source": "asset_registry", "publication_date": as_of.isoformat(), "data_origin": "ASSET_REGISTRY", "note": "Registry presence is not direct investment evidence."},
        })

    current_facts = _snapshot_facts(session, normalized_symbol, research, as_of)
    modules = current_facts["modules"]
    previous_snapshots = session.query(AssetDecisionSnapshot).filter(
        AssetDecisionSnapshot.asset_id == asset.id if asset else False
    ).order_by(AssetDecisionSnapshot.id.desc()).limit(100).all() if asset else []
    eligible_snapshots = sorted([
        item for item in previous_snapshots
        if (item.snapshot_data.get("facts", {}).get("as_of_date") or "") <= as_of.isoformat()
    ], key=lambda item: (
        item.snapshot_data.get("facts", {}).get("as_of_date", ""),
        item.id,
    ), reverse=True)
    if not eligible_snapshots:
        what_changed = [{
            "claim_type": "UNCERTAINTY",
            "responsible_module": "decision_intelligence",
            "metric": None,
            "before": None,
            "after": None,
            "date": as_of.isoformat(),
            "magnitude": None,
            "source": "asset_decision_snapshots",
            "evidence": [{"claim_type": "UNCERTAINTY", "note": "No earlier persisted snapshot is available for comparison."}],
        }]
    else:
        previous_facts = eligible_snapshots[1].snapshot_data.get("facts", {}) if len(eligible_snapshots) > 1 else eligible_snapshots[0].snapshot_data.get("facts", {})
        compared_facts = eligible_snapshots[0].snapshot_data.get("facts", {}) if len(eligible_snapshots) > 1 else current_facts
        previous_values = _flatten_snapshot(previous_facts.get("modules", {}))
        compared_values = _flatten_snapshot(compared_facts.get("modules", {}))
        what_changed = []
        for metric in sorted(previous_values.keys() | compared_values.keys()):
            before = previous_values.get(metric)
            after = compared_values.get(metric)
            if before == after:
                continue
            responsible_module = metric.split(".", 1)[0]
            evidence = current_facts["evidence"].get(responsible_module, [])
            primary_source = next((item.get("source") for item in evidence if item.get("source")), responsible_module)
            what_changed.append({
                "claim_type": "FACT" if responsible_module == "events" else "MODEL_OUTPUT",
                "responsible_module": responsible_module,
                "metric": metric,
                "before": before,
                "after": after,
                "date": compared_facts.get("as_of_date", as_of.isoformat()),
                "magnitude": _change_magnitude(before, after),
                "source": primary_source,
                "evidence": evidence,
            })
        if not what_changed:
            what_changed = [{
                "claim_type": "MODEL_OUTPUT",
                "responsible_module": "decision_intelligence",
                "metric": None,
                "before": None,
                "after": None,
                "date": as_of.isoformat(),
                "magnitude": None,
                "source": "asset_decision_snapshots",
                "evidence": [{"claim_type": "MODEL_OUTPUT", "note": "No differences were found in the tracked fields between the selected snapshots."}],
            }]

    why_now, why_not_now = _decision_claims(research, modules, current_facts["evidence"])
    scenario_reason = "No validated scenario model with supported assumptions and valuation ranges is available."
    scenario = {name: _unavailable_scenario(scenario_reason) for name in ("bear", "base", "bull")}

    fundamentals = modules.get("fundamentals", {})
    fundamentals_metrics = fundamentals.get("metrics", {})
    valuation = modules.get("valuation", {})
    valuation_metrics = valuation.get("metrics", {})
    factors = modules.get("factors", {})
    factor_scores = factors.get("scores", {})
    portfolio_fit_item = modules.get("portfolio_fit", {})

    def explainability_component(status: Any, value: Any, evidence_module: str, note: Any = None) -> dict[str, Any]:
        return {
            "status": status or "INSUFFICIENT_DATA",
            "value": value,
            "evidence": current_facts["evidence"].get(evidence_module, []),
            "note": note,
        }

    explainability = {
        "valuation": explainability_component(valuation.get("status"), valuation_metrics, "valuation"),
        "quality": explainability_component(fundamentals.get("status"), {key: fundamentals_metrics.get(key) for key in ("roe", "roa", "roic", "net_margin", "current_ratio")}, "fundamentals"),
        "growth": explainability_component(fundamentals.get("status"), {key: fundamentals_metrics.get(key) for key in ("revenue_yoy", "net_income_yoy", "eps_yoy", "revenue_cagr_3y")}, "fundamentals"),
        "value": explainability_component(valuation.get("status"), {key: valuation_metrics.get(key) for key in ("pe", "pb")}, "valuation", "Observed multiples are not fair-value estimates."),
        "momentum": explainability_component(factor_scores.get("momentum", {}).get("status"), factor_scores.get("momentum"), "factors"),
        "dividend": explainability_component(factor_scores.get("dividend", {}).get("status"), {"factor": factor_scores.get("dividend"), "yield": valuation_metrics.get("dividend_yield")}, "factors"),
        "macro": explainability_component(modules.get("macro", {}).get("status"), modules.get("macro"), "macro"),
        "risk": explainability_component(modules.get("risk", {}).get("status"), modules.get("risk"), "risk"),
        "events": explainability_component("AVAILABLE" if modules.get("events") else "INSUFFICIENT_DATA", modules.get("events"), "events"),
        "opportunity": explainability_component(modules.get("opportunity", {}).get("status"), modules.get("opportunity", {}).get("score"), "opportunity"),
        "confidence": explainability_component("AVAILABLE" if modules.get("opportunity", {}).get("confidence") not in (None, "INSUFFICIENT") else "INSUFFICIENT_DATA", modules.get("opportunity", {}).get("confidence"), "opportunity"),
        "portfolio_fit": explainability_component(portfolio_fit_item.get("status"), portfolio_fit_item, "portfolio_fit"),
        "portfolio_overlap": explainability_component(portfolio_fit_item.get("status"), {"holding": modules.get("portfolio", {}).get("holding"), "fit": portfolio_fit_item}, "portfolio"),
    }

    watchlist_item = session.query(WatchlistItem).filter(WatchlistItem.asset_id == asset.id).first() if asset else None
    invalidation = ([{
        "type": "USER_DEFINED",
        "claim_type": "HYPOTHESIS",
        "condition": watchlist_item.invalidation,
        "source": "watchlist_item.invalidation",
        "evidence": [{
            "claim_type": "UNCERTAINTY",
            "source": "watchlist_item.invalidation",
            "data_origin": "USER_ENTERED_THESIS",
            "note": "User-entered invalidation rule; not independently verified by the data engines.",
        }],
    }] if watchlist_item and watchlist_item.invalidation else [])

    evidence_items = [
        {"responsible_module": module_name, **evidence}
        for module_name, evidence_records in current_facts["evidence"].items()
        for evidence in evidence_records
    ]

    return {
        "symbol": normalized_symbol,
        "decision_state": research.status if research else "INSUFFICIENT_DATA",
        "what_changed": what_changed,
        "why_now": why_now,
        "why_not_now": why_not_now,
        "what_would_make_me_wrong": invalidation,
        "scenario": scenario,
        "snapshot": current_facts,
        "evidence": evidence_items,
        "timeline": timeline,
        "explainability": explainability,
        "as_of_date": as_of.isoformat(),
    }


def build_portfolio_decision_view(session: Session, as_of: date) -> dict[str, Any]:
    dashboard = portfolio_dashboard(session, as_of)
    fit = portfolio_fit(session, as_of)
    asset_by_id = {item.id: item.symbol for item in session.query(Asset).all()}

    allocation_drift = []
    target_rows = session.query(PortfolioTarget).filter(PortfolioTarget.portfolio_id == PORTFOLIO_ID).all()
    for target in target_rows:
        symbol = asset_by_id.get(target.asset_id)
        current = next((holding for holding in dashboard["holdings"] if holding["symbol"] == symbol), None)
        current_weight = current.get("current_weight") if current else None
        target_weight = float(target.target_weight)
        drift = None if current_weight is None else current_weight - target_weight
        allocation_drift.append({
            "claim_type": "MODEL_OUTPUT" if drift is not None else "UNCERTAINTY",
            "responsible_module": "portfolio_targets",
            "symbol": symbol,
            "current_weight": current_weight,
            "target_weight": target_weight,
            "drift_pct": drift,
            "direction": "UNDER" if current_weight is not None and current_weight < target_weight else "OVER" if current_weight is not None and current_weight > target_weight else "UNAVAILABLE",
            "evidence_source": "portfolio_target_vs_holding",
            "date": as_of.isoformat(),
            "magnitude": {"absolute": drift} if drift is not None else None,
            "evidence": [{
                "claim_type": "FACT" if current_weight is not None else "UNCERTAINTY",
                "source": "portfolio_target_vs_holding",
                "observation_date": as_of.isoformat(),
                "data_origin": "LOCAL_PERSONAL_PORTFOLIO",
                "freshness": current.get("price_status", "INSUFFICIENT_DATA") if current else "INSUFFICIENT_DATA",
            }],
        })

    if not allocation_drift:
        allocation_drift = [{
            "claim_type": "UNCERTAINTY",
            "responsible_module": "portfolio_targets",
            "symbol": None,
            "current_weight": None,
            "target_weight": None,
            "drift_pct": None,
            "direction": "UNAVAILABLE",
            "evidence_source": "portfolio_target_vs_holding",
            "date": as_of.isoformat(),
            "magnitude": None,
            "evidence": [{"claim_type": "UNCERTAINTY", "source": "portfolio_target_vs_holding", "data_origin": "LOCAL_PERSONAL_PORTFOLIO", "freshness": "INSUFFICIENT_DATA"}],
        }]

    saved_snapshots = session.query(PersonalPortfolioSnapshot).filter(
        PersonalPortfolioSnapshot.portfolio_id == PORTFOLIO_ID
    ).order_by(PersonalPortfolioSnapshot.captured_at.desc(), PersonalPortfolioSnapshot.id.desc()).all()
    eligible_portfolio_snapshots = [
        item for item in saved_snapshots
        if (item.snapshot_data.get("as_of_date") or "") <= as_of.isoformat()
    ]
    eligible_portfolio_snapshots.sort(key=lambda item: (
        item.snapshot_data.get("as_of_date", ""),
        item.captured_at.isoformat() if item.captured_at else "",
        item.id,
    ), reverse=True)
    portfolio_changes = []
    if len(eligible_portfolio_snapshots) >= 2:
        account = session.get(PersonalPortfolio, PORTFOLIO_ID)
        threshold = float(account.material_change_threshold) if account and account.material_change_threshold is not None else None
        portfolio_changes = compare_snapshots(
            eligible_portfolio_snapshots[1].snapshot_data or {},
            eligible_portfolio_snapshots[0].snapshot_data or {},
            threshold,
        )

    portfolio_symbols = {item["symbol"] for item in dashboard.get("holdings", [])}
    portfolio_assets = session.query(Asset).filter(Asset.symbol.in_(portfolio_symbols)).all() if portfolio_symbols else []
    portfolio_asset_by_id = {item.id: item.symbol for item in portfolio_assets}
    opportunity_changes = _asset_module_changes(session, portfolio_asset_by_id, "opportunity", as_of)
    risk_changes = _asset_module_changes(session, portfolio_asset_by_id, "risk", as_of)
    portfolio_fit_changes = _asset_module_changes(session, portfolio_asset_by_id, "portfolio_fit", as_of)
    if not risk_changes:
        risk_changes = [{
            "claim_type": "UNCERTAINTY",
            "symbol": item.get("symbol"),
            "responsible_module": "risk",
            "before": None,
            "after": item.get("risk_score"),
            "date": as_of.isoformat(),
            "magnitude": None,
            "source": "portfolio_fit",
            "status": "INSUFFICIENT_DATA" if item.get("risk_score") is None else item.get("status"),
            "evidence": [{"claim_type": "UNCERTAINTY", "note": "No pair of eligible risk snapshots is available for comparison."}],
        } for item in fit.get("items", [])] or [{
            "claim_type": "UNCERTAINTY",
            "responsible_module": "risk",
            "before": None,
            "after": None,
            "date": as_of.isoformat(),
            "magnitude": None,
            "source": "portfolio_fit",
            "status": "INSUFFICIENT_DATA",
            "evidence": [{"claim_type": "UNCERTAINTY", "note": "No risk signal is available for the current holding set."}],
        }]

    scenario = {name: _unavailable_scenario("No validated portfolio scenario model is available.") for name in ("bear", "base", "bull")}

    return {
        "portfolio_id": PORTFOLIO_ID,
        "decision_state": dashboard.get("status", "INSUFFICIENT_DATA"),
        "allocation_drift": allocation_drift,
        "concentration": dashboard.get("concentration", {}),
        "portfolio_changes": portfolio_changes,
        "opportunity_changes": opportunity_changes,
        "risk_changes": risk_changes,
        "portfolio_fit_changes": portfolio_fit_changes,
        "scenario": scenario,
        "evidence": [
            {"claim_type": "MODEL_OUTPUT", "responsible_module": "portfolio_concentration", **warning}
            for warning in dashboard.get("concentration", {}).get("warnings", [])
        ] or [{
            "claim_type": "UNCERTAINTY",
            "responsible_module": "portfolio_concentration",
            "code": "NO_EVIDENCE",
            "message": "No concentration evidence is currently available.",
        }],
        "recommended_actions": [],
        "as_of_date": as_of.isoformat(),
    }
