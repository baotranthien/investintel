from datetime import date
from decimal import Decimal
from math import isclose
from typing import Any, Optional

from sqlalchemy.orm import Session

from database.models import (
    Asset,
    DcaPlan,
    ManualPortfolioTransaction,
    PersonalPortfolio,
    PersonalPortfolioSnapshot,
    PortfolioHolding,
    PortfolioTarget,
    Price,
    WatchlistItem,
    WatchlistSnapshot,
    WatchlistThesisRevision,
)
from services.research.workspace import build_research_workspace

PORTFOLIO_ID = "personal"
DEFAULT_DCA_AMOUNT = 350_000
DEFAULT_CORE_PCT = Decimal("0.75")
DEFAULT_SATELLITE_PCT = Decimal("0.25")


def ensure_portfolio(session: Session) -> PersonalPortfolio:
    portfolio = session.get(PersonalPortfolio, PORTFOLIO_ID)
    if portfolio is None:
        portfolio = PersonalPortfolio(id=PORTFOLIO_ID, name="Personal Portfolio", base_currency="VND")
        session.add(portfolio)
        session.flush()
    return portfolio


def canonical_asset(session: Session, symbol: str) -> Optional[Asset]:
    asset = session.query(Asset).filter(
        Asset.symbol == symbol.upper(),
        Asset.status == "ACTIVE",
        Asset.asset_type.in_(["STOCK", "ETF", "MUTUAL_FUND"]),
    ).first()
    return asset


