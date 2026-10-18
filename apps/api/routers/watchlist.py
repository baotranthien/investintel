from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Asset, PersonalPortfolio, WatchlistItem, WatchlistSnapshot, WatchlistThesisRevision
from services.portfolio.engine import PORTFOLIO_ID, canonical_asset
from services.portfolio.schemas import WatchlistCreate, WatchlistItemView, WatchlistPatch
from services.research.workspace import ResearchWorkspace, build_research_workspace

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


def _metric_value(metric: Any, key: str):
    return metric.get(key) if isinstance(metric, dict) else getattr(metric, key, None)


def _iso_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _snapshot_payload(research: ResearchWorkspace) -> dict[str, Any]:
    return {
        "as_of_date": research.as_of_date.isoformat(),
        "symbol": research.asset["symbol"],
        "price": {
            "value": research.price["value"],
            "status": research.price["status"],
            "source": research.price["source"],
                "as_of_date": _iso_value(research.price["as_of_date"]),
        },
        "opportunity": {"score": research.opportunity["score"], "confidence": research.opportunity["confidence"]},
        "risk": {"score": research.risk["overall_score"], "status": research.risk["status"]},
        "valuation": {
            key: {
                "value": _metric_value(metric, "value"),
                "status": _metric_value(metric, "status"),
                "source": (
                    metric.get("evidence", {}).get("source")
                    if isinstance(metric, dict) and isinstance(metric.get("evidence"), dict)
                    else getattr(getattr(metric, "evidence", None), "source", None)
                ),
            }
            for key, metric in research.valuation["metrics"].items()
        },
        "factor_scores": {key: _metric_value(metric, "value") for key, metric in research.factors["scores"].items()},
        "events": [
                {"id": event["id"], "title": event["title"], "published_at": _iso_value(event["published_at"]), "source": event["source"]}
            for event in research.events
        ],
    }


def _compare_watchlist_snapshots(previous: dict[str, Any], current: dict[str, Any], threshold: float | None):
    changes = []
    comparisons = [
        ("price", "value", "PRICE_CHANGE"),
        ("opportunity", "score", "OPPORTUNITY_CHANGE"),
        ("risk", "score", "RISK_CHANGE"),
    ]
    for group, field, change_type in comparisons:
        before_group = previous.get(group, {})
        current_group = current.get(group, {})
        before_value = before_group.get(field)
        current_value = current_group.get(field)
        if before_value is None or current_value is None or before_value == current_value:
            continue
        relative_change = abs(current_value - before_value) / abs(before_value) if before_value else None
        source = current_group.get("source")
        if group == "price" and not source:
            continue
        is_material = threshold is not None and relative_change is not None and relative_change >= threshold
        changes.append({
            "type": change_type,
            "before": before_value,
            "after": current_value,
            "change_pct": relative_change,
            "materiality": "MATERIAL" if is_material else "OBSERVED_UNCLASSIFIED",
            "evidence": {"source": source, "as_of_date": current_group.get("as_of_date")},
        })

    previous_events = {event["id"] for event in previous.get("events", [])}
    for event in current.get("events", []):
        if event["id"] not in previous_events and event.get("source"):
            changes.append({
                "type": "NEW_EVENT",
                "before": None,
                "after": event["title"],
                "materiality": "OBSERVED_UNCLASSIFIED",
                "evidence": {"source": event["source"], "published_at": event["published_at"]},
            })
    return changes


def _item_view(session: Session, item: WatchlistItem, asset: Asset, as_of: date) -> dict[str, Any]:
    research = build_research_workspace(session, asset.symbol, as_of)
    snapshots = session.query(WatchlistSnapshot).filter(
        WatchlistSnapshot.watchlist_id == item.id
    ).order_by(WatchlistSnapshot.captured_at.desc(), WatchlistSnapshot.id.desc()).limit(2).all()
    changes = []
    if len(snapshots) >= 2:
        account = session.get(PersonalPortfolio, PORTFOLIO_ID)
        threshold = float(account.material_change_threshold) if account and account.material_change_threshold is not None else None
        changes = _compare_watchlist_snapshots(snapshots[1].snapshot_data, snapshots[0].snapshot_data, threshold)

    price_metric = research.price if research else {}
    valuation_metrics = research.valuation["metrics"] if research else {}
    return WatchlistItemView(
        id=item.id,
        symbol=asset.symbol,
        name=asset.name,
        sector=asset.sector,
        thesis=item.thesis,
        horizon=item.horizon,
        invalidation=item.invalidation,
        last_reviewed_at=item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
        last_changed_at=item.last_changed_at.isoformat() if item.last_changed_at else "",
        opportunity=research.opportunity["score"] if research else None,
        confidence=research.opportunity["confidence"] if research else "INSUFFICIENT",
        risk=research.risk["overall_score"] if research else None,
        valuation={
            key: {"value": _metric_value(metric, "value"), "status": _metric_value(metric, "status")}
            for key, metric in valuation_metrics.items()
        } if research else None,
        why_now=research.opportunity["why_now"] if research else [],
        why_not_now=research.opportunity["why_not_now"] if research else [],
        data_status=research.status if research else "INSUFFICIENT_DATA",
        data_freshness={"status": price_metric.get("status", "INSUFFICIENT_DATA"), "as_of_date": price_metric.get("as_of_date"), "source": price_metric.get("source")},
        changes=changes,
    ).model_dump()


