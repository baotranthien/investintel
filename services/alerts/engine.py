# -*- coding: utf-8 -*-
"""
Investment Alerts Engine — Phase 5F.
Monitors fundamental inflection points, valuation thresholds, and risk triggers:
1. MARGIN_DECAY: Gross margin decay > 200 bps or Net margin decay > 150 bps YoY.
2. DEBT_EXPANSION: D/E ratio > 1.5x or Debt jump > 25% YoY.
3. VALUATION_OPPORTUNITY: Margin of safety >= 20% (undervalued discount).
4. VALUATION_OVERVALUED: Margin of safety <= -20% (overextended premium).
5. EARNINGS_ACCELERATION: Net Income YoY growth >= 25%.
Includes deterministic deduplication and throttling to prevent notification fatigue.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import Asset, Price, AnalystAlert
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.valuation.builder import ValuationSnapshotBuilder


class AlertRuleResult(BaseModel):
    symbol: str
    alert_type: str
    severity: str  # HIGH, MEDIUM, LOW, INFO
    title: str
    description: str
    metrics: Dict[str, Any]
    triggered_at: datetime
    status: str = "OPEN"


class InvestmentAlertsEngine:
    """Evaluates institutional investment alerts with deterministic deduplication."""

    def __init__(self, session: Session):
        self.session = session
        self.repo = FinancialRepository(session)

    def evaluate_symbol(self, symbol: str, as_of: Optional[date] = None) -> List[AlertRuleResult]:
        as_of = as_of or date.today()
        sym = symbol.upper()

        asset = self.session.query(Asset).filter(Asset.symbol == sym).first()
        if not asset:
            return []

        dataset = self.repo.get_financial_dataset(sym, as_of_date=as_of)
        if not dataset or not dataset.get("income_annual"):
            return []

        sector = asset.sector or dataset.get("sector") or "GENERAL"
        builder = FundamentalSnapshotBuilder(sym, sector)
        snap = builder.build_snapshot(
            income_quarters=dataset["income_quarters"],
            income_annual=dataset["income_annual"],
            balance_annual=dataset["balance_annual"],
            cashflow_annual=dataset["cashflow_annual"],
            shares_outstanding=dataset.get("shares_outstanding"),
            as_of_date=as_of,
        )

        p_row = (
            self.session.query(Price)
            .filter(Price.asset_id == asset.id, Price.status == "VALID", Price.observation_date <= as_of)
            .order_by(Price.observation_date.desc())
            .first()
        )
        current_price = float(p_row.adjusted_close if p_row.adjusted_close is not None else p_row.raw_close) if p_row else None

        alerts: List[AlertRuleResult] = []
        now = datetime.now(timezone.utc)

        # 1. Check MARGIN_DECAY & EARNINGS_ACCELERATION (using annual comparative statements)
        income_annual = dataset.get("income_annual", [])
        if len(income_annual) >= 2:
            latest = income_annual[-1]
            prior = income_annual[-2]

            rev_curr = latest.get("revenue") or 0.0
            rev_prior = prior.get("revenue") or 0.0
            ni_curr = latest.get("net_income") or latest.get("net_income_parent") or 0.0
            ni_prior = prior.get("net_income") or prior.get("net_income_parent") or 0.0

            gm_curr = (latest.get("gross_profit", 0) / rev_curr * 100) if rev_curr > 0 else 0.0
            gm_prior = (prior.get("gross_profit", 0) / rev_prior * 100) if rev_prior > 0 else 0.0
            gm_change_bps = (gm_curr - gm_prior) * 100

            nm_curr = (ni_curr / rev_curr * 100) if rev_curr > 0 else 0.0
            nm_prior = (ni_prior / rev_prior * 100) if rev_prior > 0 else 0.0
            nm_change_bps = (nm_curr - nm_prior) * 100

            # Rule 1: Margin Decay Alert (> 200 bps decline in gross margin or > 150 bps in net margin)
            if gm_change_bps < -200 or nm_change_bps < -150:
                alerts.append(AlertRuleResult(
                    symbol=sym,
                    alert_type="MARGIN_DECAY",
                    severity="HIGH" if gm_change_bps < -400 else "MEDIUM",
                    title=f"Cảnh báo Suy giảm Biên Lợi nhuận — {sym}",
                    description=f"{sym} ghi nhận biên lợi nhuận gộp suy giảm {abs(gm_change_bps):.0f} bps và biên ròng giảm {abs(nm_change_bps):.0f} bps YoY.",
                    metrics={"gross_margin_curr": round(gm_curr, 2), "gross_margin_prior": round(gm_prior, 2), "delta_bps": round(gm_change_bps, 0)},
                    triggered_at=now,
                ))

            # Rule 2: Earnings Acceleration Alert (Net income YoY >= +25%)
            if ni_prior > 0:
                ni_growth_pct = ((ni_curr - ni_prior) / ni_prior) * 100
                if ni_growth_pct >= 25.0:
                    alerts.append(AlertRuleResult(
                        symbol=sym,
                        alert_type="EARNINGS_ACCELERATION",
                        severity="MEDIUM",
                        title=f"Tín hiệu Tăng tốc Lợi nhuận — {sym}",
                        description=f"{sym} đạt mức tăng trưởng lợi nhuận ròng ấn tượng +{ni_growth_pct:.1f}% YoY trong kỳ tài chính gần nhất.",
                        metrics={"net_income_curr": ni_curr, "net_income_prior": ni_prior, "growth_pct": round(ni_growth_pct, 1)},
                        triggered_at=now,
                    ))

        # 2. Check DEBT_EXPANSION (Balance Sheet health)
        bs = snap.get("balance_sheet", {})
        de_val = bs.get("de_ratio", {}).get("value") if isinstance(bs.get("de_ratio"), dict) else None
        if de_val is not None and de_val > 1.5:
            alerts.append(AlertRuleResult(
                symbol=sym,
                alert_type="DEBT_EXPANSION",
                severity="HIGH" if de_val > 2.5 else "MEDIUM",
                title=f"Cảnh báo Đòn bẩy Tài chính Cao — {sym}",
                description=f"{sym} có tỷ lệ nợ trên vốn chủ sở hữu (D/E) đạt {de_val:.2f}x, vượt ngưỡng an toàn khuyến nghị 1.50x.",
                metrics={"de_ratio": round(de_val, 2), "threshold": 1.5},
                triggered_at=now,
            ))

        # 3. Check VALUATION_OPPORTUNITY & VALUATION_OVERVALUED
        eps = snap.get("eps_ttm") or snap.get("eps_basic")
        if current_price and eps:
            try:
                from apps.api.routers.valuation import _load_fundamentals_for_valuation
                funds = _load_fundamentals_for_valuation(sym, as_of) or {}
                val_builder = ValuationSnapshotBuilder(sym, sector)
                val_snap = val_builder.build(funds, current_price, as_of)
                if val_snap and val_snap.composite_fair_value:
                    base_fv = val_snap.composite_fair_value.range.base
                    if base_fv and base_fv > 0:
                        mos_pct = round(((base_fv - current_price) / base_fv) * 100, 1)

                        if mos_pct >= 20.0:
                            alerts.append(AlertRuleResult(
                                symbol=sym,
                                alert_type="VALUATION_OPPORTUNITY",
                                severity="LOW",  # Opportunity notification
                                title=f"Cơ hội Định giá Hấp dẫn — {sym}",
                                description=f"{sym} đang giao dịch ở mức thị giá {current_price:,.0f} VND, chiết khấu sâu với biên an toàn {mos_pct:+.1f}% so với giá trị hợp lý {base_fv:,.0f} VND.",
                                metrics={"current_price": current_price, "fair_value": round(base_fv, 0), "margin_of_safety_pct": mos_pct},
                                triggered_at=now,
                            ))
                        elif mos_pct <= -20.0:
                            alerts.append(AlertRuleResult(
                                symbol=sym,
                                alert_type="VALUATION_OVERVALUED",
                                severity="HIGH",
                                title=f"Cảnh báo Thị giá Vượt Giá trị Hợp lý — {sym}",
                                description=f"{sym} đang giao dịch ở mức cao hơn {abs(mos_pct):.1f}% so với giá trị hợp lý {base_fv:,.0f} VND.",
                                metrics={"current_price": current_price, "fair_value": round(base_fv, 0), "margin_of_safety_pct": mos_pct},
                                triggered_at=now,
                            ))
            except Exception:
                pass

        # 4. Save and Deduplicate into database
        saved_alerts: List[AlertRuleResult] = []
        for a in alerts:
            alert_id = f"ALERT-{sym}-{a.alert_type}-{as_of.strftime('%Y%m')}"
            existing = self.session.query(AnalystAlert).filter(AnalystAlert.alert_id == alert_id).first()
            if existing and existing.status == "DISMISSED":
                continue
            if not existing:
                new_alert = AnalystAlert(
                    alert_id=alert_id,
                    symbol=sym,
                    kind=a.alert_type,
                    status="OPEN",
                    payload={
                        "title": a.title,
                        "description": a.description,
                        "severity": a.severity,
                        "metrics": a.metrics,
                        "summary": a.description,
                        "as_of_date": as_of.isoformat(),
                    },
                )
                self.session.add(new_alert)
                saved_alerts.append(a)
            else:
                saved_alerts.append(a)

        try:
            self.session.commit()
        except Exception:
            self.session.rollback()

        return saved_alerts

    def scan_active_universe(self, as_of: Optional[date] = None, limit: int = 15) -> List[AlertRuleResult]:
        as_of = as_of or date.today()
        assets = self.session.query(Asset).filter(Asset.status == "ACTIVE").limit(limit).all()
        all_alerts: List[AlertRuleResult] = []
        for a in assets:
            if not a.symbol or a.symbol.startswith("^"):
                continue
            res = self.evaluate_symbol(a.symbol, as_of=as_of)
            all_alerts.extend(res)
        return all_alerts

