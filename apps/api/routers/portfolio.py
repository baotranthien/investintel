from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import (
    Asset,
    DcaPlan,
    ManualPortfolioTransaction,
    PersonalPortfolio,
    PersonalPortfolioSnapshot,
    PortfolioHolding,
    PortfolioTarget,
)
from services.portfolio.engine import (
    DEFAULT_CORE_PCT,
    DEFAULT_DCA_AMOUNT,
    DEFAULT_SATELLITE_PCT,
    PORTFOLIO_ID,
    canonical_asset,
    compare_snapshots,
    dca_plan_view,
    ensure_portfolio,
    portfolio_dashboard,
    portfolio_fit,
)
from services.portfolio.schemas import (
    DcaPlanUpdate,
    HoldingCreate,
    HoldingPatch,
    ManualTransactionCreate,
    PortfolioDashboardResponse,
    PortfolioFitResponse,
    PortfolioSettingsPatch,
    PortfolioSettingsResponse,
    PortfolioHoldingView,
    TargetAllocationUpdate,
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioDashboardResponse)
def get_portfolio(session: Session = Depends(get_db)):
    return portfolio_dashboard(session, date.today())


@router.get("/holdings", response_model=list[PortfolioHoldingView])
def get_holdings(session: Session = Depends(get_db)):
    return portfolio_dashboard(session, date.today())["holdings"]


@router.post("/holdings", status_code=201)
def create_holding(payload: HoldingCreate, session: Session = Depends(get_db)):
    if payload.acquisition_date > date.today():
        raise HTTPException(status_code=422, detail="Acquisition date cannot be in the future.")
    asset = canonical_asset(session, payload.symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Symbol is not an active canonical stock/ETF/fund.")
    ensure_portfolio(session)
    holding = PortfolioHolding(
        portfolio_id=PORTFOLIO_ID,
        asset_id=asset.id,
        quantity=payload.quantity,
        average_cost=payload.average_cost,
        acquisition_date=payload.acquisition_date,
        role=payload.role,
        horizon=payload.horizon,
        notes=payload.notes,
    )
    session.add(holding)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A holding for this symbol already exists; edit the existing record.") from exc
    return next(item for item in portfolio_dashboard(session, date.today())["holdings"] if item["id"] == holding.id)


@router.patch("/holdings/{holding_id}")
def update_holding(holding_id: int, payload: HoldingPatch, session: Session = Depends(get_db)):
    holding = session.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == PORTFOLIO_ID,
    ).first()
    if holding is None:
        raise HTTPException(status_code=404, detail="Holding not found.")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("acquisition_date") and updates["acquisition_date"] > date.today():
        raise HTTPException(status_code=422, detail="Acquisition date cannot be in the future.")
    for key, value in updates.items():
        setattr(holding, key, value)
    session.commit()
    return next(item for item in portfolio_dashboard(session, date.today())["holdings"] if item["id"] == holding.id)


@router.delete("/holdings/{holding_id}", status_code=204)
def delete_holding(holding_id: int, session: Session = Depends(get_db)):
    holding = session.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == PORTFOLIO_ID,
    ).first()
    if holding is None:
        raise HTTPException(status_code=404, detail="Holding not found.")
    session.delete(holding)
    session.commit()
    return Response(status_code=204)


@router.get("/transactions")
def get_manual_transactions(session: Session = Depends(get_db)) -> dict[str, Any]:
    rows = session.query(ManualPortfolioTransaction, Asset).join(
        Asset, ManualPortfolioTransaction.asset_id == Asset.id
    ).filter(ManualPortfolioTransaction.portfolio_id == PORTFOLIO_ID).order_by(
        ManualPortfolioTransaction.transaction_date.desc(), ManualPortfolioTransaction.id.desc()
    ).limit(200).all()
    return {"mode": "MANUAL_RECORDS_ONLY", "transactions": [
        {
            "id": item.id,
            "symbol": asset.symbol,
            "transaction_type": item.transaction_type,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "transaction_date": item.transaction_date,
            "entry_source": item.entry_source,
            "notes": item.notes,
        }
        for item, asset in rows
    ]}


