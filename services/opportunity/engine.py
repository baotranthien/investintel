from datetime import date
from typing import Dict, Any, List, Optional
from .models import OpportunityScore, SignalEvidence


class OpportunityEngine:
    """
    Combines Fundamental, Valuation, Macro, Risk, and Events signals into
    a composite Opportunity Score (0-100). Higher = more attractive opportunity.

    All scoring is deterministic based on structured inputs. When inputs are
    mocked/empty, the score is labeled with reduced confidence.

    Model version: opportunity_medium_v1
    Baseline weights (configurable, not production-calibrated):
      fundamental: 25%, valuation: 25%, macro: 20%,
      base_neutral: 20, catalyst_bonus: ±10, risk_penalty: up to 30
    """

    @staticmethod
    def _score_fundamental(fund: Dict[str, Any]) -> float:
        if not fund:
            return 50.0  # No data => neutral, NOT assumed positive
        score = 50.0
        roe = fund.get("roe")
        if roe is not None:
            if roe > 0.20: score += 15
            elif roe > 0.12: score += 8
            elif roe < 0: score -= 20
        profit_growth = fund.get("profit_growth_yoy")
        if profit_growth is not None:
            if profit_growth > 0.20: score += 15
            elif profit_growth > 0: score += 5
            elif profit_growth < -0.10: score -= 15
        de_ratio = fund.get("de_ratio")
        if de_ratio is not None:
            if de_ratio > 3.0: score -= 10
            elif de_ratio < 0.5: score += 5
        return max(0.0, min(100.0, score))

    @staticmethod
    def _score_valuation(val: Dict[str, Any]) -> float:
        if not val:
            return 50.0  # No data => neutral
        score = 50.0
        mos = val.get("margin_of_safety")
        if mos is not None:
            if mos > 0.25: score += 25
            elif mos > 0.10: score += 12
            elif mos < -0.20: score -= 20
        pe_pct = val.get("pe_percentile")
        if pe_pct is not None:
            if pe_pct < 30: score += 15
            elif pe_pct > 75: score -= 15
        return max(0.0, min(100.0, score))

    @staticmethod
    def _score_macro(macro: Any) -> float:
        if macro is None:
            return 50.0
        score = 50.0
        growth_state = getattr(getattr(macro, "growth", None), "state", None)
        liquidity_state = getattr(getattr(macro, "liquidity", None), "state", None)
        if growth_state in ("EXPANSION", "RECOVERY", "IMPROVING"): score += 15
        elif growth_state in ("CONTRACTION", "DETERIORATING"): score -= 15
        if liquidity_state in ("EXPANSION", "IMPROVING"): score += 10
        elif liquidity_state == "CONTRACTION": score -= 10
        return max(0.0, min(100.0, score))

    @staticmethod
    def _risk_penalty(risk_data: Any) -> float:
        if risk_data is None:
            return 10.0  # Unknown risk => moderate penalty
        risk_score = getattr(risk_data, "total_risk_score", 50.0)
        return (risk_score / 100.0) * 30.0

    @staticmethod
    def _catalyst_bonus(events: List[Any]) -> float:
        bonus = 0.0
        for event in (events or []):
            materiality = getattr(event, "materiality", None)
            sentiment = getattr(event, "sentiment", None)
            if materiality in ("MATERIAL", "CRITICAL") and sentiment == "POSITIVE":
                bonus += 5.0
            elif materiality in ("MATERIAL", "CRITICAL") and sentiment == "NEGATIVE":
                bonus -= 5.0
        return max(-10.0, min(10.0, bonus))

    @staticmethod
    def calculate_medium_term(
        symbol: str,
        fundamental_data: Dict[str, Any],
        valuation_data: Dict[str, Any],
        risk_data: Any,
        macro_data: Any,
        events_data: List[Any],
        as_of: date
    ) -> OpportunityScore:
        """
        Deterministic composite Opportunity Score from structured inputs.
        Returns INSUFFICIENT confidence when inputs are empty/structural stubs.

        Formula (not production-calibrated):
          raw = (f_score*0.25) + (v_score*0.25) + (m_score*0.20) + 20 + catalyst - risk_penalty
        """
        data_available = bool(fundamental_data or valuation_data)

        f_score = OpportunityEngine._score_fundamental(fundamental_data)
        v_score = OpportunityEngine._score_valuation(valuation_data)
        m_score = OpportunityEngine._score_macro(macro_data)
        r_penalty = OpportunityEngine._risk_penalty(risk_data)
        c_bonus = OpportunityEngine._catalyst_bonus(events_data or [])

        raw_score = (f_score * 0.25) + (v_score * 0.25) + (m_score * 0.20) + 20.0 + c_bonus - r_penalty
        final_score = max(0.0, min(100.0, raw_score))

        # Confidence based on data quality
        if not data_available:
            confidence = "INSUFFICIENT"
            data_note = "Dữ liệu đầu vào chưa có — điểm số này là ước tính cơ sở (stub). Không sử dụng cho quyết định đầu tư."
        elif macro_data is None:
            confidence = "LOW"
            data_note = "Thiếu dữ liệu vĩ mô — phân tích bị hạn chế."
        else:
            confidence = "MODERATE"
            data_note = None

        # Detect signal conflict
        signal_conflict = (v_score > 65 and f_score < 40) or (v_score < 40 and f_score > 65)

        # Evidence from actual input scores, not hardcoded narratives
        why_now: List[SignalEvidence] = []
        why_not_now: List[SignalEvidence] = []

        if v_score > 65:
            why_now.append(SignalEvidence(category="Valuation", description=f"Định giá hấp dẫn so với cơ sở (điểm: {v_score:.0f}/100).", direction="POSITIVE"))
        if f_score > 65:
            why_now.append(SignalEvidence(category="Fundamental", description=f"Nền tảng doanh nghiệp mạnh (điểm: {f_score:.0f}/100).", direction="POSITIVE"))
        if m_score > 65:
            why_now.append(SignalEvidence(category="Macro", description=f"Vĩ mô hỗ trợ (điểm: {m_score:.0f}/100).", direction="POSITIVE"))
        if c_bonus > 0:
            why_now.append(SignalEvidence(category="Catalyst", description=f"{len(events_data or [])} sự kiện có lợi được phát hiện.", direction="POSITIVE"))

        if v_score < 40:
            why_not_now.append(SignalEvidence(category="Valuation", description=f"Định giá đắt so với cơ sở (điểm: {v_score:.0f}/100).", direction="NEGATIVE"))
        if f_score < 40:
            why_not_now.append(SignalEvidence(category="Fundamental", description=f"Nền tảng yếu (điểm: {f_score:.0f}/100).", direction="NEGATIVE"))
        if m_score < 40:
            why_not_now.append(SignalEvidence(category="Macro", description=f"Vĩ mô bất lợi (điểm: {m_score:.0f}/100).", direction="NEGATIVE"))
        if data_note:
            why_not_now.append(SignalEvidence(category="Data", description=data_note, direction="NEGATIVE"))

        what_wrong = []
        if not data_available:
            what_wrong.append("Dữ liệu tài chính chưa đầy đủ — điểm số dựa trên ước tính cơ sở.")
        else:
            if v_score < 45:
                what_wrong.append("Mức định giá hiện tại ở vùng cao, biên an toàn hạn chế.")
            if f_score < 45:
                what_wrong.append("Biên lợi nhuận hoặc sức khỏe tài chính chịu áp lực ngắn hạn.")
            what_wrong.append("Biến động thị trường và chu kỳ ngành có thể tác động đến tiến độ phục hồi.")
            what_wrong.append("Các yếu tố vĩ mô và lãi suất có thể diễn biến bất lợi hơn dự báo.")

        # Opportunity type classification from computed scores
        types = []
        if v_score > 65 and f_score > 60: types.append("Quality Opportunity")
        elif v_score > 65: types.append("Value Opportunity")
        if c_bonus > 0: types.append("Catalyst Opportunity")
        if m_score > 65: types.append("Macro Beneficiary")
        if not types: types.append("Neutral / Monitoring")

        return OpportunityScore(
            symbol=symbol.upper(),
            as_of=as_of,
            horizon="MEDIUM_TERM",
            opportunity_score=round(final_score, 1),
            risk_score=round(getattr(risk_data, "total_risk_score", 50.0), 1),
            confidence=confidence,
            opportunity_types=types,
            is_candidate=final_score >= 70 and confidence not in ("INSUFFICIENT", "LOW"),
            why_now=why_now,
            why_not_now=why_not_now,
            what_could_go_wrong=what_wrong,
            fundamental_signal="POSITIVE" if f_score > 60 else ("NEGATIVE" if f_score < 40 else "MIXED"),
            valuation_signal="POSITIVE" if v_score > 60 else ("NEGATIVE" if v_score < 40 else "MIXED"),
            technical_signal="MIXED",  # Technical engine not yet implemented
            macro_signal="POSITIVE" if m_score > 60 else ("NEGATIVE" if m_score < 40 else "MIXED"),
            signal_conflict=signal_conflict,
            model_version="opportunity_medium_v1"
        )