def portfolio_dashboard(session: Session, as_of: date) -> dict[str, Any]:
    account = session.get(PersonalPortfolio, PORTFOLIO_ID)
    holdings_rows = []
    if account is not None:
        holdings_rows = session.query(PortfolioHolding, Asset).join(
            Asset, PortfolioHolding.asset_id == Asset.id
        ).filter(PortfolioHolding.portfolio_id == PORTFOLIO_ID).order_by(Asset.symbol).all()
    targets = {
        target.asset_id: float(target.target_weight)
        for target in session.query(PortfolioTarget).filter(PortfolioTarget.portfolio_id == PORTFOLIO_ID).all()
    } if account else {}

    holdings = []
    for holding, asset in holdings_rows:
        latest_price = session.query(Price).filter(
            Price.asset_id == asset.id,
            Price.status == "VALID",
            Price.observation_date <= as_of,
        ).order_by(Price.observation_date.desc()).first()
        current_price = None
        price_date = None
        price_status = "INSUFFICIENT_DATA"
        price_source = None
        if latest_price is not None:
            current_price = float(latest_price.adjusted_close if latest_price.adjusted_close is not None else latest_price.raw_close)
            price_date = latest_price.observation_date
            price_status = "STALE" if (as_of - price_date).days > 7 else "AVAILABLE"
            price_source = latest_price.source
        quantity = Decimal(holding.quantity)
        average_cost = Decimal(holding.average_cost)
        cost_basis = quantity * average_cost
        market_value = quantity * Decimal(str(current_price)) if current_price is not None else None
        holdings.append({
            "id": holding.id,
            "symbol": asset.symbol,
            "name": asset.name,
            "sector": asset.sector,
            "asset_type": asset.asset_type,
            "quantity": float(quantity),
            "average_cost": float(average_cost),
            "acquisition_date": holding.acquisition_date,
            "role": holding.role,
            "horizon": holding.horizon,
            "notes": holding.notes,
            "current_price": current_price,
            "price_as_of": price_date,
            "price_source": price_source,
            "price_status": price_status,
            "cost_basis": float(cost_basis),
            "market_value": float(market_value) if market_value is not None else None,
            "unrealized_pnl": float(market_value - cost_basis) if market_value is not None else None,
            "target_weight": targets.get(asset.id),
            "current_weight": None,
        })

    all_prices_available = bool(holdings) and all(item["market_value"] is not None for item in holdings)
    any_stale = any(item["price_status"] == "STALE" for item in holdings)
    cost_basis_total = sum((Decimal(str(item["cost_basis"])) for item in holdings), Decimal("0"))
    total_value = sum((Decimal(str(item["market_value"])) for item in holdings), Decimal("0")) if all_prices_available else None
    total_pnl = total_value - cost_basis_total if total_value is not None else None

    if total_value is not None and total_value > 0:
        for item in holdings:
            item["current_weight"] = item["market_value"] / float(total_value)

    sector_values: dict[str, float] = {}
    role_values: dict[str, float] = {"CORE": 0.0, "SATELLITE": 0.0, "UNASSIGNED": 0.0}
    if all_prices_available:
        for item in holdings:
            sector = item["sector"] or "UNKNOWN"
            sector_values[sector] = sector_values.get(sector, 0.0) + float(item["market_value"])
            role_values[item["role"]] += float(item["market_value"])
    sector_allocation = [
        {"sector": sector, "market_value": value, "weight": value / float(total_value)}
        for sector, value in sorted(sector_values.items())
    ] if total_value is not None and total_value > 0 else []
    role_allocation = [
        {"role": role, "market_value": value, "weight": value / float(total_value)}
        for role, value in role_values.items()
    ] if total_value is not None and total_value > 0 else []

    single_limit = float(account.single_name_limit) if account and account.single_name_limit is not None else None
    sector_limit = float(account.sector_limit) if account and account.sector_limit is not None else None
    warnings = []
    if holdings and not all_prices_available:
        missing_symbols = [item["symbol"] for item in holdings if item["market_value"] is None]
        warnings.append({"code": "MISSING_PRICE", "symbols": missing_symbols, "message": "Total value and normalized allocations are withheld until every holding has a canonical price."})
    if any_stale:
        warnings.append({"code": "STALE_PRICE", "symbols": [item["symbol"] for item in holdings if item["price_status"] == "STALE"], "message": "At least one holding price is more than seven days old."})
    if holdings and single_limit is None:
        warnings.append({"code": "SINGLE_NAME_LIMIT_UNSET", "message": "No single-name concentration threshold is configured."})
    if holdings and sector_limit is None:
        warnings.append({"code": "SECTOR_LIMIT_UNSET", "message": "No sector concentration threshold is configured."})
    if single_limit is not None and total_value and total_value > 0:
        for item in holdings:
            if item["current_weight"] is not None and item["current_weight"] > single_limit:
                warnings.append({"code": "SINGLE_NAME_CONCENTRATION", "symbol": item["symbol"], "weight": item["current_weight"], "limit": single_limit})
    if sector_limit is not None:
        for item in sector_allocation:
            if item["weight"] > sector_limit:
                warnings.append({"code": "SECTOR_CONCENTRATION", "sector": item["sector"], "weight": item["weight"], "limit": sector_limit})

    return {
        "portfolio_id": PORTFOLIO_ID,
        "as_of_date": as_of,
        "status": "EMPTY" if not holdings else "AVAILABLE" if all_prices_available and not any_stale else "PARTIAL",
        "summary": {
            "holdings_count": len(holdings),
            "total_value": float(total_value) if total_value is not None else None,
            "cost_basis": float(cost_basis_total),
            "unrealized_pnl": float(total_pnl) if total_pnl is not None else None,
            "currency": account.base_currency if account else "VND",
            "value_status": "AVAILABLE" if total_value is not None else "INSUFFICIENT_DATA",
        },
        "holdings": holdings,
        "allocation": {
            "status": "AVAILABLE" if total_value is not None and total_value > 0 else "INSUFFICIENT_DATA",
            "sector": sector_allocation,
            "core_satellite": role_allocation,
        },
        "concentration": {
            "single_name_limit": single_limit,
            "sector_limit": sector_limit,
            "status": "AVAILABLE" if total_value is not None else "INSUFFICIENT_DATA",
            "warnings": warnings,
        },
        "risk_exposure": {"status": "INSUFFICIENT_DATA", "value": None, "note": "Portfolio risk aggregation requires evidence-backed per-asset risk scores."},
        "factor_exposure": {"status": "INSUFFICIENT_DATA", "value": None, "note": "Portfolio factor aggregation requires evidence-backed factor profiles."},
    }


