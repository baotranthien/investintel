from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Asset, Price
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.sector_models import get_sector_for_symbol
from services.fundamentals.snapshot import FundamentalSnapshotBuilder

_UNSET_DATASET = object()


def compute_beta_and_wacc(
    session: Session,
    sym: str,
    sector: str,
    de_ratio: Optional[float],
    as_of_date: Optional[date] = None,
) -> tuple[float, float, float]:
    """Compute Blume-adjusted beta, CAPM cost of equity, and after-tax WACC."""
    beta = 1.0
    try:
        stock_asset = session.query(Asset).filter(Asset.symbol == sym).first()
        mkt_asset = session.query(Asset).filter(Asset.symbol == "VNINDEX").first()
        if stock_asset:
            stock_q = session.query(Price.observation_date, Price.raw_close).filter(
                Price.asset_id == stock_asset.id,
                Price.status == "VALID",
            )
            if as_of_date:
                stock_q = stock_q.filter(Price.observation_date <= as_of_date)
            stock_prices = dict(stock_q.order_by(Price.observation_date.desc()).limit(252).all())

            mkt_prices: dict[date, float] = {}
            if mkt_asset:
                mkt_q = session.query(Price.observation_date, Price.raw_close).filter(
                    Price.asset_id == mkt_asset.id,
                    Price.status == "VALID",
                )
                if as_of_date:
                    mkt_q = mkt_q.filter(Price.observation_date <= as_of_date)
                mkt_prices = dict(mkt_q.order_by(Price.observation_date.desc()).limit(252).all())

            if len(mkt_prices) < 120:
                vn100_asset = session.query(Asset).filter(Asset.symbol == "VN100").first()
                if vn100_asset:
                    vn100_q = session.query(Price.observation_date, Price.raw_close).filter(
                        Price.asset_id == vn100_asset.id,
                        Price.status == "VALID",
                    )
                    if as_of_date:
                        vn100_q = vn100_q.filter(Price.observation_date <= as_of_date)
                    vn100_prices = dict(vn100_q.order_by(Price.observation_date.desc()).limit(252).all())
                    if len(vn100_prices) > len(mkt_prices):
                        mkt_prices = vn100_prices

            common_dates = sorted(set(stock_prices.keys()).intersection(set(mkt_prices.keys())))
            paired_returns = []
            for i in range(1, len(common_dates)):
                d_prev = common_dates[i - 1]
                d_curr = common_dates[i]
                if (d_curr - d_prev).days > 7:
                    continue
                s_prev = stock_prices[d_prev]
                s_curr = stock_prices[d_curr]
                m_prev = mkt_prices[d_prev]
                m_curr = mkt_prices[d_curr]
                if s_prev <= 0 or m_prev <= 0:
                    continue
                paired_returns.append(((s_curr - s_prev) / s_prev, (m_curr - m_prev) / m_prev))

            if len(paired_returns) >= 30:
                r_stock = [p[0] for p in paired_returns]
                r_mkt = [p[1] for p in paired_returns]
                mean_s = sum(r_stock) / len(r_stock)
                mean_m = sum(r_mkt) / len(r_mkt)
                cov = sum((r_stock[i] - mean_s) * (r_mkt[i] - mean_m) for i in range(len(r_stock))) / (len(r_stock) - 1)
                var_m = sum((r_mkt[i] - mean_m) ** 2 for i in range(len(r_mkt))) / (len(r_mkt) - 1)
                if var_m > 1e-8:
                    raw_beta = cov / var_m
                    blume_beta = 0.67 * raw_beta + 0.33 * 1.0
                    beta = max(0.70, min(1.50, blume_beta))
    except Exception:
        beta = 1.0

    rf = 0.048
    erp = 0.070
    cost_of_equity = max(0.110, min(0.160, rf + beta * erp))

    kd_after_tax = 0.085 * (1.0 - 0.20)
    norm_sector = (sector or "").upper()
    if norm_sector in ("BANK", "BANKING", "SECURITIES", "FINANCIALS", "FINANCIAL SERVICES", "INSURANCE"):
        wacc = cost_of_equity
    else:
        de = max(0.0, float(de_ratio)) if de_ratio is not None else 0.5
        d_weight = min(0.65, max(0.0, de / (1.0 + de)))
        e_weight = 1.0 - d_weight
        wacc_raw = (cost_of_equity * e_weight) + (kd_after_tax * d_weight)
        wacc = max(0.100, min(0.155, wacc_raw))

    return round(beta, 3), round(cost_of_equity, 4), round(wacc, 4)


