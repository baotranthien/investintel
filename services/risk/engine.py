from datetime import date
from typing import Dict, Any, List
from .models import StockRiskProfile, RiskCategory, MacroSensitivity, DrawdownStats


class RiskEngine:
    @staticmethod
    def _cat(name: str, score: float, rtype: str, drivers: List[str]) -> RiskCategory:
        return RiskCategory(name=name, score=round(score, 1), type=rtype, drivers=drivers)

    @staticmethod
    def calculate_profile(symbol: str, fundamentals: Dict[str, Any], valuation: Dict[str, Any], as_of: date) -> StockRiskProfile:
        """
        Calculates 10 risk categories deterministically from structured inputs.
        Higher score = More risk (0-100).

        When fundamentals dict is empty, categories default to neutral estimates
        and are labeled [STUB_DATA] to signal missing real data.
        """
        data_available = bool(fundamentals)
        stub_note = " [STUB_DATA — kết nối nguồn dữ liệu để tính chính xác]"

        # Market Risk (Systematic)
        mom_score = fundamentals.get("price_momentum_score")
        beta_val = fundamentals.get("beta")
        mkt_score = 45.0 if data_available else 50.0
        if beta_val is not None:
            mkt_score = max(25.0, min(75.0, 45.0 + (float(beta_val) - 1.0) * 30.0))
        elif mom_score is not None:
            if mom_score <= -5.0:
                mkt_score = 60.0
            elif mom_score >= 5.0:
                mkt_score = 35.0
        market = RiskEngine._cat(
            "Market Risk", mkt_score, "SYSTEMATIC",
            [f"Beta chưa tính được{stub_note}"] if not data_available else ["Beta calculated from price history"]
        )

        # Business Risk (Idiosyncratic)
        revenue_concentration = fundamentals.get("revenue_concentration")
        roe_val = fundamentals.get("roe")
        biz_score = 30.0 if data_available else 50.0
        if revenue_concentration and revenue_concentration > 0.5:
            biz_score += 20
        if roe_val is not None:
            roe_norm = roe_val / 100.0 if abs(roe_val) > 1.0 else roe_val
            if roe_norm >= 0.20:
                biz_score = max(15.0, biz_score - 10.0)
            elif roe_norm < 0.08:
                biz_score = min(75.0, biz_score + 15.0)
        business = RiskEngine._cat(
            "Business Risk", biz_score, "IDIOSYNCRATIC",
            [f"Rủi ro kinh doanh chưa tính được{stub_note}"] if not data_available else ["Concentration, competitive position"]
        )

        # Financial Risk (Idiosyncratic) — Bank vs Industrial awareness
        sector_str = str(fundamentals.get("sector") or "").upper()
        is_bank = sector_str in ("BANK", "BANKING")
        de_ratio = fundamentals.get("de_ratio")
        npl_ratio = fundamentals.get("npl_ratio")
        llr_coverage = fundamentals.get("llr_coverage")
        fin_score = 30.0 if data_available else 50.0
        if is_bank and (npl_ratio is not None or llr_coverage is not None):
            if npl_ratio is not None:
                npl_pct = npl_ratio * 100.0 if npl_ratio < 0.20 else npl_ratio
                if npl_pct > 2.5:
                    fin_score = 60.0
                elif npl_pct > 1.8:
                    fin_score = 40.0
                else:
                    fin_score = 22.0
            if llr_coverage is not None:
                llr_pct = llr_coverage * 100.0 if llr_coverage < 5.0 else llr_coverage
                if llr_pct >= 120.0:
                    fin_score = max(15.0, fin_score - 8.0)
                elif llr_pct < 80.0:
                    fin_score = min(75.0, fin_score + 10.0)
            fin_driver = f"NPL = {npl_ratio}%, LLR = {llr_coverage}%"
        else:
            if de_ratio is not None and not is_bank:
                if de_ratio > 3.0: fin_score = 70.0
                elif de_ratio > 1.5: fin_score = 45.0
                elif de_ratio < 0.3: fin_score = 15.0
            fin_driver = f"D/E = {de_ratio:.2f}" if de_ratio is not None else f"D/E chưa có{stub_note}"
        financial = RiskEngine._cat(
            "Financial Risk", fin_score, "IDIOSYNCRATIC",
            [fin_driver]
        )

        # Valuation Risk (Idiosyncratic)
        margin_of_safety = valuation.get("margin_of_safety") if valuation else None
        val_score = 50.0
        if margin_of_safety is not None:
            if margin_of_safety < -0.20: val_score = 75.0
            elif margin_of_safety > 0.20: val_score = 20.0
        valuation_risk = RiskEngine._cat(
            "Valuation Risk", val_score, "IDIOSYNCRATIC",
            [f"Margin of Safety = {margin_of_safety:.1%}" if margin_of_safety is not None else f"Định giá chưa có{stub_note}"]
        )

        # Liquidity Risk (Idiosyncratic)
        avg_volume = fundamentals.get("avg_daily_volume_vnd")
        liq_score = 20.0 if data_available else 30.0
        if avg_volume is not None:
            if avg_volume < 1_000_000_000: liq_score = 50.0
            elif avg_volume < 5_000_000_000: liq_score = 30.0
        liquidity = RiskEngine._cat(
            "Liquidity Risk", liq_score, "IDIOSYNCRATIC",
            [f"Volume {avg_volume:,.0f} VND/ngày" if avg_volume else f"Volume chưa có{stub_note}"]
        )

        # Macro Risk (Systematic)
        macro = RiskEngine._cat("Macro Risk", 45.0, "SYSTEMATIC",
                                ["Rủi ro lãi suất, tỷ giá (cần dữ liệu sensitivity)"])

        # Geopolitical Risk (Systematic)
        geo = RiskEngine._cat("Geopolitical Risk", 20.0, "SYSTEMATIC",
                              ["Rủi ro địa chính trị ở mức trung bình (cần Event Engine)"])

        # Event Risk
        event = RiskEngine._cat("Event Risk", 25.0, "IDIOSYNCRATIC",
                                ["Rủi ro sự kiện sắp tới (cần Event Engine)"])

        # Data Risk
        data_score = 5.0 if data_available else 40.0
        data_risk = RiskEngine._cat(
            "Data Risk", data_score, "IDIOSYNCRATIC",
            ["Dữ liệu BCTC đã kiểm toán" if data_available else f"Không có dữ liệu{stub_note}"]
        )

        # Model Risk
        model_risk = RiskEngine._cat("Model Risk", 15.0, "IDIOSYNCRATIC",
                                     ["Uncertainty từ model DCF và định giá tương đối"])

        # Aggregate
        categories = [market, business, financial, valuation_risk, liquidity, macro, geo, event, data_risk, model_risk]
        total = sum(c.score for c in categories) / len(categories)
        top_contributors = [c.name for c in sorted(categories, key=lambda x: x.score, reverse=True)[:3]]

        sensitivities = [
            MacroSensitivity(
                variable="USD/VND",
                sensitivity="NEGATIVE",
                confidence="LOW" if not data_available else "MEDIUM",
                description="Historical Association: Chưa tính được — cần dữ liệu giá lịch sử."
            ),
            MacroSensitivity(
                variable="US10Y",
                sensitivity="NEGATIVE",
                confidence="LOW" if not data_available else "MEDIUM",
                description="Historical Association: Rising US yields pressure Vietnam multiples (sector-dependent)."
            )
        ]

        drawdown = DrawdownStats(
            max_drawdown=fundamentals.get("max_drawdown", -0.50),
            average_drawdown=fundamentals.get("avg_drawdown", -0.15),
            recovery_time_days=fundamentals.get("avg_recovery_days", 180),
            current_drawdown=fundamentals.get("current_drawdown", 0.0)
        )

        return StockRiskProfile(
            symbol=symbol.upper(),
            as_of=as_of,
            total_risk_score=round(total, 1),
            market_risk=market,
            business_risk=business,
            financial_risk=financial,
            valuation_risk=valuation_risk,
            liquidity_risk=liquidity,
            macro_risk=macro,
            geopolitical_risk=geo,
            event_risk=event,
            data_risk=data_risk,
            model_risk=model_risk,
            top_contributors=top_contributors,
            macro_sensitivities=sensitivities,
            drawdown_stats=drawdown,
            volatility_annualized=fundamentals.get("volatility_annualized", 0.0),
            beta=fundamentals.get("beta")
        )
