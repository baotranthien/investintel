# -*- coding: utf-8 -*-
"""
Deep Company Analysis Engine — Phase 4A.
Provides a comprehensive 7-section institutional investment analysis:
1. Business Overview & Capitalization
2. Revenue & Growth Trajectory
3. Profitability & Operational Efficiency
4. Capital Structure, Debt & Financial Health
5. Cash Flow & Earnings Quality
6. Valuation & Fair Value Estimates
7. Strategic Risks, Catalysts & Sensitivities
"""
from datetime import date
from typing import Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import Asset, Price, PeerGroup
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.valuation.builder import ValuationSnapshotBuilder
from services.research.workspace import build_research_workspace


class DeepCompanyAnalysis(BaseModel):
    symbol: str
    name: str
    as_of_date: date
    status: str
    business_overview: dict[str, Any]
    revenue_growth: dict[str, Any]
    profitability: dict[str, Any]
    financial_health: dict[str, Any]
    cash_flow_quality: dict[str, Any]
    valuation: dict[str, Any]
    risks_and_catalysts: dict[str, Any]


class CompanyDeepAnalysisEngine:
    """Produces the 7-section deep company investment analysis with deterministic grounding."""

    def __init__(self, session: Session):
        self.session = session

    def generate_analysis(self, symbol: str, as_of: Optional[date] = None) -> DeepCompanyAnalysis:
        as_of = as_of or date.today()
        sym = symbol.upper()

        # 1. Load Workspace & Asset
        asset = self.session.query(Asset).filter(Asset.symbol == sym).first()
        asset_name = asset.name if asset else f"{sym} Corporation"
        repo = FinancialRepository(self.session)
        dataset = repo.get_financial_dataset(sym, as_of_date=as_of) or {}
        sector = (asset.sector if asset and asset.sector else None) or dataset.get("sector") or "GENERAL"
        shares_out = dataset.get("shares_outstanding")

        ws = build_research_workspace(self.session, sym, as_of)
        if not ws:
            raise ValueError(f"Could not build research workspace for symbol '{sym}'")
        metrics = ws.fundamentals.get("metrics", {})
        price_info = ws.price or {}
        current_price = price_info.get("value")

        # Fallback price lookup if workspace price is missing
        if current_price is None and asset:
            p_row = (
                self.session.query(Price)
                .filter(Price.asset_id == asset.id, Price.status == "VALID", Price.observation_date <= as_of)
                .order_by(Price.observation_date.desc())
                .first()
            )
            if p_row:
                current_price = float(p_row.adjusted_close if p_row.adjusted_close is not None else p_row.raw_close)

        def _val(m_key: str, default: Any = None) -> Any:
            m = metrics.get(m_key)
            if isinstance(m, dict):
                return m.get("value", default)
            return getattr(m, "value", default) if m else default

        def _unit(m_key: str, default: str = "") -> str:
            m = metrics.get(m_key)
            if isinstance(m, dict):
                return m.get("unit", default)
            return getattr(m, "unit", default) if m else default

        market_cap_bil = None
        if current_price and shares_out:
            market_cap_bil = round((current_price * shares_out) / 1_000_000_000, 2)

        # ─────────────────────────────────────────────────────────────
        # SECTION 1: Business Overview
        # ─────────────────────────────────────────────────────────────
        business_overview = {
            "symbol": sym,
            "name": asset_name,
            "sector": sector,
            "exchange": asset.exchange if asset else "HOSE",
            "current_price": current_price,
            "shares_outstanding": shares_out,
            "market_cap_billion_vnd": market_cap_bil,
            "data_origin": "CANONICAL_DATABASE",
            "summary": (
                f"{asset_name} ({sym}) niêm yết tại sàn {asset.exchange if asset else 'HOSE'}, "
                f"hoạt động trong ngành {sector} với quy mô vốn hóa ước đạt "
                f"{market_cap_bil:,.1f} tỷ VND." if market_cap_bil else f"{asset_name} ({sym}) hoạt động trong ngành {sector}."
            )
        }

        # ─────────────────────────────────────────────────────────────
        # SECTION 2: Revenue & Growth Trajectory
        # ─────────────────────────────────────────────────────────────
        revenue_val = _val("revenue")
        revenue_growth = {
            "revenue_ttm": revenue_val,
            "revenue_yoy": _val("revenue_yoy"),
            "net_income_yoy": _val("net_income_yoy"),
            "eps_yoy": _val("eps_yoy"),
            "revenue_cagr_3y": _val("revenue_cagr_3y"),
            "revenue_cagr_5y": _val("revenue_cagr_5y"),
            "quarterly_history": [
                {
                    "quarter": q.get("fiscal_quarter"),
                    "year": q.get("fiscal_year"),
                    "period_end": str(q.get("fiscal_period_end")),
                    "revenue": q.get("revenue"),
                    "net_income": q.get("net_income_parent") or q.get("net_income"),
                    "gross_profit": q.get("gross_profit"),
                }
                for q in (dataset.get("income_quarters") or [])[-4:]
            ],
            "assessment": (
                "Tăng trưởng doanh thu duy trì xu hướng tích cực."
                if (_val("revenue_yoy") or 0) > 10 else
                "Doanh thu đi ngang hoặc tăng trưởng vừa phải."
                if (_val("revenue_yoy") or 0) >= 0 else
                "Doanh thu có dấu hiệu suy giảm so với cùng kỳ."
            )
        }

        # ─────────────────────────────────────────────────────────────
        # SECTION 3: Profitability & Operational Efficiency
        # ─────────────────────────────────────────────────────────────
        gm = _val("gross_margin")
        nm = _val("net_margin")
        roe = _val("roe")
        roa = _val("roa")
        roic = _val("roic")

        profitability = {
            "gross_margin": gm,
            "ebit_margin": _val("ebit_margin"),
            "ebitda_margin": _val("ebitda_margin"),
            "net_margin": nm,
            "roe": roe,
            "roa": roa,
            "roic": roic,
            "assessment": (
                f"Khả năng sinh lời vượt trội với ROE đạt {roe:.1f}% và biên gộp {gm:.1f}%."
                if (roe or 0) > 20 and (gm or 0) > 25 else
                f"Khả năng sinh lời ổn định (ROE {roe:.1f}%, biên ròng {nm:.1f}%)."
                if (roe or 0) > 12 else
                "Hiệu quả sinh lời ở mức trung bình hoặc đang đối mặt áp lực chi phí."
            )
        }

        # ─────────────────────────────────────────────────────────────
        # SECTION 4: Capital Structure & Financial Health
        # ─────────────────────────────────────────────────────────────
        de = _val("de_ratio")
        debt_assets = _val("debt_to_assets")
        cr = _val("current_ratio")
        qr = _val("quick_ratio")
        net_debt_ebitda = _val("net_debt_ebitda")
        gross_debt = _val("gross_debt") or _val("total_debt")
        cash_val = _val("cash")
        net_debt = _val("net_debt")

        financial_health = {
            "debt_to_assets": debt_assets,
            "de_ratio": de,
            "net_debt_ebitda": net_debt_ebitda,
            "current_ratio": cr,
            "quick_ratio": qr,
            "interest_coverage": _val("interest_coverage"),
            "gross_debt": gross_debt,
            "cash": cash_val,
            "net_debt": net_debt,
            "is_net_cash": (net_debt is not None and net_debt < 0),
            "assessment": (
                "Cấu trúc vốn lành mạnh, tiền mặt vượt trội tổng nợ vay (vị thế tiền mặt ròng)."
                if (net_debt is not None and net_debt < 0) else
                "Đòn bẩy tài chính ở mức an toàn, áp lực nợ vay được kiểm soát tốt."
                if (de is not None and de < 0.8) else
                "Đòn bẩy tài chính ở mức cần theo dõi."
            )
        }

        # ─────────────────────────────────────────────────────────────
        # SECTION 5: Cash Flow & Earnings Quality
        # ─────────────────────────────────────────────────────────────
        cfo = _val("cfo")
        capex = _val("capex")
        fcf = _val("fcf")
        cfo_ni = _val("cfo_to_ni")
        fcf_ni = _val("fcf_to_ni")

        cash_flow_quality = {
            "cfo": cfo,
            "capex": capex,
            "fcf": fcf,
            "cfo_to_ni": cfo_ni,
            "fcf_to_ni": fcf_ni,
            "assessment": (
                "Dòng tiền thuần từ kinh doanh (CFO) và dòng tiền tự do (FCF) dồi dào, chất lượng lợi nhuận cao."
                if (cfo or 0) > 0 and (fcf or 0) > 0 else
                "Dòng tiền kinh doanh dương nhưng dòng tiền tự do chịu áp lực đầu tư mở rộng (Capex)."
                if (cfo or 0) > 0 else
                "Dòng tiền kinh doanh âm, cần chú ý quản trị vốn lưu động."
            )
        }

        # ─────────────────────────────────────────────────────────────
        # SECTION 6: Valuation & Fair Value Estimates
        # ─────────────────────────────────────────────────────────────
        val_metrics = ws.valuation.get("metrics", {})
        pe = val_metrics.get("pe", {}).get("value")
        pb = val_metrics.get("pb", {}).get("value")
        ev_ebitda = val_metrics.get("ev_ebitda", {}).get("value")
        div_yield = val_metrics.get("dividend_yield", {}).get("value")

        # Intrinsic Valuation Builder
        builder = ValuationSnapshotBuilder(sym, sector)
        val_snapshot = builder.build(
            fundamentals={
                "eps_ttm": _val("eps_ttm", 0),
                "bvps": _val("bvps", 0),
                "shares_outstanding": shares_out or 100_000_000,
                "revenue_ttm": revenue_val,
                "net_debt": net_debt or 0.0,
                "roe": roe or 15.0,
            },
            current_price=current_price or 100_000.0,
            as_of=as_of
        )
        comp_fv = val_snapshot.composite_fair_value
        dcf_method = next((m for m in val_snapshot.methods if m.method == "DCF"), None)

        valuation = {
            "current_price": current_price,
            "pe": pe,
            "pb": pb,
            "ev_ebitda": ev_ebitda,
            "dividend_yield": div_yield,
            "bvps": _val("bvps"),
            "eps_ttm": _val("eps_ttm"),
            "fair_value_composite": {
                "bear": round(comp_fv.range.bear, 0) if comp_fv else None,
                "base": round(comp_fv.range.base, 0) if comp_fv else None,
                "bull": round(comp_fv.range.bull, 0) if comp_fv else None,
                "confidence": comp_fv.confidence if comp_fv else "LOW",
            },
            "dcf_intrinsic_value": {
                "bear": round(dcf_method.fair_value.bear, 0) if dcf_method else None,
                "base": round(dcf_method.fair_value.base, 0) if dcf_method else None,
                "bull": round(dcf_method.fair_value.bull, 0) if dcf_method else None,
            } if dcf_method else None,
            "margin_of_safety_pct": round(val_snapshot.margin_of_safety * 100, 1) if val_snapshot.margin_of_safety else None,
        }

        # ─────────────────────────────────────────────────────────────
        # SECTION 7: Strategic Risks, Catalysts & Sensitivities
        # ─────────────────────────────────────────────────────────────
        risk_mod = ws.risk or {}
        macro_sens = ws.macro_sensitivity or {}
        events_list = ws.events or []

        risks_and_catalysts = {
            "risk_score": risk_mod.get("overall_score"),
            "risk_status": risk_mod.get("status", "AVAILABLE"),
            "financial_flags": ws.fundamentals.get("flags", []),
            "macro_sensitivities": macro_sens.get("sensitivities", {}),
            "catalysts": [
                {
                    "title": ev.get("title"),
                    "date": ev.get("published_at"),
                    "severity": ev.get("severity"),
                    "sentiment": ev.get("sentiment"),
                }
                for ev in events_list[:5]
            ],
            "invalidation_triggers": [
                "Biên lợi nhuận gộp suy giảm liên tiếp trên 2 quý.",
                "Tỷ lệ nợ vay gia tăng đột biến vượt 50% tổng tài sản.",
                "Dòng tiền kinh doanh CFO âm kéo dài trên 1 năm tài chính.",
            ]
        }

        return DeepCompanyAnalysis(
            symbol=sym,
            name=asset_name,
            as_of_date=as_of,
            status=ws.status,
            business_overview=business_overview,
            revenue_growth=revenue_growth,
            profitability=profitability,
            financial_health=financial_health,
            cash_flow_quality=cash_flow_quality,
            valuation=valuation,
            risks_and_catalysts=risks_and_catalysts,
        )