@router.get("", response_model=list[WatchlistItemView])
def get_watchlist(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
):
    rows = session.query(WatchlistItem, Asset).join(Asset, WatchlistItem.asset_id == Asset.id).order_by(
        WatchlistItem.last_changed_at.desc(), Asset.symbol
    ).offset(offset).limit(limit).all()
    return [_item_view(session, item, asset, date.today()) for item, asset in rows]


@router.post("", status_code=201, response_model=WatchlistItemView)
def add_watchlist_item(payload: WatchlistCreate, session: Session = Depends(get_db)):
    asset = canonical_asset(session, payload.symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Symbol is not an active canonical stock/ETF/fund.")
    existing = session.query(WatchlistItem).filter(WatchlistItem.asset_id == asset.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Asset is already on the watchlist.")
    item = WatchlistItem(asset_id=asset.id, thesis=payload.thesis, horizon=payload.horizon, invalidation=payload.invalidation)
    session.add(item)
    session.commit()
    return _item_view(session, item, asset, date.today())


@router.get("/{item_id}", response_model=WatchlistItemView)
def get_watchlist_item(item_id: int, session: Session = Depends(get_db)):
    row = session.query(WatchlistItem, Asset).join(Asset, WatchlistItem.asset_id == Asset.id).filter(WatchlistItem.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    return _item_view(session, row[0], row[1], date.today())


@router.patch("/{item_id}", response_model=WatchlistItemView)
def patch_watchlist_item(item_id: int, payload: WatchlistPatch, session: Session = Depends(get_db)):
    item = session.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    updates = payload.model_dump(exclude_unset=True)
    reason = updates.pop("change_reason", None)
    if "last_reviewed_at" in updates:
        reviewed_date = updates.pop("last_reviewed_at")
        item.last_reviewed_at = datetime.combine(reviewed_date, time.min, tzinfo=timezone.utc) if reviewed_date else None
    if "thesis" in updates and updates["thesis"] != item.thesis:
        if not reason or not reason.strip():
            raise HTTPException(status_code=422, detail="change_reason is required when changing a thesis.")
        session.add(WatchlistThesisRevision(
            watchlist_id=item.id,
            previous_thesis=item.thesis,
            new_thesis=updates["thesis"],
            change_reason=reason.strip(),
        ))
    for key, value in updates.items():
        setattr(item, key, value)
    if updates:
        item.last_changed_at = datetime.now(timezone.utc)
    session.commit()
    asset = session.query(Asset).filter(Asset.id == item.asset_id).one()
    return _item_view(session, item, asset, date.today())


@router.delete("/{item_id}", status_code=204)
def delete_watchlist_item(item_id: int, session: Session = Depends(get_db)):
    item = session.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    session.delete(item)
    session.commit()
    return Response(status_code=204)


@router.post("/{item_id}/review", response_model=WatchlistItemView)
def review_watchlist_item(item_id: int, session: Session = Depends(get_db)):
    item = session.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    item.last_reviewed_at = datetime.now(timezone.utc)
    session.commit()
    asset = session.query(Asset).filter(Asset.id == item.asset_id).one()
    return _item_view(session, item, asset, date.today())


@router.post("/{item_id}/snapshot")
def capture_watchlist_snapshot(item_id: int, session: Session = Depends(get_db)):
    item = session.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    asset = session.query(Asset).filter(Asset.id == item.asset_id).one()
    research = build_research_workspace(session, asset.symbol, date.today())
    if research is None:
        raise HTTPException(status_code=404, detail="Canonical research data is not available for this asset.")
    payload = _snapshot_payload(research)
    previous = session.query(WatchlistSnapshot).filter(
        WatchlistSnapshot.watchlist_id == item.id
    ).order_by(WatchlistSnapshot.captured_at.desc(), WatchlistSnapshot.id.desc()).first()
    account = session.get(PersonalPortfolio, PORTFOLIO_ID)
    threshold = float(account.material_change_threshold) if account and account.material_change_threshold is not None else None
    changes = _compare_watchlist_snapshots(previous.snapshot_data, payload, threshold) if previous else []
    snapshot = WatchlistSnapshot(watchlist_id=item.id, snapshot_data=payload)
    session.add(snapshot)
    session.commit()
    return {
        "snapshot_id": snapshot.id,
        "captured_at": snapshot.captured_at,
        "status": research.status,
        "changes": changes,
        "change_threshold": threshold,
        "note": "Only changes between evidence-backed values are listed; materiality remains unclassified without a user threshold.",
    }


@router.get("/{item_id}/thesis-history")
def get_thesis_history(item_id: int, session: Session = Depends(get_db)):
    item = session.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    revisions = session.query(WatchlistThesisRevision).filter(
        WatchlistThesisRevision.watchlist_id == item_id
    ).order_by(WatchlistThesisRevision.changed_at.desc()).all()
    return {"symbol": session.query(Asset.symbol).filter(Asset.id == item.asset_id).scalar(), "revisions": [
        {"previous_thesis": row.previous_thesis, "new_thesis": row.new_thesis, "change_reason": row.change_reason, "changed_at": row.changed_at}
        for row in revisions
    ]}
