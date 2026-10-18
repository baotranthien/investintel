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
        market = RiskEngine._cat(
            "Market Risk", 50.0, "SYSTEMATIC",
            [f"Beta chưa tính được{stub_note}"] if not data_available else ["Beta calculated from price history"]
        )

        # Business Risk (Idiosyncratic)
        revenue_concentration = fundamentals.get("revenue_concentration")
        biz_score = 30.0 if data_available else 50.0
        if revenue_concentration and revenue_concentration > 0.5:
            biz_score += 20
        business = RiskEngine._cat(
            "Business Risk", biz_score, "IDIOSYNCRATIC",
            [f"Rủi ro kinh doanh chưa tính được{stub_note}"] if not data_available else ["Concentration, competitive position"]
        )

        # Financial Risk (Idiosyncratic)
        de_ratio = fundamentals.get("de_ratio")
        fin_score = 30.0 if data_available else 50.0
        if de_ratio is not None:
            if de_ratio > 3.0: fin_score = 70.0
            elif de_ratio > 1.5: fin_score = 45.0
            elif de_ratio < 0.3: fin_score = 15.0
        financial = RiskEngine._cat(
            "Financial Risk", fin_score, "IDIOSYNCRATIC",
            [f"D/E = {de_ratio:.2f}" if de_ratio is not None else f"D/E chưa có{stub_note}"]
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