def _val_and_unit(d: Any, key: str) -> tuple[Any, Any]:
    if not isinstance(d, dict):
        return None, None
    v = d.get(key)
    if isinstance(v, dict):
        return v.get("value"), v.get("unit")
    return v, None


def _val(d: Any, key: str) -> Any:
    return _val_and_unit(d, key)[0]


def _norm_ratio(d: Any, key: str, force_abs: bool = False) -> Optional[float]:
    val, unit = _val_and_unit(d, key)
    if val is None:
        return None
    if force_abs:
        val = abs(val)
    if unit in ("%", "PERCENT"):
        return float(val) / 100.0
    if abs(float(val)) > 1.0:
        return float(val) / 100.0
    return float(val)


def load_fundamentals_for_valuation(
    symbol: str,
    as_of_date: Optional[date] = None,
    session: Optional[Session] = None,
    peer_res: Optional[Any] = None,
    dataset: Any = _UNSET_DATASET,
    preloaded_snapshot: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Canonical fundamental input loader shared across /valuation, /research, and /ai.
    Guarantees identical DCF, Relative, Residual Income, and Composite Fair Value outputs.
    """
    sym = symbol.upper()
    if dataset is _UNSET_DATASET:
        if session is not None:
            dataset = FinancialRepository(session).get_financial_dataset(sym, as_of_date=as_of_date)
        else:
            with FinancialRepository() as repo:
                dataset = repo.get_financial_dataset(sym, as_of_date=as_of_date)
    if not dataset or not dataset.get("income_annual"):
        return None

    canonical_sector = get_sector_for_symbol(sym, dataset.get("sector"))
    if preloaded_snapshot is not None:
        snapshot = preloaded_snapshot
    else:
        builder = FundamentalSnapshotBuilder(sym, canonical_sector)
        snapshot = builder.build_snapshot(
            income_quarters=dataset["income_quarters"],
            income_annual=dataset["income_annual"],
            balance_annual=dataset["balance_annual"],
            cashflow_annual=dataset["cashflow_annual"],
            as_of_date=as_of_date,
            shares_outstanding=dataset.get("shares_outstanding"),
            sources=dataset.get("sources"),
        )

    per_share = snapshot.get("per_share", {})
    profitability = snapshot.get("profitability", {})
    balance_sheet = snapshot.get("balance_sheet", {})
    ttm = snapshot.get("ttm", {})
    growth = snapshot.get("growth", {})
    cash_flow = snapshot.get("cash_flow", {})

    revenue_yoy = _norm_ratio(growth, "revenue_yoy")
    revenue_cagr_3y = _norm_ratio(growth, "revenue_cagr_3y")
    operating_margin = (
        _norm_ratio(profitability, "operating_margin")
        or _norm_ratio(profitability, "ebit_margin")
        or _norm_ratio(profitability, "net_margin")
    )

    de_ratio = _val(balance_sheet, "de_ratio")
    fcf_ttm = _val(cash_flow, "fcf")
    cfo_ttm = _val(cash_flow, "cfo")
    capex_to_revenue = (
        _norm_ratio(cash_flow, "capex_to_revenue", force_abs=True)
        or _norm_ratio(profitability, "capex_to_revenue", force_abs=True)
    )

    peer_pe = None
    peer_pb = None
    beta = 1.0
    cost_of_equity = 0.12
    wacc = 0.12
    own_session = session is None
    active_session = session if session is not None else SessionLocal()
    try:
        resolved_peers = peer_res
        if resolved_peers is None:
            from services.valuation.peers import PeerComparisonEngine
            resolved_peers = PeerComparisonEngine(active_session).compare_peers(sym, as_of=as_of_date)
        if resolved_peers and resolved_peers.peer_median_pe:
            peer_pe = resolved_peers.peer_median_pe
        if resolved_peers and resolved_peers.peer_median_pb:
            peer_pb = resolved_peers.peer_median_pb

        beta, cost_of_equity, wacc = compute_beta_and_wacc(
            session=active_session,
            sym=sym,
            sector=canonical_sector,
            de_ratio=de_ratio,
            as_of_date=as_of_date,
        )
    except Exception:
        pass
    finally:
        if own_session:
            active_session.close()

    return {
        "symbol": sym,
        "sector": canonical_sector,
        "eps_ttm": snapshot.get("eps_ttm") or _val(per_share, "eps_ttm"),
        "is_eps_estimate": per_share.get("is_eps_estimate", False),
        "eps_diagnostic_reason": per_share.get("eps_diagnostic_reason"),
        "bvps": snapshot.get("bvps") or _val(per_share, "bvps"),
        "shares_outstanding": dataset.get("shares_outstanding") or _val(per_share, "shares_basic") or 1_000_000_000,
        "revenue_ttm": snapshot.get("revenue_ttm") or _val(ttm, "revenue") or snapshot.get("revenue_annual") or (dataset["income_annual"][-1].get("revenue") if dataset.get("income_annual") else None),
        "revenue_annual": snapshot.get("revenue_annual") or (dataset["income_annual"][-1].get("revenue") if dataset.get("income_annual") else None),
        "net_income_ttm": snapshot.get("net_income_ttm") or _val(ttm, "net_income_parent") or _val(ttm, "net_income") or snapshot.get("net_income_annual") or (dataset["income_annual"][-1].get("net_income_parent") if dataset.get("income_annual") else None),
        "net_debt": _val(balance_sheet, "net_debt"),
        "roe": _val(profitability, "roe"),
        "peer_pe": peer_pe,
        "hist_pe": None,
        "peer_pb": peer_pb,
        "hist_pb": None,
        "sources": dataset.get("sources", ["CANONICAL_DATABASE"]),
        "use_dynamic_assumptions": True,
        "beta": beta,
        "cost_of_equity": cost_of_equity,
        "wacc": wacc,
        "revenue_yoy": revenue_yoy,
        "revenue_cagr_3y": revenue_cagr_3y,
        "operating_margin": operating_margin,
        "de_ratio": de_ratio,
        "fcf_ttm": fcf_ttm,
        "cfo_ttm": cfo_ttm,
        "capex_to_revenue": capex_to_revenue,
    }


def get_latest_price(
    symbol: str,
    as_of_date: Optional[date] = None,
    session: Optional[Session] = None,
) -> Optional[float]:
    """Get canonical latest price for symbol on or before as_of_date."""
    own_session = session is None
    active_session = session if session is not None else SessionLocal()
    try:
        from services.market.canonical_price import CanonicalPriceResolver
        return CanonicalPriceResolver.get_latest_price_value(active_session, symbol, as_of_date)
    finally:
        if own_session:
            active_session.close()


def get_asset_sector(
    symbol: str,
    session: Optional[Session] = None,
) -> Optional[str]:
    """Get sector from canonical assets table."""
    own_session = session is None
    active_session = session if session is not None else SessionLocal()
    try:
        asset = active_session.query(Asset).filter(Asset.symbol == symbol.upper()).first()
        return asset.sector if asset else None
    finally:
        if own_session:
            active_session.close()