def portfolio_fit(session: Session, as_of: date) -> dict[str, Any]:
    dashboard = portfolio_dashboard(session, as_of)
    fit_items = []
    for holding in dashboard["holdings"]:
        asset = canonical_asset(session, holding["symbol"])
        research = build_research_workspace(session, holding["symbol"], as_of) if asset else None
        fit_items.append({
            "symbol": holding["symbol"],
            "portfolio_role": holding["role"],
            "current_weight": holding["current_weight"],
            "target_weight": holding["target_weight"],
            "sector": holding["sector"],
            "sector_weight": next((item["weight"] for item in dashboard["allocation"]["sector"] if item["sector"] == (holding["sector"] or "UNKNOWN")), None),
            "sector_overlap": "AVAILABLE" if holding["sector"] else "INSUFFICIENT_DATA",
            "opportunity_score": research.opportunity["score"] if research else None,
            "confidence": research.opportunity["confidence"] if research else "INSUFFICIENT",
            "risk_score": research.risk["overall_score"] if research else None,
            "risk_overlap": "INSUFFICIENT_DATA",
            "factor_overlap": "INSUFFICIENT_DATA",
            "horizon_compatibility": "INSUFFICIENT_DATA",
            "status": "INSUFFICIENT_DATA",
            "note": "Portfolio Fit is separate from opportunity/confidence/risk and awaits sourced factor, risk, and horizon-fit inputs.",
        })
    return {"portfolio_id": PORTFOLIO_ID, "as_of_date": as_of, "status": "INSUFFICIENT_DATA" if fit_items else "EMPTY", "items": fit_items}


def dca_plan_view(session: Session, as_of: date) -> dict[str, Any]:
    account = session.get(PersonalPortfolio, PORTFOLIO_ID)
    plan = session.query(DcaPlan).filter(DcaPlan.portfolio_id == PORTFOLIO_ID).first()
    dashboard = portfolio_dashboard(session, as_of)
    monthly_amount = plan.monthly_amount if plan else DEFAULT_DCA_AMOUNT
    core_pct = Decimal(plan.core_pct) if plan else DEFAULT_CORE_PCT
    satellite_pct = Decimal(plan.satellite_pct) if plan else DEFAULT_SATELLITE_PCT
    reserve_pct = Decimal("1") - core_pct - satellite_pct

    routes = []
    suggested_reserve = monthly_amount
    target_rows = session.query(PortfolioTarget, Asset).join(Asset, PortfolioTarget.asset_id == Asset.id).filter(
        PortfolioTarget.portfolio_id == PORTFOLIO_ID
    ).all() if account else []
    if dashboard["allocation"]["status"] == "AVAILABLE" and target_rows:
        current_weights = {item["symbol"]: item["current_weight"] or 0.0 for item in dashboard["holdings"]}
        gaps = [
            (asset.symbol, float(target.target_weight) - current_weights.get(asset.symbol, 0.0), float(target.target_weight))
            for target, asset in target_rows
        ]
        positive_gaps = sorted((row for row in gaps if row[1] > 0), key=lambda row: row[1], reverse=True)[:2]
        total_gap = sum(row[1] for row in positive_gaps)
        if total_gap > 0:
            route_budget = int(monthly_amount * float(core_pct + satellite_pct))
            for symbol, gap, target_weight in positive_gaps:
                amount = int(route_budget * gap / total_gap / 1000) * 1000
                if amount:
                    routes.append({"symbol": symbol, "amount": amount, "target_weight": target_weight, "weight_gap": gap, "status": "MODEL_OUTPUT"})
            suggested_reserve = monthly_amount - sum(route["amount"] for route in routes)

    return {
        "saved": plan is not None,
        "status": "AVAILABLE" if plan and target_rows and dashboard["allocation"]["status"] == "AVAILABLE" else "INSUFFICIENT_DATA",
        "monthly_amount": monthly_amount,
        "range": {"minimum": 300000, "maximum": 400000, "currency": "VND"},
        "core_pct": float(core_pct),
        "satellite_pct": float(satellite_pct),
        "reserve_pct": float(reserve_pct),
        "current_allocation": dashboard["allocation"],
        "routes": routes,
        "unused_or_satellite_reserve": suggested_reserve,
        "note": "Decision-support estimate only. It does not create orders or transactions; default monthly amount is an editable personal demo setting." if plan is None else "Routing is limited to at most two underweight targets per monthly contribution. No orders are executed.",
    }