@router.post("/transactions", status_code=201)
def create_manual_transaction(payload: ManualTransactionCreate, session: Session = Depends(get_db)):
    if payload.transaction_date > date.today():
        raise HTTPException(status_code=422, detail="Transaction date cannot be in the future.")
    asset = canonical_asset(session, payload.symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Symbol is not an active canonical stock/ETF/fund.")
    ensure_portfolio(session)
    row = ManualPortfolioTransaction(
        portfolio_id=PORTFOLIO_ID,
        asset_id=asset.id,
        transaction_type=payload.transaction_type,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        transaction_date=payload.transaction_date,
        entry_source="MANUAL",
        notes=payload.notes,
    )
    session.add(row)
    session.commit()
    return {"id": row.id, "symbol": asset.symbol, "entry_source": "MANUAL", "holdings_updated": False}


@router.get("/settings", response_model=PortfolioSettingsResponse)
def get_portfolio_settings(session: Session = Depends(get_db)):
    account = session.get(PersonalPortfolio, PORTFOLIO_ID)
    return PortfolioSettingsResponse(
        portfolio_id=PORTFOLIO_ID,
        name=account.name if account else "Personal Portfolio",
        base_currency=account.base_currency if account else "VND",
        single_name_limit=account.single_name_limit if account else None,
        sector_limit=account.sector_limit if account else None,
        core_target=account.core_target if account else None,
        satellite_target=account.satellite_target if account else None,
        material_change_threshold=account.material_change_threshold if account else None,
    )


@router.patch("/settings", response_model=PortfolioSettingsResponse)
def patch_portfolio_settings(payload: PortfolioSettingsPatch, session: Session = Depends(get_db)):
    account = ensure_portfolio(session)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(account, key, value)
    session.commit()
    return get_portfolio_settings(session)


@router.get("/targets")
def get_targets(session: Session = Depends(get_db)):
    rows = session.query(PortfolioTarget, Asset).join(Asset, PortfolioTarget.asset_id == Asset.id).filter(
        PortfolioTarget.portfolio_id == PORTFOLIO_ID
    ).order_by(Asset.symbol).all()
    return {"status": "AVAILABLE" if rows else "EMPTY", "targets": [
        {"symbol": asset.symbol, "target_weight": float(target.target_weight)} for target, asset in rows
    ], "total_weight": sum(float(target.target_weight) for target, _ in rows)}


@router.put("/targets")
def replace_targets(payload: TargetAllocationUpdate, session: Session = Depends(get_db)):
    assets = {item.symbol: canonical_asset(session, item.symbol) for item in payload.targets}
    missing = [symbol for symbol, asset in assets.items() if asset is None]
    if missing:
        raise HTTPException(status_code=404, detail={"unknown_symbols": missing})
    ensure_portfolio(session)
    session.query(PortfolioTarget).filter(PortfolioTarget.portfolio_id == PORTFOLIO_ID).delete(synchronize_session=False)
    for item in payload.targets:
        session.add(PortfolioTarget(portfolio_id=PORTFOLIO_ID, asset_id=assets[item.symbol].id, target_weight=item.target_weight))
    session.commit()
    return get_targets(session)


@router.delete("/targets/{symbol}", status_code=204)
def delete_target(symbol: str, session: Session = Depends(get_db)):
    asset = canonical_asset(session, symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Canonical asset not found.")
    target = session.query(PortfolioTarget).filter(
        PortfolioTarget.portfolio_id == PORTFOLIO_ID,
        PortfolioTarget.asset_id == asset.id,
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Portfolio target not found.")
    session.delete(target)
    session.commit()
    return Response(status_code=204)


@router.get("/templates")
def get_personal_templates():
    return {"templates": [{
        "id": "personal-starting-template",
        "label": "Personal Starting Template / Cấu hình khởi đầu cá nhân",
        "classification": "USER_EDITABLE_PERSONAL_TEMPLATE",
        "targets": [
            {"symbol": "FUEVN100", "target_weight": 0.75},
            {"symbol": "FPT", "target_weight": 0.0833},
            {"symbol": "VCB", "target_weight": 0.0833},
            {"symbol": "MWG", "target_weight": 0.0833},
        ],
        "note": "Personal editable starting configuration; not a best, optimal, or universal recommendation.",
    }]}


@router.post("/templates/{template_id}/apply")
def apply_personal_template(template_id: str, session: Session = Depends(get_db)):
    if template_id != "personal-starting-template":
        raise HTTPException(status_code=404, detail="Personal template not found.")
    template = get_personal_templates()["templates"][0]
    return replace_targets(TargetAllocationUpdate(targets=template["targets"]), session)


@router.get("/allocation")
def get_portfolio_allocation(session: Session = Depends(get_db)):
    dashboard = portfolio_dashboard(session, date.today())
    targets = get_targets(session)
    holdings_by_symbol = {item["symbol"]: item for item in dashboard["holdings"]}
    drift = []
    for target in targets["targets"]:
        holding = holdings_by_symbol.get(target["symbol"])
        current_weight = holding["current_weight"] if holding else (0.0 if dashboard["allocation"]["status"] == "AVAILABLE" else None)
        drift.append({
            "symbol": target["symbol"],
            "current_weight": current_weight,
            "target_weight": target["target_weight"],
            "drift": current_weight - target["target_weight"] if current_weight is not None else None,
            "status": "AVAILABLE" if current_weight is not None else "INSUFFICIENT_DATA",
        })
    return {
        "as_of_date": date.today(),
        "status": dashboard["allocation"]["status"],
        "current": dashboard["allocation"],
        "target": targets,
        "drift": drift,
        "warnings": dashboard["concentration"]["warnings"],
    }


@router.get("/fit", response_model=PortfolioFitResponse)
def get_portfolio_fit(session: Session = Depends(get_db)):
    return portfolio_fit(session, date.today())


@router.get("/dca")
def get_dca(session: Session = Depends(get_db)):
    return dca_plan_view(session, date.today())


@router.put("/dca")
def put_dca(payload: DcaPlanUpdate, session: Session = Depends(get_db)):
    ensure_portfolio(session)
    plan = session.query(DcaPlan).filter(DcaPlan.portfolio_id == PORTFOLIO_ID).first()
    if plan is None:
        plan = DcaPlan(portfolio_id=PORTFOLIO_ID)
        session.add(plan)
    plan.monthly_amount = payload.monthly_amount
    plan.core_pct = payload.core_pct
    plan.satellite_pct = payload.satellite_pct
    session.commit()
    return dca_plan_view(session, date.today())


@router.post("/snapshot")
def create_portfolio_snapshot(session: Session = Depends(get_db)):
    dashboard = portfolio_dashboard(session, date.today())
    if dashboard["status"] == "EMPTY":
        raise HTTPException(status_code=409, detail="Cannot snapshot an empty portfolio.")
    previous = session.query(PersonalPortfolioSnapshot).filter(
        PersonalPortfolioSnapshot.portfolio_id == PORTFOLIO_ID
    ).order_by(PersonalPortfolioSnapshot.captured_at.desc(), PersonalPortfolioSnapshot.id.desc()).first()
    account = session.get(PersonalPortfolio, PORTFOLIO_ID)
    threshold = float(account.material_change_threshold) if account and account.material_change_threshold is not None else None
    changes = compare_snapshots(previous.snapshot_data, dashboard, threshold) if previous else []
    row = PersonalPortfolioSnapshot(portfolio_id=PORTFOLIO_ID, snapshot_data=jsonable_encoder(dashboard))
    session.add(row)
    session.commit()
    return {
        "snapshot_id": row.id,
        "captured_at": row.captured_at,
        "status": dashboard["status"],
        "change_threshold": threshold,
        "changes": changes,
        "note": "Changes are observed only from sourced values; materiality is unclassified unless the user configures a threshold.",
    }


@router.get("/changes")
def get_portfolio_changes(session: Session = Depends(get_db)):
    snapshots = session.query(PersonalPortfolioSnapshot).filter(
        PersonalPortfolioSnapshot.portfolio_id == PORTFOLIO_ID
    ).order_by(PersonalPortfolioSnapshot.captured_at.desc(), PersonalPortfolioSnapshot.id.desc()).limit(2).all()
    if len(snapshots) < 2:
        return {"status": "INSUFFICIENT_DATA", "changes": [], "note": "Capture at least two explicit portfolio snapshots to compare changes."}
    account = session.get(PersonalPortfolio, PORTFOLIO_ID)
    threshold = float(account.material_change_threshold) if account and account.material_change_threshold is not None else None
    return {
        "status": "AVAILABLE",
        "before": snapshots[1].captured_at,
        "after": snapshots[0].captured_at,
        "change_threshold": threshold,
        "changes": compare_snapshots(snapshots[1].snapshot_data, snapshots[0].snapshot_data, threshold),
    }