def compare_snapshots(previous: dict[str, Any], current: dict[str, Any], threshold: Optional[float] = None) -> list[dict[str, Any]]:
    changes = []
    before_rows = previous.get("holdings", []) if isinstance(previous, dict) else []
    current_rows = current.get("holdings", []) if isinstance(current, dict) else []
    before_holdings = {
        item["symbol"]: item
        for item in before_rows
        if isinstance(item, dict) and isinstance(item.get("symbol"), str)
    }
    current_holdings = {
        item["symbol"]: item
        for item in current_rows
        if isinstance(item, dict) and isinstance(item.get("symbol"), str)
    }

    for symbol in sorted(before_holdings.keys() | current_holdings.keys()):
        if symbol not in before_holdings:
            holding = current_holdings[symbol]
            changes.append({
                "claim_type": "FACT",
                "responsible_module": "portfolio_holdings",
                "symbol": symbol,
                "kind": "HOLDING_ADDED",
                "direction": "ADDED",
                "before": None,
                "after": holding,
                "change_pct": None,
                "status": "AVAILABLE" if holding.get("current_price") is not None else "INSUFFICIENT_DATA",
                "materiality": "OBSERVED_UNCLASSIFIED",
                "evidence": {"claim_type": "FACT", "source": holding.get("price_source"), "observation_date": holding.get("price_as_of"), "data_origin": "LOCAL_PERSONAL_PORTFOLIO"},
            })
            continue
        if symbol not in current_holdings:
            holding = before_holdings[symbol]
            changes.append({
                "claim_type": "FACT",
                "responsible_module": "portfolio_holdings",
                "symbol": symbol,
                "kind": "HOLDING_REMOVED",
                "direction": "REMOVED",
                "before": holding,
                "after": None,
                "change_pct": None,
                "status": "AVAILABLE",
                "materiality": "OBSERVED_UNCLASSIFIED",
                "evidence": {"claim_type": "FACT", "source": holding.get("price_source"), "observation_date": holding.get("price_as_of"), "data_origin": "LOCAL_PERSONAL_PORTFOLIO"},
            })
            continue

        before = before_holdings[symbol]
        after = current_holdings[symbol]
        for key, kind in (("current_price", "PRICE_CHANGE"), ("current_weight", "ALLOCATION_DRIFT")):
            old_value = before.get(key)
            new_value = after.get(key)
            old_numeric = float(old_value) if isinstance(old_value, (int, float, Decimal)) and not isinstance(old_value, bool) else None
            new_numeric = float(new_value) if isinstance(new_value, (int, float, Decimal)) and not isinstance(new_value, bool) else None
            missing = old_value is None or new_value is None
            if missing:
                direction = "DATA_AVAILABLE" if old_value is None and new_value is not None else "DATA_MISSING" if new_value is None and old_value is not None else "INSUFFICIENT_DATA"
                status = "INSUFFICIENT_DATA"
                delta = None
                pct_change = None
                material = False
            elif old_numeric is not None and new_numeric is not None:
                delta = new_numeric - old_numeric
                unchanged = isclose(old_numeric, new_numeric, rel_tol=1e-6, abs_tol=1e-8)
                direction = "UNCHANGED" if unchanged else "INCREASED" if delta > 0 else "DECREASED"
                status = after.get("price_status", "AVAILABLE") if kind == "PRICE_CHANGE" else "AVAILABLE"
                pct_change = delta / abs(old_numeric) if old_numeric != 0 else None
                material = not unchanged and threshold is not None and pct_change is not None and abs(pct_change) >= threshold
            else:
                delta = None
                pct_change = None
                direction = "UNCHANGED" if old_value == new_value else "CHANGED"
                status = "AVAILABLE"
                material = False
            changes.append({
                "claim_type": "UNCERTAINTY" if status == "INSUFFICIENT_DATA" else "MODEL_OUTPUT",
                "responsible_module": "portfolio_market_value" if kind == "PRICE_CHANGE" else "portfolio_allocation",
                "symbol": symbol,
                "kind": kind,
                "direction": direction,
                "before": old_value,
                "after": new_value,
                "delta": delta,
                "change_pct": pct_change,
                "status": status,
                "materiality": "MATERIAL" if material else "OBSERVED_UNCLASSIFIED",
                "evidence": {
                    "claim_type": "FACT" if after.get("price_source") else "UNCERTAINTY",
                    "source": after.get("price_source"),
                    "observation_date": after.get("price_as_of"),
                    "data_origin": "SEEDED_OR_UNTRACED" if (after.get("price_source") or "").upper() in {"HOSE_CSV", "MARKETDATACSV"} else "CANONICAL_DATABASE_RECORD",
                    "freshness": after.get("price_status", "INSUFFICIENT_DATA"),
                },
            })
    return changes
